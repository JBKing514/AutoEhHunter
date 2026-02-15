#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import psycopg
import requests
import requests_unixsocket
import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer


RUNTIME_DIR = Path(os.getenv("DATA_UI_RUNTIME_DIR", "/app/runtime/webui"))
SCHEDULE_FILE = RUNTIME_DIR / "schedule.json"
RUN_HISTORY_FILE = RUNTIME_DIR / "run_history.jsonl"
TASK_LOG_DIR = RUNTIME_DIR / "task_logs"

DEFAULT_SCHEDULE = {
    "eh_fetch": {"enabled": False, "interval_minutes": 30},
    "lrr_export": {"enabled": False, "interval_minutes": 60},
    "text_ingest": {"enabled": False, "interval_minutes": 60},
    "compute_daily": {"enabled": False, "interval_minutes": 60},
}


def ensure_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    TASK_LOG_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_schedule() -> dict[str, Any]:
    ensure_dirs()
    if not SCHEDULE_FILE.exists():
        save_schedule(DEFAULT_SCHEDULE)
        return dict(DEFAULT_SCHEDULE)
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    merged = dict(DEFAULT_SCHEDULE)
    merged.update(data if isinstance(data, dict) else {})
    return merged


def save_schedule(data: dict[str, Any]) -> None:
    ensure_dirs()
    SCHEDULE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_run_history(item: dict[str, Any]) -> None:
    ensure_dirs()
    with RUN_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_run_history(limit: int = 200) -> list[dict[str, Any]]:
    if not RUN_HISTORY_FILE.exists():
        return []
    rows: list[dict[str, Any]] = []
    with RUN_HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


def db_dsn() -> str:
    dsn = os.getenv("POSTGRES_DSN", "").strip()
    return dsn


def query_df(sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    dsn = db_dsn()
    if not dsn:
        return pd.DataFrame()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def run_task(task_name: str, cmd: list[str], timeout_s: int = 1800) -> dict[str, Any]:
    ensure_dirs()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = TASK_LOG_DIR / f"{task_name}_{ts}.log"
    started = time.time()
    status = "success"
    rc = 0
    out = ""
    err = ""
    try:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
            rc = int(proc.returncode)
            out = proc.stdout or ""
            err = proc.stderr or ""
            if rc != 0:
                status = "failed"
        except FileNotFoundError as e:
            if cmd and cmd[0] == "docker":
                rc, out, err = run_docker_exec_via_socket(cmd, timeout_s=timeout_s)
                if rc != 0:
                    status = "failed"
            else:
                raise e
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        rc = 124
        raw_out = e.stdout or ""
        raw_err = e.stderr or ""
        out = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out)
        err_txt = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
        err = err_txt + "\nTimeout expired"
    elapsed = round(time.time() - started, 2)
    content = (
        f"[{now_iso()}] task={task_name} status={status} rc={rc} elapsed={elapsed}s\n"
        + "\n--- STDOUT ---\n"
        + out
        + "\n--- STDERR ---\n"
        + err
    )
    log_path.write_text(content, encoding="utf-8")
    event = {
        "ts": now_iso(),
        "task": task_name,
        "status": status,
        "rc": rc,
        "elapsed_s": elapsed,
        "log_file": str(log_path),
    }
    append_run_history(event)
    return event


def run_docker_exec_via_socket(cmd: list[str], timeout_s: int = 1800) -> tuple[int, str, str]:
    """Fallback for environments where docker CLI binary is unavailable.

    Supports command shape:
      docker exec [-i|-t|-it] <container> <script> [args...]
    """
    if not Path("/var/run/docker.sock").exists():
        return (127, "", "docker CLI missing and /var/run/docker.sock not mounted")

    if len(cmd) < 4 or cmd[0] != "docker" or cmd[1] != "exec":
        return (2, "", f"unsupported docker command: {' '.join(cmd)}")

    idx = 2
    while idx < len(cmd) and cmd[idx].startswith("-"):
        idx += 1
    if idx >= len(cmd):
        return (2, "", "missing container name in docker exec command")
    container = cmd[idx]
    argv = cmd[idx + 1 :]
    if not argv:
        return (2, "", "missing command in docker exec")

    session = requests_unixsocket.Session()
    base = "http+unix://%2Fvar%2Frun%2Fdocker.sock"

    try:
        create = session.post(
            f"{base}/containers/{container}/exec",
            json={
                "AttachStdout": True,
                "AttachStderr": True,
                "Tty": True,
                "Cmd": argv,
            },
            timeout=min(timeout_s, 30),
        )
        if create.status_code >= 400:
            return (1, "", f"docker exec create failed: HTTP {create.status_code} {create.text}")
        exec_id = (create.json() or {}).get("Id")
        if not exec_id:
            return (1, "", "docker exec create failed: missing exec id")

        start = session.post(
            f"{base}/exec/{exec_id}/start",
            json={"Detach": False, "Tty": True},
            timeout=timeout_s,
        )
        combined = start.text if start.text is not None else ""

        inspect = session.get(f"{base}/exec/{exec_id}/json", timeout=min(timeout_s, 30))
        if inspect.status_code >= 400:
            return (1, combined, f"docker exec inspect failed: HTTP {inspect.status_code} {inspect.text}")
        exit_code = int((inspect.json() or {}).get("ExitCode") or 0)
        if exit_code == 0:
            return (0, combined, "")
        return (exit_code, combined, "docker exec returned non-zero exit code")
    except Exception as e:
        return (1, "", f"docker socket exec error: {e}")


def compute_container_name() -> str:
    return os.getenv("COMPUTE_CONTAINER_NAME", "autoeh-compute").strip() or "autoeh-compute"


def compute_exec_cmd(script_path: str, args: list[str] | None = None) -> list[str]:
    cmd = ["docker", "exec", "-i", compute_container_name(), script_path]
    if args:
        cmd.extend(args)
    return cmd


@st.cache_resource
def get_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.start()
    return scheduler


def sync_scheduler() -> None:
    cfg = load_schedule()
    scheduler = get_scheduler()
    desired = {
        "eh_fetch": ["/app/ehCrawler/run_eh_fetch.sh"],
        "lrr_export": ["/app/lrrDataFlush/run_daily_lrr_export.sh"],
        "text_ingest": ["/app/textIngest/run_daily_text_ingest.sh"],
        "compute_daily": compute_exec_cmd("/app/vectorIngest/run_daily.sh"),
    }
    existing = {j.id for j in scheduler.get_jobs()}
    for job_id, cmd in desired.items():
        setting = cfg.get(job_id, {})
        enabled = bool(setting.get("enabled", False))
        minutes = max(1, int(setting.get("interval_minutes", 60)))
        if enabled:
            if job_id in existing:
                scheduler.reschedule_job(job_id, trigger="interval", minutes=minutes)
            else:
                scheduler.add_job(run_task, "interval", minutes=minutes, args=[job_id, cmd], id=job_id, replace_existing=True)
        else:
            if job_id in existing:
                scheduler.remove_job(job_id)


def check_http(url: str, timeout: int = 4) -> tuple[bool, str]:
    if not url:
        return (False, "empty url")
    candidate = str(url).strip()
    parsed = urlparse(candidate)
    if not parsed.scheme:
        candidate = f"http://{candidate}"
    try:
        r = requests.get(candidate, timeout=timeout)
        return (r.ok, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, str(e))


def dashboard_page() -> None:
    st.subheader("Dashboard")
    col1, col2, col3 = st.columns(3)

    works = query_df("SELECT count(*) AS n FROM works")
    eh_works = query_df("SELECT count(*) AS n FROM eh_works")
    recent = query_df("SELECT max(last_fetched_at) AS latest FROM eh_works")

    total_works = int(works.iloc[0]["n"]) if not works.empty else 0
    total_eh = int(eh_works.iloc[0]["n"]) if not eh_works.empty else 0
    last_fetch = str(recent.iloc[0]["latest"]) if not recent.empty else "-"

    col1.metric("库内本子数(works)", total_works)
    col2.metric("EH 元数据数(eh_works)", total_eh)
    col3.metric("最近 EH 抓取", last_fetch)

    st.markdown("### 系统健康")
    lrr_base = os.getenv("LRR_BASE", "http://lanraragi:3000").strip().rstrip("/")
    if not urlparse(lrr_base).scheme:
        lrr_base = f"http://{lrr_base}"
    compute_health = os.getenv("COMPUTE_HEALTH_URL", "http://autoeh-compute:18080/health")
    openai_health = os.getenv("OPENAI_HEALTH_URL", "").strip()

    ok_lrr, msg_lrr = check_http(f"{lrr_base}/api/info")
    ok_compute, msg_compute = check_http(compute_health)
    c1, c2, c3 = st.columns(3)
    c1.metric("LRR", "UP" if ok_lrr else "DOWN", msg_lrr)
    c2.metric("Compute Agent", "UP" if ok_compute else "DOWN", msg_compute)
    if openai_health:
        ok_llm, msg_llm = check_http(openai_health)
        c3.metric("LLM", "UP" if ok_llm else "DOWN", msg_llm)
    else:
        c3.metric("LLM", "N/A", "Set OPENAI_HEALTH_URL")


def control_page() -> None:
    st.subheader("Control")
    st.markdown("### Manual Trigger")
    col1, col2, col3 = st.columns(3)
    if col1.button("立即爬取 EH", use_container_width=True):
        result = run_task("eh_fetch_manual", ["/app/ehCrawler/run_eh_fetch.sh"])
        st.write(result)
    if col2.button("导出 LRR", use_container_width=True):
        result = run_task("lrr_export_manual", ["/app/lrrDataFlush/run_daily_lrr_export.sh"])
        st.write(result)
    if col3.button("文本入库", use_container_width=True):
        result = run_task("text_ingest_manual", ["/app/textIngest/run_daily_text_ingest.sh"])
        st.write(result)

    st.markdown("### Manual Trigger (Compute)")
    st.caption("需要 data-ui 容器可访问 Docker Socket，并且 compute 容器名正确。")
    c4, c5, c6 = st.columns(3)
    worker_args = st.text_input("run_worker 参数", value="--limit 20 --only-missing", help="会直接追加到 run_worker.sh 后")
    if c4.button("向量入库 run_worker", use_container_width=True):
        args = [a for a in worker_args.split(" ") if a.strip()]
        result = run_task("compute_run_worker_manual", compute_exec_cmd("/app/vectorIngest/run_worker.sh", args))
        st.write(result)
    if c5.button("EH 入库 run_eh_ingest", use_container_width=True):
        result = run_task("compute_run_eh_ingest_manual", compute_exec_cmd("/app/vectorIngest/run_eh_ingest.sh"))
        st.write(result)
    if c6.button("日常入库 run_daily", use_container_width=True):
        result = run_task("compute_run_daily_manual", compute_exec_cmd("/app/vectorIngest/run_daily.sh"))
        st.write(result)

    st.markdown("### Scheduler")
    cfg = load_schedule()
    with st.form("scheduler_form"):
        out = {}
        for key, label in [
            ("eh_fetch", "EH Fetch"),
            ("lrr_export", "LRR Export"),
            ("text_ingest", "Text Ingest"),
            ("compute_daily", "Compute run_daily"),
        ]:
            st.markdown(f"**{label}**")
            c1, c2 = st.columns([1, 2])
            enabled = c1.checkbox(f"启用 {label}", value=bool(cfg.get(key, {}).get("enabled", False)), key=f"en_{key}")
            mins = c2.number_input(
                f"间隔(分钟) {label}",
                min_value=1,
                max_value=24 * 60,
                value=int(cfg.get(key, {}).get("interval_minutes", 60)),
                key=f"min_{key}",
            )
            out[key] = {"enabled": enabled, "interval_minutes": int(mins)}

        submitted = st.form_submit_button("保存定时配置")
        if submitted:
            save_schedule(out)
            sync_scheduler()
            st.success("已保存并应用定时任务。")


def audit_page() -> None:
    st.subheader("Audit")
    st.markdown("### 最近任务记录")
    rows = load_run_history(limit=300)
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df.sort_values("ts", ascending=False), width="stretch", hide_index=True)
    else:
        st.info("暂无任务记录。")

    st.markdown("### 日志预览")
    logs = sorted(TASK_LOG_DIR.glob("*.log"), reverse=True)
    pick = st.selectbox("选择日志文件", options=[str(p.name) for p in logs] if logs else ["<none>"])
    if logs and pick != "<none>":
        p = TASK_LOG_DIR / pick
        txt = p.read_text(encoding="utf-8", errors="replace")
        st.text_area("log", txt[-12000:], height=320)


def xp_map_page() -> None:
    st.subheader("XP 地形图")
    days = st.slider("统计窗口(天)", min_value=3, max_value=90, value=30)
    k = st.slider("聚类数", min_value=2, max_value=8, value=3)

    sql = (
        "SELECT w.arcid, w.title, w.tags "
        "FROM works w JOIN read_events r ON r.arcid = w.arcid "
        "WHERE r.read_time >= extract(epoch from now())::bigint - %s "
        "GROUP BY w.arcid, w.title, w.tags "
        "LIMIT 1000"
    )
    df = query_df(sql, (days * 86400,))
    if df.empty:
        st.warning("暂无足够阅读记录用于聚类。")
        return

    docs = [" ".join((tags or [])) for tags in df["tags"].tolist()]
    if len(docs) < 4 or sum(len(d.strip()) > 0 for d in docs) < 4:
        st.warning("可用于聚类的标签文本不足。")
        return

    vec = TfidfVectorizer(max_features=3000, token_pattern=r"[^\s]+")
    X = vec.fit_transform(docs)
    n_samples = X.shape[0]
    k_use = min(k, max(2, n_samples // 2))
    km = KMeans(n_clusters=k_use, n_init=10, random_state=42)
    labels = km.fit_predict(X)

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X.toarray())
    plot_df = pd.DataFrame(
        {
            "x": coords[:, 0],
            "y": coords[:, 1],
            "cluster": labels.astype(str),
            "title": df["title"].fillna("").astype(str),
            "arcid": df["arcid"].astype(str),
        }
    )
    fig = px.scatter(plot_df, x="x", y="y", color="cluster", hover_data=["title", "arcid"], title="XP Clusters (PCA 2D)")
    st.plotly_chart(fig, width="stretch")


def main() -> None:
    st.set_page_config(page_title="AutoEhHunter Data UI", layout="wide")
    ensure_dirs()
    sync_scheduler()

    st.title("AutoEhHunter Data UI")
    tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Control", "Audit", "XP Map"])
    with tab1:
        dashboard_page()
    with tab2:
        control_page()
    with tab3:
        audit_page()
    with tab4:
        xp_map_page()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import base64
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import pandas as pd
import plotly.express as px
import psycopg
import requests
import requests_unixsocket
import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet, InvalidToken
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer


RUNTIME_DIR = Path(os.getenv("DATA_UI_RUNTIME_DIR", "/app/runtime/webui"))
SCHEDULE_FILE = RUNTIME_DIR / "schedule.json"
RUN_HISTORY_FILE = RUNTIME_DIR / "run_history.jsonl"
TASK_LOG_DIR = RUNTIME_DIR / "task_logs"
APP_CONFIG_FILE = RUNTIME_DIR / "app_config.json"
APP_CONFIG_KEY_FILE = RUNTIME_DIR / ".app_config.key"
LOGO_PATH = Path(__file__).resolve().parent / "ico" / "AutoEhHunterLogo_128.png"
I18N_DIR = Path(__file__).resolve().parent / "i18n"

DEFAULT_SCHEDULE = {
    "eh_fetch": {"enabled": False, "interval_minutes": 30},
    "lrr_export": {"enabled": False, "interval_minutes": 60},
    "text_ingest": {"enabled": False, "interval_minutes": 60},
    "compute_daily": {"enabled": False, "interval_minutes": 60},
}

def _load_i18n(lang: str) -> dict[str, str]:
    p = I18N_DIR / f"{lang}.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return {str(k): str(v) for k, v in obj.items()}
    except Exception:
        return {}
    return {}


STRINGS = {
    "zh": _load_i18n("zh"),
    "en": _load_i18n("en"),
}


CONFIG_SCOPE = "global"
CONFIG_SPECS: dict[str, dict[str, Any]] = {
    "POSTGRES_DSN": {"type": "text", "default": "", "secret": True},
    "POSTGRES_HOST": {"type": "text", "default": "pgvector-db"},
    "POSTGRES_PORT": {"type": "int", "default": 5432, "min": 1, "max": 65535},
    "POSTGRES_DB": {"type": "text", "default": "lrr_library"},
    "POSTGRES_USER": {"type": "text", "default": "postgres"},
    "POSTGRES_PASSWORD": {"type": "text", "default": "", "secret": True},
    "POSTGRES_SSLMODE": {"type": "text", "default": "prefer"},
    "LRR_BASE": {"type": "url", "default": "http://lanraragi:3000"},
    "LRR_API_KEY": {"type": "text", "default": "", "secret": True},
    "OPENAI_API_KEY": {"type": "text", "default": "", "secret": True},
    "COMPUTE_HEALTH_URL": {"type": "url", "default": "http://autoeh-compute:18080/health"},
    "OPENAI_HEALTH_URL": {"type": "url", "default": ""},
    "COMPUTE_CONTAINER_NAME": {"type": "text", "default": "autoeh-compute"},
    "DATA_UI_LANG": {"type": "text", "default": "zh"},
    "TEXT_INGEST_PRUNE_NOT_SEEN": {"type": "bool", "default": True},
    "WORKER_ONLY_MISSING": {"type": "bool", "default": True},
    "EH_FETCH_MAX_PAGES": {"type": "int", "default": 8, "min": 1, "max": 64},
    "TEXT_INGEST_BATCH_SIZE": {"type": "int", "default": 1000, "min": 100, "max": 5000},
    "EH_QUEUE_LIMIT": {"type": "int", "default": 2000, "min": 100, "max": 5000},
}

COMPUTE_ENV_FORWARD_KEYS = [
    "POSTGRES_DSN",
    "LRR_BASE",
    "LRR_API_KEY",
    "OPENAI_API_KEY",
    "WORKER_ONLY_MISSING",
    "EH_QUEUE_LIMIT",
]


def _str_bool(v: bool) -> str:
    return "1" if bool(v) else "0"


def _as_bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _normalize_value(key: str, raw: Any) -> str:
    spec = CONFIG_SPECS.get(key, {"type": "text", "default": ""})
    kind = str(spec.get("type", "text"))
    default = spec.get("default", "")
    if kind == "bool":
        return _str_bool(_as_bool(raw, bool(default)))
    if kind == "int":
        try:
            n = int(str(raw).strip())
        except Exception:
            n = int(default)
        n = max(int(spec.get("min", n)), min(int(spec.get("max", n)), n))
        return str(n)
    if raw is None:
        return str(default)
    return str(raw).strip()


@st.cache_resource
def get_config_cipher() -> Fernet:
    ensure_dirs()
    key_env = os.getenv("DATA_UI_CONFIG_CRYPT_KEY", "").strip()
    key: bytes
    if key_env:
        if len(key_env) == 44 and key_env.endswith("="):
            key = key_env.encode("ascii")
        else:
            key = base64.urlsafe_b64encode(key_env.encode("utf-8")[:32].ljust(32, b"0"))
        return Fernet(key)

    if APP_CONFIG_KEY_FILE.exists():
        key = APP_CONFIG_KEY_FILE.read_bytes().strip()
        return Fernet(key)

    key = Fernet.generate_key()
    APP_CONFIG_KEY_FILE.write_bytes(key + b"\n")
    return Fernet(key)


def _encrypt_secret(value: str) -> str:
    v = str(value or "").strip()
    if not v:
        return ""
    token = get_config_cipher().encrypt(v.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def _decrypt_secret(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if not s.startswith("enc:v1:"):
        return s
    token = s[len("enc:v1:") :]
    try:
        return get_config_cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


def _parse_dsn_components(dsn: str) -> dict[str, str]:
    out: dict[str, str] = {}
    s = str(dsn or "").strip()
    if not s:
        return out
    try:
        u = urlparse(s)
    except Exception:
        return out
    out["POSTGRES_HOST"] = (u.hostname or "").strip()
    try:
        out["POSTGRES_PORT"] = str(u.port or 5432)
    except Exception:
        out["POSTGRES_PORT"] = "5432"
    out["POSTGRES_DB"] = (u.path or "").lstrip("/").strip()
    out["POSTGRES_USER"] = (u.username or "").strip()
    out["POSTGRES_PASSWORD"] = (u.password or "").strip()
    q = (u.query or "").strip()
    if "sslmode=" in q:
        for item in q.split("&"):
            if item.startswith("sslmode="):
                out["POSTGRES_SSLMODE"] = item.split("=", 1)[1].strip()
                break
    return out


def _build_dsn(values: dict[str, str]) -> str:
    manual = str(values.get("POSTGRES_DSN", "")).strip()
    host = str(values.get("POSTGRES_HOST", "")).strip()
    db = str(values.get("POSTGRES_DB", "")).strip()
    user = str(values.get("POSTGRES_USER", "")).strip()
    pwd = str(values.get("POSTGRES_PASSWORD", "")).strip()
    if not host or not db or not user:
        return manual
    port = _normalize_value("POSTGRES_PORT", values.get("POSTGRES_PORT", "5432"))
    sslmode = str(values.get("POSTGRES_SSLMODE", "prefer")).strip() or "prefer"
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{quote_plus(db)}"
        f"?sslmode={quote_plus(sslmode)}"
    )


def _load_json_config() -> dict[str, str]:
    ensure_dirs()
    if not APP_CONFIG_FILE.exists():
        return {}
    try:
        obj = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    vals = obj.get("values", obj) if isinstance(obj, dict) else {}
    if not isinstance(vals, dict):
        return {}
    out: dict[str, str] = {}
    for key, spec in CONFIG_SPECS.items():
        if key not in vals:
            continue
        raw = vals.get(key)
        if spec.get("secret", False):
            out[key] = _decrypt_secret(str(raw or ""))
        else:
            out[key] = _normalize_value(key, raw)
    return out


def _save_json_config(values: dict[str, str]) -> None:
    ensure_dirs()
    payload: dict[str, Any] = {"version": 1, "updated_at": now_iso(), "values": {}}
    for key, spec in CONFIG_SPECS.items():
        raw = str(values.get(key, _normalize_value(key, spec.get("default", ""))))
        if spec.get("secret", False):
            payload["values"][key] = _encrypt_secret(raw)
        else:
            payload["values"][key] = _normalize_value(key, raw)
    APP_CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_db_config(dsn: str) -> tuple[dict[str, str], str]:
    s = str(dsn or "").strip()
    if not s:
        return ({}, "missing dsn")
    sql = (
        "SELECT key, value, is_secret "
        "FROM app_config "
        "WHERE scope = %s"
    )
    try:
        out: dict[str, str] = {}
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (CONFIG_SCOPE,))
                for key, value, is_secret in cur.fetchall():
                    if key not in CONFIG_SPECS:
                        continue
                    if is_secret:
                        out[key] = _decrypt_secret(str(value or ""))
                    else:
                        out[key] = _normalize_value(str(key), value)
        return (out, "")
    except Exception as e:
        return ({}, str(e))


def _save_db_config(dsn: str, values: dict[str, str]) -> tuple[bool, str]:
    s = str(dsn or "").strip()
    if not s:
        return (False, "missing dsn")

    create_sql = (
        "CREATE TABLE IF NOT EXISTS app_config ("
        "scope text NOT NULL DEFAULT 'global',"
        "key text NOT NULL,"
        "value text NOT NULL,"
        "value_type text NOT NULL DEFAULT 'string',"
        "is_secret boolean NOT NULL DEFAULT false,"
        "description text,"
        "created_at timestamptz NOT NULL DEFAULT now(),"
        "updated_at timestamptz NOT NULL DEFAULT now(),"
        "PRIMARY KEY (scope, key)"
        ")"
    )
    upsert_sql = (
        "INSERT INTO app_config(scope, key, value, value_type, is_secret, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, now()) "
        "ON CONFLICT (scope, key) DO UPDATE "
        "SET value = EXCLUDED.value, "
        "value_type = EXCLUDED.value_type, "
        "is_secret = EXCLUDED.is_secret, "
        "updated_at = now()"
    )
    try:
        with psycopg.connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute(create_sql)
                for key, spec in CONFIG_SPECS.items():
                    plain = str(values.get(key, _normalize_value(key, spec.get("default", ""))))
                    stored = _encrypt_secret(plain) if spec.get("secret", False) else _normalize_value(key, plain)
                    cur.execute(
                        upsert_sql,
                        (
                            CONFIG_SCOPE,
                            key,
                            stored,
                            str(spec.get("type", "text")),
                            bool(spec.get("secret", False)),
                        ),
                    )
            conn.commit()
        return (True, "")
    except Exception as e:
        return (False, str(e))


def resolve_config(force_refresh: bool = False) -> tuple[dict[str, str], dict[str, Any]]:
    cache_key = "_runtime_config_cache"
    if not force_refresh and cache_key in st.session_state:
        return st.session_state[cache_key]

    merged: dict[str, str] = {}
    for key, spec in CONFIG_SPECS.items():
        merged[key] = _normalize_value(key, spec.get("default", ""))

    env_vals: dict[str, str] = {}
    for key in CONFIG_SPECS:
        v = os.getenv(key)
        if v is None:
            continue
        env_vals[key] = _normalize_value(key, v)
    if env_vals.get("POSTGRES_DSN"):
        env_vals.update(_parse_dsn_components(env_vals["POSTGRES_DSN"]))

    json_vals = _load_json_config()
    if json_vals.get("POSTGRES_DSN"):
        json_vals.update(_parse_dsn_components(json_vals["POSTGRES_DSN"]))

    merged.update(env_vals)
    merged.update(json_vals)
    merged["POSTGRES_DSN"] = _build_dsn(merged)

    db_vals, db_error = _load_db_config(merged.get("POSTGRES_DSN", ""))
    if db_vals.get("POSTGRES_DSN"):
        db_vals.update(_parse_dsn_components(db_vals["POSTGRES_DSN"]))
    merged.update(db_vals)
    merged["POSTGRES_DSN"] = _build_dsn(merged)

    meta = {
        "db_connected": bool(merged.get("POSTGRES_DSN", "")) and not db_error,
        "db_error": db_error,
        "sources": "db > json > env",
    }
    st.session_state[cache_key] = (merged, meta)
    return merged, meta


def get_config_value(key: str, fallback: str = "") -> str:
    cfg, _ = resolve_config()
    return str(cfg.get(key, fallback))


def build_runtime_env() -> dict[str, str]:
    cfg, _ = resolve_config()
    env = dict(os.environ)
    for key in CONFIG_SPECS:
        val = str(cfg.get(key, ""))
        if val:
            env[key] = val
    env["POSTGRES_DSN"] = cfg.get("POSTGRES_DSN", "")
    return env


def get_lang() -> str:
    if "ui_lang" not in st.session_state:
        st.session_state.ui_lang = get_config_value("DATA_UI_LANG", "zh").strip().lower()
    if st.session_state.ui_lang not in STRINGS:
        st.session_state.ui_lang = "zh"
    return st.session_state.ui_lang


def t(key: str, **kwargs: Any) -> str:
    lang = get_lang()
    raw = STRINGS.get(lang, {}).get(key, STRINGS["en"].get(key, key))
    try:
        return str(raw).format(**kwargs)
    except Exception:
        return str(raw)


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
    return get_config_value("POSTGRES_DSN", "").strip()


def query_df(sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    dsn = db_dsn()
    if not dsn:
        return pd.DataFrame()
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [d.name for d in cur.description] if cur.description else []
        st.session_state.pop("_last_db_query_error", None)
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.session_state["_last_db_query_error"] = str(e)
        return pd.DataFrame()


def run_docker_exec_via_socket(cmd: list[str], timeout_s: int = 1800) -> tuple[int, str, str]:
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
            json={"AttachStdout": True, "AttachStderr": True, "Tty": True, "Cmd": argv},
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
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
                env=build_runtime_env(),
            )
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


def compute_container_name() -> str:
    return get_config_value("COMPUTE_CONTAINER_NAME", "autoeh-compute").strip() or "autoeh-compute"


def compute_exec_cmd(script_path: str, args: list[str] | None = None) -> list[str]:
    runtime_env = build_runtime_env()
    cmd = ["docker", "exec", "-i", compute_container_name(), "env"]
    for key in COMPUTE_ENV_FORWARD_KEYS:
        val = str(runtime_env.get(key, "")).strip()
        if val:
            cmd.append(f"{key}={val}")
    cmd.append(script_path)
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


def render_header() -> None:
    left, right = st.columns([8, 2])
    with left:
        cols = st.columns([1, 12])
        with cols[0]:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=42)
        with cols[1]:
            st.markdown(f"## {t('app.title')}")
    with right:
        current = get_lang()
        st.markdown(t("lang.current", lang=current.upper()))
        choice = st.selectbox(
            t("lang.label"),
            options=["ZH", "EN"],
            index=0 if current == "zh" else 1,
            label_visibility="collapsed",
            key="lang_switch",
        )
        st.session_state.ui_lang = "zh" if choice == "ZH" else "en"


def dashboard_page() -> None:
    st.subheader(t("dashboard.title"))
    col1, col2, col3 = st.columns(3)
    works = query_df("SELECT count(*) AS n FROM works")
    eh_works = query_df("SELECT count(*) AS n FROM eh_works")
    recent = query_df("SELECT max(last_fetched_at) AS latest FROM eh_works")

    db_err = str(st.session_state.get("_last_db_query_error", "")).strip()
    if db_err:
        st.warning(t("dashboard.db_warning", reason=db_err))

    total_works = int(works.iloc[0]["n"]) if not works.empty else 0
    total_eh = int(eh_works.iloc[0]["n"]) if not eh_works.empty else 0
    last_fetch = str(recent.iloc[0]["latest"]) if not recent.empty else "-"

    col1.metric(t("dashboard.metric.works"), total_works)
    col2.metric(t("dashboard.metric.eh_works"), total_eh)
    col3.metric(t("dashboard.metric.last_fetch"), last_fetch)

    st.markdown(f"### {t('dashboard.health')}")
    lrr_base = get_config_value("LRR_BASE", "http://lanraragi:3000").strip().rstrip("/")
    if not urlparse(lrr_base).scheme:
        lrr_base = f"http://{lrr_base}"
    compute_health = get_config_value("COMPUTE_HEALTH_URL", "http://autoeh-compute:18080/health")
    openai_health = get_config_value("OPENAI_HEALTH_URL", "").strip()

    ok_lrr, msg_lrr = check_http(f"{lrr_base}/api/info")
    ok_compute, msg_compute = check_http(compute_health)
    c1, c2, c3 = st.columns(3)
    c1.metric(t("health.lrr"), t("status.up") if ok_lrr else t("status.down"), msg_lrr)
    c2.metric(t("health.compute"), t("status.up") if ok_compute else t("status.down"), msg_compute)
    if openai_health:
        ok_llm, msg_llm = check_http(openai_health)
        c3.metric(t("health.llm"), t("status.up") if ok_llm else t("status.down"), msg_llm)
    else:
        c3.metric(t("health.llm"), t("status.na"), t("health.llm.na"))


def control_page() -> None:
    st.subheader(t("control.title"))
    st.markdown(f"### {t('control.manual')}")
    col1, col2, col3 = st.columns(3)
    if col1.button(t("control.btn.eh_fetch"), width="stretch"):
        st.write(run_task("eh_fetch_manual", ["/app/ehCrawler/run_eh_fetch.sh"]))
    if col2.button(t("control.btn.lrr_export"), width="stretch"):
        st.write(run_task("lrr_export_manual", ["/app/lrrDataFlush/run_daily_lrr_export.sh"]))
    if col3.button(t("control.btn.text_ingest"), width="stretch"):
        st.write(run_task("text_ingest_manual", ["/app/textIngest/run_daily_text_ingest.sh"]))

    st.markdown(f"### {t('control.manual.compute')}")
    st.caption(t("control.caption.compute"))
    worker_args = st.text_input(t("control.worker.args"), value="--limit 20 --only-missing", help=t("control.worker.args.help"))
    c4, c5, c6 = st.columns(3)
    if c4.button(t("control.btn.compute_worker"), width="stretch"):
        args = [a for a in worker_args.split(" ") if a.strip()]
        st.write(run_task("compute_run_worker_manual", compute_exec_cmd("/app/vectorIngest/run_worker.sh", args)))
    if c5.button(t("control.btn.compute_eh_ingest"), width="stretch"):
        st.write(run_task("compute_run_eh_ingest_manual", compute_exec_cmd("/app/vectorIngest/run_eh_ingest.sh")))
    if c6.button(t("control.btn.compute_daily"), width="stretch"):
        st.write(run_task("compute_run_daily_manual", compute_exec_cmd("/app/vectorIngest/run_daily.sh")))

    st.markdown(f"### {t('control.scheduler')}")
    cfg = load_schedule()
    labels = {
        "eh_fetch": t("scheduler.eh_fetch"),
        "lrr_export": t("scheduler.lrr_export"),
        "text_ingest": t("scheduler.text_ingest"),
        "compute_daily": t("scheduler.compute_daily"),
    }
    with st.form("scheduler_form"):
        out: dict[str, Any] = {}
        for key in ["eh_fetch", "lrr_export", "text_ingest", "compute_daily"]:
            label = labels[key]
            st.markdown(f"**{label}**")
            c1, c2 = st.columns([1, 2])
            enabled = c1.checkbox(t("control.scheduler.enable", label=label), value=bool(cfg.get(key, {}).get("enabled", False)), key=f"en_{key}")
            mins = c2.number_input(
                t("control.scheduler.interval", label=label),
                min_value=1,
                max_value=24 * 60,
                value=int(cfg.get(key, {}).get("interval_minutes", 60)),
                key=f"min_{key}",
            )
            out[key] = {"enabled": enabled, "interval_minutes": int(mins)}

        if st.form_submit_button(t("control.scheduler.save")):
            save_schedule(out)
            sync_scheduler()
            st.success(t("control.scheduler.saved"))


def _validate_url(value: str, required: bool = False) -> str:
    v = str(value or "").strip()
    if not v:
        return "required" if required else ""
    p = urlparse(v)
    if p.scheme not in ("http", "https"):
        return "invalid"
    return ""


def settings_page() -> None:
    st.subheader(t("settings.title"))
    cfg, meta = resolve_config()

    source_msg = t("settings.source", chain=str(meta.get("sources", "db > json > env")))
    st.caption(source_msg)
    if meta.get("db_connected"):
        st.success(t("settings.db_connected"))
    else:
        st.info(t("settings.db_disconnected", reason=str(meta.get("db_error", "")) or "n/a"))

    has_lrr_key = bool(cfg.get("LRR_API_KEY", ""))
    has_openai_key = bool(cfg.get("OPENAI_API_KEY", ""))
    has_db_password = bool(cfg.get("POSTGRES_PASSWORD", ""))

    with st.form("settings_form"):
        st.markdown(f"### {t('settings.section.db')}")
        c1, c2 = st.columns([3, 1])
        db_host = c1.text_input(t("settings.pg.host"), value=cfg.get("POSTGRES_HOST", "pgvector-db"))
        db_port = c2.text_input(
            t("settings.pg.port"),
            value=_normalize_value("POSTGRES_PORT", cfg.get("POSTGRES_PORT", "5432")),
        )
        c3, c4 = st.columns(2)
        db_name = c3.text_input(t("settings.pg.db"), value=cfg.get("POSTGRES_DB", "lrr_library"))
        db_user = c4.text_input(t("settings.pg.user"), value=cfg.get("POSTGRES_USER", "postgres"))
        db_password = st.text_input(
            t("settings.pg.password"),
            value="",
            type="password",
            placeholder=t("settings.secret.keep") if has_db_password else "",
        )
        sslmode = st.selectbox(
            t("settings.pg.sslmode"),
            options=["disable", "allow", "prefer", "require", "verify-ca", "verify-full"],
            index=["disable", "allow", "prefer", "require", "verify-ca", "verify-full"].index(
                cfg.get("POSTGRES_SSLMODE", "prefer") if cfg.get("POSTGRES_SSLMODE", "prefer") in ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] else "prefer"
            ),
        )

        st.markdown(f"### {t('settings.section.urls')}")
        lrr_base = st.text_input(t("settings.lrr.base"), value=cfg.get("LRR_BASE", "http://lanraragi:3000"))
        compute_health = st.text_input(
            t("settings.compute.health"),
            value=cfg.get("COMPUTE_HEALTH_URL", "http://autoeh-compute:18080/health"),
        )
        openai_health = st.text_input(t("settings.openai.health"), value=cfg.get("OPENAI_HEALTH_URL", ""))

        st.markdown(f"### {t('settings.section.secrets')}")
        lrr_api_key = st.text_input(
            t("settings.lrr.api_key"),
            value="",
            type="password",
            placeholder=t("settings.secret.keep") if has_lrr_key else "",
        )
        openai_api_key = st.text_input(
            t("settings.openai.api_key"),
            value="",
            type="password",
            placeholder=t("settings.secret.keep") if has_openai_key else "",
        )

        st.markdown(f"### {t('settings.section.behavior')}")
        c5, c6 = st.columns(2)
        prune_not_seen = c5.checkbox(
            t("settings.text_ingest.prune"),
            value=_as_bool(cfg.get("TEXT_INGEST_PRUNE_NOT_SEEN", "1"), True),
        )
        worker_only_missing = c6.checkbox(
            t("settings.worker.only_missing"),
            value=_as_bool(cfg.get("WORKER_ONLY_MISSING", "1"), True),
        )

        c7, c8, c9 = st.columns(3)
        eh_max_pages = c7.slider(
            t("settings.eh.max_pages"),
            min_value=1,
            max_value=64,
            value=int(_normalize_value("EH_FETCH_MAX_PAGES", cfg.get("EH_FETCH_MAX_PAGES", "8"))),
            step=1,
        )
        text_batch = c8.slider(
            t("settings.text_ingest.batch"),
            min_value=100,
            max_value=5000,
            value=int(_normalize_value("TEXT_INGEST_BATCH_SIZE", cfg.get("TEXT_INGEST_BATCH_SIZE", "1000"))),
            step=100,
        )
        eh_queue_limit = c9.slider(
            t("settings.eh.queue_limit"),
            min_value=100,
            max_value=5000,
            value=int(_normalize_value("EH_QUEUE_LIMIT", cfg.get("EH_QUEUE_LIMIT", "2000"))),
            step=100,
        )

        compute_container = st.text_input(
            t("settings.compute.container"),
            value=cfg.get("COMPUTE_CONTAINER_NAME", "autoeh-compute"),
        )
        data_ui_lang = st.selectbox(
            t("settings.ui.lang"),
            options=["zh", "en"],
            index=0 if cfg.get("DATA_UI_LANG", "zh") == "zh" else 1,
            format_func=lambda x: x.upper(),
        )

        submitted = st.form_submit_button(t("settings.save"))

    if not submitted:
        return

    errs: list[str] = []
    lrr_err = _validate_url(lrr_base, required=True)
    if lrr_err:
        errs.append(t("settings.err.lrr_base"))
    compute_err = _validate_url(compute_health, required=True)
    if compute_err:
        errs.append(t("settings.err.compute_health"))
    port_txt = str(db_port or "").strip()
    if not port_txt.isdigit():
        errs.append(t("settings.err.pg_port_digits"))
        db_port_int = 5432
    else:
        db_port_int = int(port_txt)
        if db_port_int < 1 or db_port_int > 65535:
            errs.append(t("settings.err.pg_port_range"))
    openai_err = _validate_url(openai_health, required=False)
    if openai_err == "invalid":
        errs.append(t("settings.err.openai_health"))

    if errs:
        for e in errs:
            st.error(e)
        return

    new_cfg = dict(cfg)
    new_cfg["POSTGRES_HOST"] = db_host.strip()
    new_cfg["POSTGRES_PORT"] = str(db_port_int)
    new_cfg["POSTGRES_DB"] = db_name.strip()
    new_cfg["POSTGRES_USER"] = db_user.strip()
    if db_password.strip():
        new_cfg["POSTGRES_PASSWORD"] = db_password.strip()
    new_cfg["POSTGRES_SSLMODE"] = sslmode
    new_cfg["LRR_BASE"] = lrr_base.strip().rstrip("/")
    new_cfg["COMPUTE_HEALTH_URL"] = compute_health.strip()
    new_cfg["OPENAI_HEALTH_URL"] = openai_health.strip()
    if lrr_api_key.strip():
        new_cfg["LRR_API_KEY"] = lrr_api_key.strip()
    if openai_api_key.strip():
        new_cfg["OPENAI_API_KEY"] = openai_api_key.strip()
    new_cfg["TEXT_INGEST_PRUNE_NOT_SEEN"] = _str_bool(prune_not_seen)
    new_cfg["WORKER_ONLY_MISSING"] = _str_bool(worker_only_missing)
    new_cfg["EH_FETCH_MAX_PAGES"] = str(eh_max_pages)
    new_cfg["TEXT_INGEST_BATCH_SIZE"] = str(text_batch)
    new_cfg["EH_QUEUE_LIMIT"] = str(eh_queue_limit)
    new_cfg["COMPUTE_CONTAINER_NAME"] = compute_container.strip() or "autoeh-compute"
    new_cfg["DATA_UI_LANG"] = data_ui_lang.strip().lower()
    new_cfg["POSTGRES_DSN"] = _build_dsn(new_cfg)

    _save_json_config(new_cfg)
    st.success(t("settings.saved_json"))

    ok_db, db_err = _save_db_config(new_cfg.get("POSTGRES_DSN", ""), new_cfg)
    if ok_db:
        st.success(t("settings.saved_db"))
    else:
        st.warning(t("settings.saved_db_failed", reason=db_err or "n/a"))

    resolve_config(force_refresh=True)
    st.session_state.ui_lang = new_cfg.get("DATA_UI_LANG", "zh")


def audit_page() -> None:
    st.subheader(t("audit.title"))
    st.markdown(f"### {t('audit.history')}")
    rows = load_run_history(limit=300)
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df.sort_values("ts", ascending=False), width="stretch", hide_index=True)
    else:
        st.info(t("audit.no_history"))

    st.markdown(f"### {t('audit.logs')}")
    logs = sorted(TASK_LOG_DIR.glob("*.log"), reverse=True)
    pick = st.selectbox(t("audit.select_log"), options=[str(p.name) for p in logs] if logs else ["<none>"])
    if logs and pick != "<none>":
        p = TASK_LOG_DIR / pick
        txt = p.read_text(encoding="utf-8", errors="replace")
        st.text_area("log", txt[-12000:], height=320)


def xp_map_page() -> None:
    st.subheader(t("xp.title"))
    days = st.slider(t("xp.days"), min_value=3, max_value=90, value=30)
    k = st.slider(t("xp.k"), min_value=2, max_value=8, value=3)

    sql = (
        "SELECT w.arcid, w.title, w.tags "
        "FROM works w JOIN read_events r ON r.arcid = w.arcid "
        "WHERE r.read_time >= extract(epoch from now())::bigint - %s "
        "GROUP BY w.arcid, w.title, w.tags "
        "LIMIT 1000"
    )
    df = query_df(sql, (days * 86400,))
    if df.empty:
        st.warning(t("xp.no_data"))
        return

    docs = [" ".join((tags or [])) for tags in df["tags"].tolist()]
    if len(docs) < 4 or sum(len(d.strip()) > 0 for d in docs) < 4:
        st.warning(t("xp.no_tags"))
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
    fig = px.scatter(plot_df, x="x", y="y", color="cluster", hover_data=["title", "arcid"], title=t("xp.chart_title"))
    st.plotly_chart(fig, width="stretch")


def main() -> None:
    page_icon = str(LOGO_PATH) if LOGO_PATH.exists() else "🌐"
    st.set_page_config(page_title=t("app.title"), page_icon=page_icon, layout="wide")
    ensure_dirs()
    resolve_config(force_refresh=True)
    sync_scheduler()
    render_header()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            t("tab.dashboard"),
            t("tab.control"),
            t("tab.audit"),
            t("tab.xp_map"),
            t("tab.settings"),
        ]
    )
    with tab1:
        dashboard_page()
    with tab2:
        control_page()
    with tab3:
        audit_page()
    with tab4:
        xp_map_page()
    with tab5:
        settings_page()


if __name__ == "__main__":
    main()

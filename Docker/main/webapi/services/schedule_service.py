import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ..core.constants import DEFAULT_SCHEDULE, RUN_HISTORY_FILE, SCHEDULE_FILE, TASK_COMMANDS, TASK_LOG_DIR
from ..core.runtime_state import scheduler
from .config_service import apply_runtime_timezone, build_runtime_env, ensure_dirs, now_iso, _runtime_tzinfo


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


def _date_to_epoch(date_txt: str, end_of_day: bool = False) -> int | None:
    s = str(date_txt or "").strip()
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
        tz = _runtime_tzinfo()
        if end_of_day:
            dt = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=tz)
        else:
            dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        return int(dt.timestamp())
    except Exception:
        return None


def _filter_run_history(
    rows: list[dict[str, Any]],
    task: str = "",
    status: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
) -> list[dict[str, Any]]:
    task_q = str(task or "").strip().lower()
    status_q = str(status or "").strip().lower()
    kw_q = str(keyword or "").strip().lower()
    start_ep = _date_to_epoch(start_date, end_of_day=False)
    end_ep = _date_to_epoch(end_date, end_of_day=True)
    out: list[dict[str, Any]] = []
    for row in rows:
        task_val = str(row.get("task") or "").lower()
        status_val = str(row.get("status") or "").lower()
        line = json.dumps(row, ensure_ascii=False).lower()
        ts = str(row.get("ts") or "")
        try:
            row_ep = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception:
            row_ep = None
        if task_q and task_q not in task_val:
            continue
        if status_q and status_q != status_val:
            continue
        if kw_q and kw_q not in line:
            continue
        if start_ep is not None and (row_ep is None or row_ep < start_ep):
            continue
        if end_ep is not None and (row_ep is None or row_ep > end_ep):
            continue
        out.append(row)
    return out


def _minutes_to_cron(minutes: int) -> str:
    m = max(1, int(minutes))
    if m <= 59:
        return f"*/{m} * * * *"
    if m < 1440 and m % 60 == 0:
        hours = max(1, min(23, m // 60))
        return f"0 */{hours} * * *"
    if m % 1440 == 0:
        days = m // 1440
        if days <= 1:
            return "0 0 * * *"
        if days <= 31:
            return f"0 0 */{days} * *"
        return "0 0 1 * *"
    return "0 * * * *"


def _coerce_cron_expr(cron_txt: str, fallback_minutes: int = 60) -> str:
    raw = str(cron_txt or "").strip()
    if raw:
        try:
            CronTrigger.from_crontab(raw)
            return raw
        except Exception:
            m = re.match(r"\*/(\d+)\s+\*\s+\*\s+\*\s+\*", raw)
            if m:
                return _minutes_to_cron(int(m.group(1)))
    return _minutes_to_cron(fallback_minutes)


def _normalize_schedule(data: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_SCHEDULE)
    src = data if isinstance(data, dict) else {}
    for key in merged:
        item = src.get(key, {}) if isinstance(src.get(key, {}), dict) else {}
        enabled = bool(item.get("enabled", merged[key]["enabled"]))
        cron = str(item.get("cron", "")).strip()
        fallback_minutes = 60
        if "interval_minutes" in item:
            try:
                fallback_minutes = max(1, int(item.get("interval_minutes", 60)))
            except Exception:
                fallback_minutes = 60
        cron = _coerce_cron_expr(cron or merged[key]["cron"], fallback_minutes=fallback_minutes)
        merged[key] = {"enabled": enabled, "cron": cron}
    return merged


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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False, env=build_runtime_env())
        rc = int(proc.returncode)
        out = proc.stdout or ""
        err = proc.stderr or ""
        if rc != 0:
            status = "failed"
    except subprocess.TimeoutExpired as e:
        status = "timeout"
        rc = 124
        raw_out = e.stdout or ""
        raw_err = e.stderr or ""
        out = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else str(raw_out)
        err_txt = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else str(raw_err)
        err = err_txt + "\nTimeout expired"

    elapsed = round(time.time() - started, 2)

    def _task_error_hint(task: str, stderr_txt: str) -> str:
        s = str(stderr_txt or "").lower()
        if task == "eh_fetch":
            if "checkpoint" in s:
                return "Hint: EH checkpoint may be stale/corrupted; try clearing checkpoint from Control page."
            if "timeout" in s or "connection" in s or "dns" in s:
                return "Hint: EH network issue; verify EH_BASE_URL, connectivity, and cookie/user-agent settings."
            return "Hint: check EH crawler log for URL fetch/parsing errors."
        if task in {"lrr_sync", "lrr_sync_manual"}:
            if "401" in s or "403" in s or "unauthorized" in s:
                return "Hint: LRR API auth failed; verify LRR_API_KEY and LRR_BASE."
            if "timeout" in s or "connection" in s or "dns" in s or "network" in s:
                return "Hint: LRR network issue; verify LRR_BASE reachability and service status."
            if "relation" in s or "column" in s or "postgres" in s or "psycopg" in s:
                return "Hint: target pgvector schema mismatch; run latest schema.sql migrations."
            return "Hint: check LRR sync logs for API payload or DB upsert errors."
        if task == "eh_ingest":
            if "translation" in s:
                return "Hint: translation payload error; verify TAG_TRANSLATION_REPO or network to translation source."
            if "timeout" in s or "connection" in s or "dns" in s:
                return "Hint: EH network failure; verify EH network reachability and request throttle settings."
            return "Hint: check EH ingest logs for metadata fetch/title-tags parse issues."
        if task == "lrr_ingest":
            if "chat/completions" in s or "vlm" in s:
                return "Hint: VL model endpoint/config may be invalid; verify INGEST_API_BASE and INGEST_VL_MODEL."
            if "embeddings" in s or "embedding" in s:
                return "Hint: EMB model endpoint/config may be invalid; verify INGEST_API_BASE and INGEST_EMB_MODEL."
            return "Hint: check LRR ingest logs for VL/EMB service connectivity or model loading errors."
        return ""

    def _sanitize_task_log_text(task: str, text: str) -> str:
        raw = str(text or "")
        if task not in {"eh_ingest", "lrr_ingest", "eh_lrr_ingest", "lrr_sync", "lrr_sync_manual"}:
            return raw
        out_lines: list[str] = []
        for line in raw.replace("\r", "\n").splitlines():
            s = str(line or "")
            low = s.lower()
            if "siglip" in low and ("%|" in s or "it/s" in s or "█" in s):
                continue
            if "loading checkpoint shards" in low and ("%|" in s or "it/s" in s):
                continue
            out_lines.append(s)
        return "\n".join(out_lines)

    content = (
        f"[{now_iso()}] task={task_name} status={status} rc={rc} elapsed={elapsed}s\n"
        + "\n--- STDOUT ---\n"
        + _sanitize_task_log_text(task_name, out)
        + "\n--- STDERR ---\n"
        + _sanitize_task_log_text(task_name, err)
    )
    if status != "success":
        hint = _task_error_hint(task_name, err)
        if hint:
            content += "\n--- HINT ---\n" + hint + "\n"
    log_path.write_text(content, encoding="utf-8")
    out_tail = _sanitize_task_log_text(task_name, out)[-4000:]
    err_tail = _sanitize_task_log_text(task_name, err)[-4000:]
    event = {
        "task_id": str(uuid.uuid4()),
        "ts": now_iso(),
        "task": task_name,
        "status": status,
        "rc": rc,
        "elapsed_s": elapsed,
        "log_file": str(log_path),
        "stdout_tail": out_tail,
        "stderr_tail": err_tail,
        "task_summary": (out_tail + "\n" + err_tail)[-1200:],
        "hint": _task_error_hint(task_name, err),
    }
    append_run_history(event)
    return event


def load_schedule() -> dict[str, Any]:
    ensure_dirs()
    if not SCHEDULE_FILE.exists():
        save_schedule(DEFAULT_SCHEDULE)
        return dict(DEFAULT_SCHEDULE)
    try:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return _normalize_schedule(data if isinstance(data, dict) else {})


def save_schedule(data: dict[str, Any]) -> None:
    ensure_dirs()
    normalized = _normalize_schedule(data)
    SCHEDULE_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_task_command(task_name: str, args_line: str = "") -> list[str]:
    args = shlex.split(args_line or "")
    py = shlex.quote(sys.executable)
    args_q = " ".join(shlex.quote(a) for a in args)

    if task_name == "lrr_ingest":
        cmd = f"{py} -u /app/vectorIngest/worker_vl_ingest.py --dsn \"$POSTGRES_DSN\""
        if args_q:
            cmd = f"{cmd} {args_q}"
        return ["bash", "-lc", cmd]

    if task_name == "eh_ingest":
        cmd = f"{py} -u /app/vectorIngest/ingest_eh_metadata_to_pg.py --dsn \"$POSTGRES_DSN\""
        if args_q:
            cmd = f"{cmd} {args_q}"
        return ["bash", "-lc", cmd]

    if task_name == "eh_lrr_ingest":
        cmd = (
            f"{py} -u /app/vectorIngest/ingest_eh_metadata_to_pg.py --dsn \"$POSTGRES_DSN\" || true; "
            f"{py} -u /app/vectorIngest/worker_vl_ingest.py --dsn \"$POSTGRES_DSN\""
        )
        if args_q:
            cmd = f"{cmd} {args_q}"
        return ["bash", "-lc", cmd]

    if task_name in TASK_COMMANDS:
        return TASK_COMMANDS[task_name] + args
    raise ValueError(f"unsupported task: {task_name}")


def _eh_checkpoint_file() -> Path:
    configured = str(os.getenv("EH_STATE_FILE", "")).strip()
    if configured:
        return Path(configured)
    return Path("/app/ehCrawler/cache/eh_incremental_state.json")


def _clear_eh_checkpoint() -> dict[str, Any]:
    p = _eh_checkpoint_file()
    existed = bool(p.exists())
    removed = False
    size = 0
    if existed:
        try:
            size = int(p.stat().st_size)
        except Exception:
            size = 0
        try:
            p.unlink(missing_ok=True)
            removed = True
        except Exception:
            removed = False
    return {
        "ok": True,
        "path": str(p),
        "existed": existed,
        "removed": removed,
        "freed_bytes": size,
        "freed_kb": round(size / 1024, 2),
    }


def sync_scheduler() -> None:
    apply_runtime_timezone()
    runtime_tz = _runtime_tzinfo()
    cfg = load_schedule()
    desired = {k: resolve_task_command(k) for k in DEFAULT_SCHEDULE.keys()}
    existing = {j.id for j in scheduler.get_jobs()}
    for job_id, cmd in desired.items():
        setting = cfg.get(job_id, {})
        enabled = bool(setting.get("enabled", False))
        cron_expr = _coerce_cron_expr(str(setting.get("cron", "")).strip(), fallback_minutes=60)
        if enabled:
            try:
                trigger = CronTrigger.from_crontab(cron_expr, timezone=runtime_tz)
            except Exception:
                trigger = CronTrigger.from_crontab("0 * * * *", timezone=runtime_tz)
            if job_id in existing:
                scheduler.reschedule_job(job_id, trigger=trigger)
            else:
                scheduler.add_job(run_task, trigger=trigger, args=[job_id, cmd], id=job_id, replace_existing=True)
        elif job_id in existing:
            scheduler.remove_job(job_id)

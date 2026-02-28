import json
import subprocess
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..core.constants import RUN_HISTORY_FILE, TASK_LOG_DIR
from ..core.runtime_state import task_proc_lock, task_proc_state, task_state, task_state_lock
from ..core.schemas import ScheduleUpdateRequest, TaskRunRequest, TaskStopRequest
from ..services.config_service import build_runtime_env, ensure_dirs, now_iso
from ..services.db_service import db_dsn
from ..services.schedule_service import (
    _clear_eh_checkpoint,
    _filter_run_history,
    _normalize_schedule,
    append_run_history,
    load_run_history,
    load_schedule,
    resolve_task_command,
    run_task,
    save_schedule,
    sync_scheduler,
)

router = APIRouter(tags=["tasks"])


def _require_db_dsn() -> str:
    dsn = str(db_dsn() or "").strip()
    if not dsn:
        raise HTTPException(status_code=400, detail="POSTGRES_DSN is not configured")
    return dsn


def run_task_async(task_name: str, args_line: str = "") -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    started_at = now_iso()
    item = {
        "task_id": task_id,
        "task": task_name,
        "status": "running",
        "started_at": started_at,
        "updated_at": started_at,
    }
    with task_state_lock:
        task_state[task_id] = item
    with task_proc_lock:
        task_proc_state[task_id] = {"proc": None, "stop_requested": False}

    def _runner() -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = TASK_LOG_DIR / f"{task_name}_{ts}.log"
        started = time.time()
        try:
            cmd = resolve_task_command(task_name, args_line)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=build_runtime_env())
            with task_proc_lock:
                st = task_proc_state.get(task_id, {})
                st["proc"] = proc
                task_proc_state[task_id] = st

            out, err = proc.communicate()
            rc = int(proc.returncode or 0)

            with task_proc_lock:
                st = task_proc_state.get(task_id, {})
                stop_requested = bool(st.get("stop_requested"))

            status = "success" if rc == 0 else "failed"
            if stop_requested:
                status = "stopped"

            elapsed = round(time.time() - started, 2)
            content = (
                f"[{now_iso()}] task={task_name} status={status} rc={rc} elapsed={elapsed}s\n"
                + "\n--- STDOUT ---\n"
                + str(out or "")
                + "\n--- STDERR ---\n"
                + str(err or "")
            )
            if status == "stopped":
                content += "\n--- NOTE ---\nStopped by user. You can manually trigger this task again from Control page.\n"
            log_path.write_text(content, encoding="utf-8")

            event = {
                "task_id": task_id,
                "ts": now_iso(),
                "task": task_name,
                "status": status,
                "rc": rc,
                "elapsed_s": elapsed,
                "log_file": str(log_path),
                "stdout_tail": str(out or "")[-4000:],
                "stderr_tail": str(err or "")[-4000:],
                "task_summary": (str(out or "") + "\n" + str(err or ""))[-1200:],
                "hint": "You can manually trigger this task again from Control page." if status == "stopped" else "",
            }
            append_run_history(event)
            with task_state_lock:
                task_state[task_id] = {
                    **task_state[task_id],
                    "status": event.get("status", "failed"),
                    "rc": event.get("rc", 1),
                    "elapsed_s": event.get("elapsed_s", 0),
                    "log_file": event.get("log_file", ""),
                    "hint": event.get("hint", ""),
                    "task_summary": event.get("task_summary", ""),
                    "stderr_tail": event.get("stderr_tail", ""),
                    "updated_at": now_iso(),
                }
        except Exception as e:
            with task_state_lock:
                task_state[task_id] = {
                    **task_state[task_id],
                    "status": "failed",
                    "rc": 1,
                    "error": str(e),
                    "updated_at": now_iso(),
                }
        finally:
            with task_proc_lock:
                task_proc_state.pop(task_id, None)

    threading.Thread(target=_runner, daemon=True).start()
    return item


@router.get("/api/schedule")
def get_schedule() -> dict[str, Any]:
    return {"schedule": load_schedule()}


@router.put("/api/schedule")
def update_schedule(req: ScheduleUpdateRequest) -> dict[str, Any]:
    merged = _normalize_schedule(req.schedule)
    save_schedule(merged)
    sync_scheduler()
    return {"ok": True, "schedule": merged}


@router.post("/api/task/run")
def trigger_task(req: TaskRunRequest) -> dict[str, Any]:
    try:
        item = run_task_async(req.task, req.args)
        return {"ok": True, "task": item}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "traceback": traceback.format_exc()})


@router.post("/api/task/stop")
def stop_task(req: TaskStopRequest) -> dict[str, Any]:
    task_id = str(req.task_id or "").strip()
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id required")

    with task_proc_lock:
        it = task_proc_state.get(task_id)
        if not isinstance(it, dict):
            raise HTTPException(status_code=404, detail="task not running")
        it["stop_requested"] = True
        proc = it.get("proc")
        task_proc_state[task_id] = it

    if proc is not None and getattr(proc, "poll", None) and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    with task_state_lock:
        old = task_state.get(task_id)
        if old and str(old.get("status") or "") == "running":
            task_state[task_id] = {**old, "status": "stopping", "updated_at": now_iso()}
    return {"ok": True, "task_id": task_id}


@router.delete("/api/eh/checkpoint")
def clear_eh_checkpoint() -> dict[str, Any]:
    return _clear_eh_checkpoint()


@router.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    with task_state_lock:
        items = [
            {
                **it,
                "can_stop": str(it.get("status") or "") in {"running", "stopping"},
            }
            for it in task_state.values()
        ]
    items.sort(key=lambda x: str(x.get("started_at", "")), reverse=True)
    return {"tasks": items[:200]}


@router.get("/api/tasks/stream")
def stream_tasks() -> StreamingResponse:
    def event_stream():
        while True:
            with task_state_lock:
                items = [
                    {
                        **it,
                        "can_stop": str(it.get("status") or "") in {"running", "stopping"},
                    }
                    for it in task_state.values()
                ]
                payload = json.dumps({"tasks": items}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            time.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/audit/history")
def audit_history(
    limit: int = Query(default=15, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    task: str = Query(default=""),
    status: str = Query(default=""),
    keyword: str = Query(default=""),
    start_date: str = Query(default=""),
    end_date: str = Query(default=""),
) -> dict[str, Any]:
    rows = load_run_history(limit=max(2000, limit + offset + 200))
    rows = _filter_run_history(
        rows,
        task=task,
        status=status,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    rows.sort(key=lambda x: str(x.get("ts", "")), reverse=True)
    total = len(rows)
    page = rows[offset : offset + limit]
    return {"rows": page, "total": total, "offset": offset, "limit": limit}


@router.get("/api/audit/logs")
def audit_logs() -> dict[str, Any]:
    logs = sorted(TASK_LOG_DIR.glob("*.log"), reverse=True)
    return {"logs": [p.name for p in logs]}


@router.delete("/api/audit/logs")
def audit_logs_clear() -> dict[str, Any]:
    ensure_dirs()
    deleted = 0
    for p in TASK_LOG_DIR.glob("*.log"):
        try:
            p.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue
    try:
        RUN_HISTORY_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass
    return {"ok": True, "deleted": deleted}


@router.get("/api/audit/tasks")
def audit_tasks(limit: int = Query(default=5000, ge=100, le=20000)) -> dict[str, Any]:
    rows = load_run_history(limit=limit)
    names = sorted({str(r.get("task") or "").strip() for r in rows if str(r.get("task") or "").strip()})
    return {"tasks": names}


@router.get("/api/audit/logs/{name}")
def audit_log_content(name: str) -> dict[str, Any]:
    safe_name = Path(name).name
    p = TASK_LOG_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="log not found")
    txt = p.read_text(encoding="utf-8", errors="replace")
    return {"name": safe_name, "content": txt[-12000:]}


@router.get("/api/audit/logs/{name}/tail")
def audit_log_tail(
    name: str,
    offset: int = Query(default=0, ge=0),
    chunk_size: int = Query(default=8000, ge=256, le=100000),
) -> dict[str, Any]:
    safe_name = Path(name).name
    p = TASK_LOG_DIR / safe_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="log not found")
    txt = p.read_text(encoding="utf-8", errors="replace")
    total = len(txt)
    start = min(offset, total)
    end = min(start + chunk_size, total)
    return {
        "name": safe_name,
        "offset": start,
        "next_offset": end,
        "total": total,
        "chunk": txt[start:end],
        "eof": end >= total,
    }


@router.post("/api/db/works/deduplicate")
def deduplicate_works_by_arcid() -> dict[str, Any]:
    dsn = _require_db_dsn()
    sql = (
        "WITH ranked AS ("
        "SELECT ctid, row_number() OVER (PARTITION BY arcid ORDER BY COALESCE(lastreadtime, 0) DESC, ctid DESC) AS rn "
        "FROM works"
        ") "
        "DELETE FROM works w USING ranked r "
        "WHERE w.ctid = r.ctid AND r.rn > 1"
    )
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                deleted = int(cur.rowcount or 0)
            conn.commit()
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"deduplicate works failed: {e}")


@router.delete("/api/db/read-events")
def clear_read_events() -> dict[str, Any]:
    dsn = _require_db_dsn()
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM read_events")
                before = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("DELETE FROM read_events")
            conn.commit()
        return {"ok": True, "deleted": before}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"clear read_events failed: {e}")

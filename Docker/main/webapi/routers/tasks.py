import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..core.constants import RUN_HISTORY_FILE, TASK_LOG_DIR
from ..core.runtime_state import task_state, task_state_lock
from ..core.schemas import ScheduleUpdateRequest, TaskRunRequest
from ..services.config_service import ensure_dirs, now_iso
from ..services.schedule_service import (
    _clear_eh_checkpoint,
    _filter_run_history,
    _normalize_schedule,
    load_run_history,
    load_schedule,
    resolve_task_command,
    run_task,
    save_schedule,
    sync_scheduler,
)

router = APIRouter(tags=["tasks"])


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

    def _runner() -> None:
        try:
            cmd = resolve_task_command(task_name, args_line)
            event = run_task(task_name, cmd)
            with task_state_lock:
                task_state[task_id] = {
                    **task_state[task_id],
                    "status": event.get("status", "failed"),
                    "rc": event.get("rc", 1),
                    "elapsed_s": event.get("elapsed_s", 0),
                    "log_file": event.get("log_file", ""),
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
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/eh/checkpoint")
def clear_eh_checkpoint() -> dict[str, Any]:
    return _clear_eh_checkpoint()


@router.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    with task_state_lock:
        items = list(task_state.values())
    items.sort(key=lambda x: str(x.get("started_at", "")), reverse=True)
    return {"tasks": items[:200]}


@router.get("/api/tasks/stream")
def stream_tasks() -> StreamingResponse:
    def event_stream():
        while True:
            with task_state_lock:
                payload = json.dumps({"tasks": list(task_state.values())}, ensure_ascii=False)
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

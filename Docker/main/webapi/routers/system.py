from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from ..core.constants import STATIC_DIR
from ..core.runtime_state import scheduler
from ..services.auth_service import ensure_auth_schema
from ..services.config_service import apply_runtime_timezone, ensure_dirs, resolve_config
from ..services.db_service import db_dsn, query_rows
from ..services.eh_cover_embedding_service import (
    get_eh_cover_embedding_worker_status,
    start_eh_cover_embedding_worker,
    stop_eh_cover_embedding_worker,
    stop_eh_cover_embedding_worker_until_restart,
)
from ..services.schedule_service import sync_scheduler
from ..services.search_service import _item_from_work
from ..services.vision_service import warmup_siglip_model, _embed_image_siglip, siglip_warmup_ready

router = APIRouter(tags=["system"])

class ImageEmbedPayload(BaseModel):
    image: str

@router.post("/api/internal/embed/image", response_class=JSONResponse)
def embed_image_internal(payload: ImageEmbedPayload) -> JSONResponse:
    image_b64 = payload.image
    if not image_b64:
        return JSONResponse({"error": "missing image field"}, status_code=400)
    try:
        import base64
        image_bytes = base64.b64decode(image_b64)
    except Exception as e:
        return JSONResponse({"error": f"invalid base64: {e}"}, status_code=400)
    try:
        cfg, _ = resolve_config()
        model_id = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384").strip()
        vec = _embed_image_siglip(image_bytes, model_id)
    except Exception as e:
        return JSONResponse({"error": f"embedding failed: {e}"}, status_code=500)
    if not vec:
        return JSONResponse({"error": "embedding empty"}, status_code=500)
    return JSONResponse({"embedding": vec})


@router.on_event("startup")
def _on_startup() -> None:
    ensure_dirs()
    apply_runtime_timezone()
    try:
        dsn = db_dsn()
        if dsn:
            ensure_auth_schema(dsn)
    except Exception:
        pass
    if not scheduler.running:
        scheduler.start()
    sync_scheduler()
    try:
        cfg, _ = resolve_config()
        target = str(cfg.get("SIGLIP_MODEL") or "google/siglip-so400m-patch14-384")
        ready, _reason = siglip_warmup_ready(target)
        if ready:
            warmup_siglip_model(target, strict=False, silent_skip=True)
    except Exception:
        pass
    try:
        start_eh_cover_embedding_worker()
    except Exception:
        pass


@router.on_event("shutdown")
def _on_shutdown() -> None:
    stop_eh_cover_embedding_worker()
    if scheduler.running:
        scheduler.shutdown(wait=False)


@router.get("/api/visual-task/status")
def visual_task_status() -> dict[str, Any]:
    return {"ok": True, "status": get_eh_cover_embedding_worker_status()}


@router.post("/api/visual-task/stop")
def stop_visual_task() -> dict[str, Any]:
    stop_eh_cover_embedding_worker_until_restart()
    return {
        "ok": True,
        "message": "visual task stopped; restart container to restore automatic visual embedding",
    }


@router.get("/api/home/history")
def home_history(
    cursor: str = Query(default=""),
    limit: int = Query(default=24, ge=1, le=80),
) -> dict[str, Any]:
    cursor_ep = None
    cursor_arcid = ""
    if cursor:
        parts = str(cursor).split("|", 1)
        if len(parts) == 2:
            try:
                cursor_ep = int(parts[0])
                cursor_arcid = str(parts[1])
            except Exception:
                cursor_ep = None
                cursor_arcid = ""

    where = ""
    params: list[Any] = []
    if cursor_ep is not None:
        where = "WHERE (l.read_time < %s OR (l.read_time = %s AND l.arcid < %s))"
        params.extend([int(cursor_ep), int(cursor_ep), cursor_arcid])
    sql = (
        "WITH latest AS ("
        "SELECT arcid, max(read_time) AS read_time FROM read_events GROUP BY arcid"
        ") "
        "SELECT l.arcid, l.read_time, w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "FROM latest l JOIN works w ON w.arcid = l.arcid "
        f"{where} "
        "ORDER BY l.read_time DESC, l.arcid DESC LIMIT %s"
    )
    params.append(int(limit))
    rows = query_rows(sql, tuple(params))
    cfg, _ = resolve_config()
    items = [_item_from_work(r, cfg) for r in rows]
    next_cursor = ""
    if len(rows) >= int(limit):
        last = rows[-1]
        next_cursor = f"{int(last.get('read_time') or 0)}|{str(last.get('arcid') or '')}"
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "meta": {"mode": "history"},
    }


@router.get("/api/home/local")
def home_local(
    cursor: str = Query(default=""),
    limit: int = Query(default=24, ge=1, le=80),
) -> dict[str, Any]:
    cursor_ts = None
    cursor_arcid = ""
    if cursor:
        parts = str(cursor).split("|", 1)
        if len(parts) == 2:
            try:
                cursor_ts = int(parts[0])
                cursor_arcid = str(parts[1])
            except Exception:
                cursor_ts = None
                cursor_arcid = ""

    where = ""
    params: list[Any] = []
    if cursor_ts is not None:
        where = (
            "WHERE (COALESCE(w.lastreadtime, w.date_added, w.eh_posted, 0) < %s "
            "OR (COALESCE(w.lastreadtime, w.date_added, w.eh_posted, 0) = %s AND w.arcid < %s))"
        )
        params.extend([int(cursor_ts), int(cursor_ts), cursor_arcid])

    sql = (
        "SELECT w.arcid, w.title, w.tags, w.eh_posted, w.date_added, w.lastreadtime "
        "FROM works w "
        f"{where} "
        "ORDER BY COALESCE(w.lastreadtime, w.date_added, w.eh_posted, 0) DESC, w.arcid DESC LIMIT %s"
    )
    params.append(int(limit))
    rows = query_rows(sql, tuple(params))
    cfg, _ = resolve_config()
    items = [_item_from_work(r, cfg) for r in rows]
    next_cursor = ""
    if len(rows) >= int(limit):
        last = rows[-1]
        last_ts = int(last.get("lastreadtime") or last.get("date_added") or last.get("eh_posted") or 0)
        next_cursor = f"{last_ts}|{str(last.get('arcid') or '')}"
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
        "meta": {"mode": "local"},
    }


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    raise HTTPException(status_code=404, detail="frontend not built")


@router.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest() -> FileResponse:
    p = STATIC_DIR / "manifest.webmanifest"
    if p.exists():
        return FileResponse(str(p), media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest not found")


@router.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    p = STATIC_DIR / "sw.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="service worker not found")


@router.get("/workbox-{name}.js", include_in_schema=False)
def workbox_bundle(name: str) -> FileResponse:
    safe = str(name or "").strip()
    if not safe:
        raise HTTPException(status_code=404, detail="not found")
    p = STATIC_DIR / f"workbox-{safe}.js"
    if p.exists():
        return FileResponse(str(p), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="not found")


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    p = STATIC_DIR / "favicon.ico"
    if p.exists():
        return FileResponse(str(p))
    raise HTTPException(status_code=404, detail="favicon not found")


@router.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str) -> FileResponse:
    p = str(path or "").strip()
    if not p:
        return index()
    if p.startswith("api/"):
        raise HTTPException(status_code=404, detail="not found")
    candidate = STATIC_DIR / p
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate))
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    raise HTTPException(status_code=404, detail="frontend not built")

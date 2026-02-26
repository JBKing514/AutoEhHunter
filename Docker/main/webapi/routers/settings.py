import importlib
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..core.config_values import as_bool as _as_bool
from ..core.config_values import normalize_value as _normalize_value
from ..core.constants import APP_CONFIG_FILE, CONFIG_SPECS, PLUGINS_DIR, RUNTIME_DIR, TRANSLATION_DIR
from ..core.runtime_state import model_dl_lock, model_dl_state
from ..core.schemas import ConfigUpdateRequest, ProviderModelsRequest, SetupValidateDbRequest, SetupValidateLrrRequest
from ..services.ai_provider import _provider_models, check_http
from ..services.auth_service import bootstrap_status as auth_bootstrap_status
from ..services.auth_service import set_initialized
from ..services.config_service import (
    _runtime_timezone_name,
    _runtime_tzinfo,
    _save_db_config,
    _save_json_config,
    apply_runtime_timezone,
    ensure_dirs,
    now_iso,
    resolve_config,
)
from ..services.db_service import _build_dsn, db_dsn, query_rows
from ..services.dev_schema import inject_schema_sql, save_schema_upload, schema_status
from ..services.schedule_service import sync_scheduler
from ..services.search_service import _clear_thumb_cache, _thumb_cache_stats
from ..services.setup_service import validate_db_connection, validate_lrr
from ..services.vision_service import (
    _clear_runtime_pydeps,
    _clear_siglip_runtime,
    _download_siglip_worker,
    _model_status,
    _set_dl_state,
)

router = APIRouter(tags=["settings"])


def _require_developer_mode(cfg: dict[str, Any]) -> None:
    if not _as_bool(cfg.get("DATA_UI_DEVELOPER_MODE"), False):
        raise HTTPException(status_code=403, detail="developer mode is disabled")


def _load_skill_registry_snapshot() -> list[dict[str, Any]]:
    ensure_dirs()
    try:
        app_root = Path("/app")
        if app_root.exists() and str(app_root) not in sys.path:
            sys.path.insert(0, str(app_root))
        from hunterAgent.skills.loader import load_all_skills

        items = load_all_skills(str(PLUGINS_DIR))
        skills = list(items) if isinstance(items, list) else []
        has_builtin = any(bool((s or {}).get("builtin")) for s in skills)
        if has_builtin:
            return skills
        try:
            builtin_pkg = importlib.import_module("hunterAgent.skills.builtin")
            builtin_dir = Path(getattr(builtin_pkg, "__file__", "")).resolve().parent
            fallback: list[dict[str, Any]] = []
            for p in sorted(builtin_dir.glob("*_skill.py")):
                name = p.stem.removesuffix("_skill")
                if name:
                    fallback.append({"name": name, "builtin": True, "description": ""})
            if fallback:
                seen = {str((s or {}).get("name") or "").strip().lower() for s in skills}
                merged = list(skills)
                for row in fallback:
                    key = str(row.get("name") or "").strip().lower()
                    if key and key not in seen:
                        merged.append(row)
                merged.sort(key=lambda x: (0 if bool((x or {}).get("builtin")) else 1, str((x or {}).get("name") or "")))
                return merged
        except Exception:
            pass
        return skills
    except Exception:
        return []


@router.get("/api/config/schema")
def get_config_schema() -> dict[str, Any]:
    return {"schema": CONFIG_SPECS}


@router.get("/api/setup/status")
def setup_status() -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    st = auth_bootstrap_status(dsn)
    return {
        "ok": True,
        "initialized": bool(st.get("initialized")),
        "user_configured": bool(st.get("user_configured")),
    }


@router.post("/api/setup/validate-db")
def setup_validate_db(req: SetupValidateDbRequest) -> dict[str, Any]:
    ok, msg, _ = validate_db_connection(req.host, int(req.port or 5432), req.db, req.user, req.password, req.sslmode)
    return {"ok": ok, "message": msg}


@router.post("/api/setup/validate-lrr")
def setup_validate_lrr(req: SetupValidateLrrRequest) -> dict[str, Any]:
    ok, msg = validate_lrr(req.base, req.api_key)
    return {"ok": ok, "message": msg}


@router.post("/api/setup/complete")
def setup_complete() -> dict[str, Any]:
    from ..services.auth_service import generate_recovery_codes, hash_recovery_codes
    from ..services.config_service import _save_json_config, resolve_config

    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    set_initialized(dsn, True)

    codes = generate_recovery_codes(10)
    hashed = hash_recovery_codes(codes)
    cfg, _ = resolve_config()
    to_save = dict(cfg)
    to_save["DATA_UI_RECOVERY_CODES"] = ",".join(hashed)
    _save_json_config(to_save)

    return {"ok": True, "recovery_codes": codes}


@router.get("/api/health")
def health() -> dict[str, Any]:
    cfg, _ = resolve_config()
    db_ok = True
    db_error = ""
    total_works = 0
    total_eh = 0
    last_fetch = "-"
    try:
        works = query_rows("SELECT count(*) AS n FROM works")
        eh_works = query_rows("SELECT count(*) AS n FROM eh_works")
        recent = query_rows("SELECT max(last_fetched_at) AS latest FROM eh_works")
        total_works = int((works[0] or {}).get("n") or 0) if works else 0
        total_eh = int((eh_works[0] or {}).get("n") or 0) if eh_works else 0
        latest = (recent[0] or {}).get("latest") if recent else None
        if isinstance(latest, datetime):
            last_fetch = latest.astimezone(_runtime_tzinfo()).isoformat(timespec="seconds")
        else:
            last_fetch = str(latest or "-")
    except Exception as e:
        db_ok = False
        db_error = str(e)

    lrr_base = str(cfg.get("LRR_BASE", "http://lanraragi:3000")).strip().rstrip("/")
    if not urlparse(lrr_base).scheme:
        lrr_base = f"http://{lrr_base}"
    openai_health = str(cfg.get("OPENAI_HEALTH_URL", "")).strip()
    llm_base = str(cfg.get("LLM_API_BASE", "")).strip()

    ok_lrr, msg_lrr = check_http(f"{lrr_base}/api/info")
    llm = {"ok": None, "message": "n/a"}
    if openai_health:
        ok_llm, msg_llm = check_http(openai_health)
        llm = {"ok": ok_llm, "message": msg_llm}
    elif llm_base:
        models, err = _provider_models(llm_base, str(cfg.get("LLM_API_KEY", "")))
        llm = {"ok": bool(models), "message": f"models={len(models)}" if models else (err or "no models")}

    return {
        "database": {
            "ok": db_ok,
            "error": db_error,
            "works": total_works,
            "eh_works": total_eh,
            "last_fetch": last_fetch,
            "timezone": _runtime_timezone_name(),
        },
        "services": {"lrr": {"ok": ok_lrr, "message": msg_lrr}, "llm": llm},
    }


@router.post("/api/provider/models")
def provider_models(req: ProviderModelsRequest) -> dict[str, Any]:
    cfg, _ = resolve_config()
    api_key = str(req.api_key or "").strip()
    base = str(req.base_url or "").strip()
    if not api_key:
        llm_base = str(cfg.get("LLM_API_BASE", "")).strip().rstrip("/")
        ingest_base = str(cfg.get("INGEST_API_BASE", "")).strip().rstrip("/")
        norm_base = base.rstrip("/")
        if norm_base == llm_base:
            api_key = str(cfg.get("LLM_API_KEY", "")).strip()
        elif norm_base == ingest_base:
            api_key = str(cfg.get("INGEST_API_KEY", "")).strip()
    models, err = _provider_models(base, api_key)
    return {"ok": bool(models), "models": models, "error": err}


@router.get("/api/skills")
def skills_list() -> dict[str, Any]:
    skills = _load_skill_registry_snapshot()
    builtin = [s for s in skills if bool(s.get("builtin"))]
    user = [s for s in skills if not bool(s.get("builtin"))]
    files = [p.name for p in sorted(PLUGINS_DIR.glob("*.py")) if p.is_file()]
    return {"ok": True, "builtin": builtin, "user": user, "files": files}


@router.post("/api/skills/plugins")
async def skills_upload_plugin(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    name = str(file.filename or "plugin.py").strip()
    safe = Path(name).name
    if not safe.lower().endswith(".py"):
        raise HTTPException(status_code=400, detail="only .py plugin is allowed")
    if safe.startswith("__"):
        raise HTTPException(status_code=400, detail="invalid plugin filename")
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="empty plugin file")
    dst = PLUGINS_DIR / safe
    dst.write_bytes(body)
    return {"ok": True, "saved": safe, "skills": _load_skill_registry_snapshot()}


@router.get("/api/config")
def get_config() -> dict[str, Any]:
    cfg, meta = resolve_config()
    values: dict[str, Any] = {}
    secret_state: dict[str, bool] = {}
    for key, spec in CONFIG_SPECS.items():
        if spec.get("secret", False):
            values[key] = ""
            secret_state[key] = bool(str(cfg.get(key, "")).strip())
        else:
            values[key] = cfg.get(key, _normalize_value(key, spec.get("default", "")))
    return {"values": values, "secret_state": secret_state, "meta": meta}


@router.put("/api/config")
def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    cfg, _ = resolve_config()
    new_cfg = dict(cfg)
    for key, spec in CONFIG_SPECS.items():
        if key not in req.values:
            continue
        v = req.values[key]
        if spec.get("secret", False) and not str(v or "").strip():
            continue
        new_cfg[key] = _normalize_value(key, v)
    new_cfg["SIGLIP_DEVICE"] = "cpu"
    new_cfg["POSTGRES_DSN"] = _build_dsn(new_cfg)
    _save_json_config(new_cfg)
    ok_db, db_err = _save_db_config(new_cfg.get("POSTGRES_DSN", ""), new_cfg)
    apply_runtime_timezone()
    sync_scheduler()
    return {"ok": True, "saved_json": True, "saved_db": ok_db, "db_error": db_err}


@router.get("/api/config/app-config/download")
def download_app_config_json() -> FileResponse:
    ensure_dirs()
    if not APP_CONFIG_FILE.exists():
        cfg, _ = resolve_config()
        _save_json_config(cfg)
    return FileResponse(
        path=str(APP_CONFIG_FILE),
        filename="app_config.json",
        media_type="application/json",
    )


@router.post("/api/config/app-config/restore")
async def restore_app_config_json(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    name = str(file.filename or "app_config.json").strip().lower()
    if not name.endswith(".json"):
        raise HTTPException(status_code=400, detail="only .json file is allowed")
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        obj = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid json: {e}")
    if not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail="invalid app_config payload")
    if "values" in obj and not isinstance(obj.get("values"), dict):
        raise HTTPException(status_code=400, detail="invalid app_config payload: values must be object")

    APP_CONFIG_FILE.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply_runtime_timezone()
    sync_scheduler()
    return {
        "ok": True,
        "path": str(APP_CONFIG_FILE),
        "bytes": len(body),
        "updated_at": datetime.fromtimestamp(APP_CONFIG_FILE.stat().st_mtime, tz=_runtime_tzinfo()).isoformat(timespec="seconds"),
        "note": "Restored runtime app_config.json only. Database config is unchanged.",
    }


@router.get("/api/dev/schema")
def dev_schema_get_status() -> dict[str, Any]:
    cfg, _ = resolve_config()
    _require_developer_mode(cfg)
    return {"ok": True, "status": schema_status(RUNTIME_DIR)}


@router.post("/api/dev/schema/upload")
async def dev_schema_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    cfg, _ = resolve_config()
    _require_developer_mode(cfg)
    body = await file.read()
    try:
        return save_schema_upload(RUNTIME_DIR, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/dev/schema/inject")
def dev_schema_inject() -> dict[str, Any]:
    cfg, _ = resolve_config()
    _require_developer_mode(cfg)
    try:
        return inject_schema_sql(db_dsn(), RUNTIME_DIR)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"schema inject failed: {e}")


@router.get("/api/cache/thumbs")
def thumb_cache_stats_api() -> dict[str, Any]:
    return _thumb_cache_stats()


@router.delete("/api/cache/thumbs")
def thumb_cache_clear_api() -> dict[str, Any]:
    return {"ok": True, **_clear_thumb_cache()}


@router.get("/api/translation/status")
def translation_status() -> dict[str, Any]:
    ensure_dirs()
    manual = TRANSLATION_DIR / "manual_tags.json"
    manual_info = {
        "path": str(manual),
        "exists": manual.exists(),
        "size": manual.stat().st_size if manual.exists() else 0,
        "updated_at": datetime.fromtimestamp(manual.stat().st_mtime, tz=_runtime_tzinfo()).isoformat(timespec="seconds") if manual.exists() else "-",
    }
    rows = query_rows("SELECT max(last_fetched_at) as ts, max(translation_repo_url) as repo, max(translation_head_sha) as sha FROM eh_works")
    latest = rows[0] if rows else {}
    fetched = latest.get("ts")
    fetched_txt = fetched.astimezone(_runtime_tzinfo()).isoformat(timespec="seconds") if isinstance(fetched, datetime) else "-"
    return {
        "repo": str((latest or {}).get("repo") or ""),
        "head_sha": str((latest or {}).get("sha") or ""),
        "fetched_at": fetched_txt,
        "manual_file": manual_info,
    }


@router.post("/api/translation/upload")
async def translation_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    ensure_dirs()
    name = str(file.filename or "").lower()
    if not (name.endswith(".json") or name.endswith(".jsonl") or name.endswith(".txt")):
        raise HTTPException(status_code=400, detail="only json/jsonl/txt allowed")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    out = TRANSLATION_DIR / "manual_tags.json"
    out.write_bytes(data)
    return {
        "ok": True,
        "path": str(out),
        "bytes": len(data),
        "updated_at": datetime.fromtimestamp(out.stat().st_mtime, tz=_runtime_tzinfo()).isoformat(timespec="seconds"),
    }


@router.get("/api/models/status")
def models_status_api() -> dict[str, Any]:
    return {"model": _model_status(), "download": list(model_dl_state.values())[-1] if model_dl_state else None}


@router.post("/api/models/siglip/download")
def model_siglip_download(model_id: str = Query(default="google/siglip-so400m-patch14-384")) -> dict[str, Any]:
    with model_dl_lock:
        for st in model_dl_state.values():
            if str(st.get("status")) == "running":
                return {"ok": True, "task_id": st.get("task_id"), "already_running": True}
    task_id = f"siglip-{int(time.time())}"
    state = {
        "task_id": task_id,
        "model_id": str(model_id or "google/siglip-so400m-patch14-384").strip(),
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "error": "",
        "logs": [],
        "started_at": now_iso(),
    }
    _set_dl_state(task_id, state)
    th = threading.Thread(target=_download_siglip_worker, args=(task_id, state["model_id"]), daemon=True)
    th.start()
    return {"ok": True, "task_id": task_id, "status": state}


@router.get("/api/models/siglip/download/{task_id}")
def model_siglip_download_status(task_id: str) -> dict[str, Any]:
    with model_dl_lock:
        st = model_dl_state.get(str(task_id))
    if not st:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True, "status": st, "model": _model_status()}


@router.delete("/api/models/siglip")
def model_siglip_clear() -> dict[str, Any]:
    return _clear_siglip_runtime()


@router.delete("/api/models/runtime-deps")
def model_runtime_deps_clear() -> dict[str, Any]:
    return _clear_runtime_pydeps()

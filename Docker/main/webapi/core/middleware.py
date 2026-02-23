from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from .config_values import as_bool as _as_bool
from ..services.auth_service import (
    bootstrap_status as auth_bootstrap_status,
    ensure_auth_schema,
    get_session_user as auth_get_session_user,
    verify_csrf,
)
from ..services.db_service import db_dsn

AUTH_COOKIE_NAME = "aeh_session"
AUTH_CSRF_COOKIE_NAME = "aeh_csrf"
AUTH_ALLOW_PATHS = {
    "/api/auth/bootstrap",
    "/api/auth/register-admin",
    "/api/auth/login",
}


def _auth_ttl_hours(cfg: dict[str, Any] | None = None) -> int:
    src = cfg or {}
    try:
        return max(1, min(168, int(str(src.get("AUTH_SESSION_TTL_HOURS") or "24"))))
    except Exception:
        return 24


def _auth_cookie_secure(cfg: dict[str, Any] | None = None) -> bool:
    src = cfg or {}
    return _as_bool(src.get("AUTH_COOKIE_SECURE"), False)


def _auth_set_cookie(resp: Response, token: str, cfg: dict[str, Any], csrf_token: str = "") -> None:
    resp.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_auth_cookie_secure(cfg),
        samesite="lax",
        max_age=_auth_ttl_hours(cfg) * 3600,
        path="/",
    )
    if csrf_token:
        resp.set_cookie(
            key=AUTH_CSRF_COOKIE_NAME,
            value=str(csrf_token),
            httponly=False,
            secure=_auth_cookie_secure(cfg),
            samesite="lax",
            max_age=_auth_ttl_hours(cfg) * 3600,
            path="/",
        )


def _auth_clear_cookie(resp: Response, cfg: dict[str, Any]) -> None:
    resp.delete_cookie(key=AUTH_COOKIE_NAME, path="/", samesite="lax", secure=_auth_cookie_secure(cfg))
    resp.delete_cookie(key=AUTH_CSRF_COOKIE_NAME, path="/", samesite="lax", secure=_auth_cookie_secure(cfg))


async def auth_guard(request: Request, call_next):
    p = str(request.url.path or "")
    method = str(request.method or "GET").upper()
    if p.startswith("/api") and p not in AUTH_ALLOW_PATHS:
        dsn = db_dsn()
        if not dsn:
            return JSONResponse(status_code=503, content={"detail": "database is not configured"})
        try:
            ensure_auth_schema(dsn)
            st = auth_bootstrap_status(dsn)
        except Exception:
            return JSONResponse(status_code=503, content={"detail": "auth service unavailable"})
        if bool(st.get("configured")):
            token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
            if not token:
                return JSONResponse(status_code=401, content={"detail": "authentication required"})
            user = auth_get_session_user(dsn, token)
            if not user:
                return JSONResponse(status_code=401, content={"detail": "invalid session"})
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                csrf_cookie = str(request.cookies.get(AUTH_CSRF_COOKIE_NAME) or "")
                csrf_header = str(request.headers.get("x-csrf-token") or "")
                if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                    return JSONResponse(status_code=403, content={"detail": "csrf verification failed"})
                if not verify_csrf(dsn, token, csrf_header):
                    return JSONResponse(status_code=403, content={"detail": "csrf verification failed"})
            request.state.auth_user = user
    return await call_next(request)

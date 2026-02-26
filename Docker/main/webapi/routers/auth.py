from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from ..core.schemas import (
    AuthChangePasswordRequest,
    AuthDeleteAccountRequest,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthUpdateProfileRequest,
)
from ..core.middleware import AUTH_COOKIE_NAME, _auth_clear_cookie, _auth_set_cookie, _auth_ttl_hours
from ..services.auth_service import (
    _generate_recovery_token,
    auth_pepper,
    authenticate_user,
    bootstrap_status as auth_bootstrap_status,
    change_password as auth_change_password,
    check_login_rate_limit,
    check_recovery_login,
    clear_login_failures,
    create_session as auth_create_session,
    delete_account as auth_delete_account,
    force_change_password_by_username,
    get_session_user as auth_get_session_user,
    issue_recovery_csrf,
    issue_csrf_token,
    record_login_failure,
    register_first_admin,
    revoke_session as auth_revoke_session,
    update_username as auth_update_username,
)
from ..services.config_service import resolve_config
from ..services.db_service import db_dsn

router = APIRouter(tags=["auth"])


@router.get("/api/auth/bootstrap")
def auth_bootstrap(request: Request) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        return {
            "ok": True,
            "db_ready": False,
            "configured": False,
            "initialized": False,
            "user_configured": False,
            "user_count": 0,
            "is_admin_session": False,
            "setup_required": True,
        }
    try:
        st = auth_bootstrap_status(dsn)
    except Exception as e:
        return {
            "ok": True,
            "db_ready": False,
            "configured": False,
            "initialized": False,
            "user_configured": False,
            "user_count": 0,
            "is_admin_session": False,
            "setup_required": True,
            "db_error": str(e),
        }

    token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    is_admin_session = False
    if token:
        try:
            user = auth_get_session_user(dsn, token)
            role = str((user or {}).get("role") or "").lower()
            is_admin_session = role == "admin"
        except Exception:
            is_admin_session = False

    return {
        "ok": True,
        "db_ready": True,
        **st,
        "is_admin_session": is_admin_session,
        "setup_required": not bool(st.get("initialized")),
    }


@router.post("/api/auth/register-admin")
def auth_register_admin(req: AuthRegisterRequest, request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    try:
        user = register_first_admin(dsn, req.username, req.password, pepper=auth_pepper())
        cfg, _ = resolve_config()
        token, sess = auth_create_session(
            dsn,
            str(user.get("uid") or ""),
            _auth_ttl_hours(cfg),
            ip=str(request.client.host if request.client else ""),
            user_agent=str(request.headers.get("user-agent") or ""),
        )
        _auth_set_cookie(response, token, cfg, csrf_token=str(sess.get("csrf_token") or ""))
        return {"ok": True, "user": user, "session": sess}
    except PermissionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"register failed: {e}")


@router.post("/api/auth/login")
def auth_login(req: AuthLoginRequest, request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    ip = str(request.client.host if request.client else "")

    try:
        st = auth_bootstrap_status(dsn)
        if not bool(st.get("configured")):
            raise HTTPException(status_code=409, detail="admin is not configured")
        allow, wait_s = check_login_rate_limit(ip, req.username)
        if not allow:
            raise HTTPException(status_code=429, detail=f"too many failed logins, retry in {wait_s}s")
        user = authenticate_user(dsn, req.username, req.password, pepper=auth_pepper())
        if not user:
            record_login_failure(ip, req.username)
            raise HTTPException(status_code=401, detail="invalid username or password")
        clear_login_failures(ip, req.username)
        cfg, _ = resolve_config()
        token, sess = auth_create_session(
            dsn,
            str(user.get("uid") or ""),
            _auth_ttl_hours(cfg),
            ip=ip,
            user_agent=str(request.headers.get("user-agent") or ""),
        )
        _auth_set_cookie(response, token, cfg, csrf_token=str(sess.get("csrf_token") or ""))
        return {"ok": True, "user": user, "session": sess}
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if (
            "connection" in err_str
            or "operationalerror" in err_str
            or "password authentication failed" in err_str
            or "failed to resolve host" in err_str
            or "name or service not known" in err_str
        ):
            if check_recovery_login(req.password):
                cfg, _ = resolve_config()
                try:
                    token = _generate_recovery_token(pepper=auth_pepper())
                    csrf = issue_recovery_csrf(token, pepper=auth_pepper())
                except ValueError as ve:
                    raise HTTPException(status_code=503, detail=str(ve))
                _auth_set_cookie(response, token, cfg, csrf_token=csrf)
                return {
                    "ok": True,
                    "user": {
                        "uid": "recovery_uid",
                        "username": "emergency_admin",
                        "role": "recovery",
                    },
                    "session": {"sid": "recovery_session", "expires_at": "", "csrf_token": csrf},
                    "recovery_mode": True,
                }
        raise


@router.post("/api/auth/verify-password")
def auth_verify_password(req: AuthLoginRequest) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    try:
        user = authenticate_user(dsn, req.username, req.password, pepper=auth_pepper())
        if not user and not check_recovery_login(req.password):
            raise HTTPException(status_code=401, detail="invalid username or password")
    except HTTPException:
        raise
    except Exception:
        if not check_recovery_login(req.password):
            raise HTTPException(status_code=401, detail="invalid username or password")
    return {"ok": True}


@router.post("/api/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    cfg, _ = resolve_config()
    token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if dsn and token:
        try:
            auth_revoke_session(dsn, token)
        except Exception:
            pass
    _auth_clear_cookie(response, cfg)
    return {"ok": True}


@router.get("/api/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="not logged in")
    user = auth_get_session_user(dsn, token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid session")
    st = auth_bootstrap_status(dsn)
    return {"ok": True, "user": user, "initialized": bool(st.get("initialized"))}


@router.get("/api/auth/csrf")
def auth_csrf(request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="not logged in")
    user = auth_get_session_user(dsn, token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid session")
    cfg, _ = resolve_config()
    csrf_token = issue_csrf_token(dsn, token)
    _auth_set_cookie(response, token, cfg, csrf_token=csrf_token)
    return {"ok": True, "csrf_token": csrf_token}


@router.put("/api/auth/profile")
def auth_profile_update(req: AuthUpdateProfileRequest, request: Request) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    user = dict(getattr(request.state, "auth_user", {}) or {})
    uid = str(user.get("uid") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="not logged in")
    try:
        updated = auth_update_username(dsn, uid, req.username)
        return {"ok": True, "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"update profile failed: {e}")


@router.put("/api/auth/password")
def auth_password_update(req: AuthChangePasswordRequest, request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    user = dict(getattr(request.state, "auth_user", {}) or {})
    uid = str(user.get("uid") or "")
    role = str(user.get("role") or "")
    token = str(request.cookies.get(AUTH_COOKIE_NAME) or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="not logged in")
    if role != "recovery" and not uid:
        raise HTTPException(status_code=401, detail="not logged in")
    try:
        if role == "recovery":
            force_change_password_by_username(dsn, req.username, req.new_password, pepper=auth_pepper())
        else:
            auth_change_password(dsn, uid, req.old_password, req.new_password, pepper=auth_pepper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"change password failed: {e}")
    cfg, _ = resolve_config()
    _auth_clear_cookie(response, cfg)
    return {"ok": True, "message": "password changed, please login again"}


@router.delete("/api/auth/account")
def auth_account_delete(req: AuthDeleteAccountRequest, request: Request, response: Response) -> dict[str, Any]:
    dsn = db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="database is not configured")
    user = dict(getattr(request.state, "auth_user", {}) or {})
    uid = str(user.get("uid") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="not logged in")
    try:
        auth_delete_account(dsn, uid, req.password, pepper=auth_pepper())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"delete account failed: {e}")
    cfg, _ = resolve_config()
    _auth_clear_cookie(response, cfg)
    return {"ok": True}

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import psycopg
from psycopg.rows import dict_row


_RATE_LOCK = threading.Lock()
_RATE_MAP: dict[str, list[float]] = {}
_RATE_BLOCK_UNTIL: dict[str, float] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, pepper: str = "", iterations: int = 310_000) -> str:
    pwd = str(password or "")
    if len(pwd) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    payload = (pwd + str(pepper or "")).encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", payload, salt, int(iterations))
    s_salt = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    s_hash = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${int(iterations)}${s_salt}${s_hash}"


def _verify_password(password: str, encoded: str, pepper: str = "") -> bool:
    try:
        algo, iter_txt, s_salt, s_hash = str(encoded or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_txt)
        salt = base64.urlsafe_b64decode(s_salt + "==")
        expected = base64.urlsafe_b64decode(s_hash + "==")
        payload = (str(password or "") + str(pepper or "")).encode("utf-8")
        got = hashlib.pbkdf2_hmac("sha256", payload, salt, iterations)
        return hmac.compare_digest(got, expected)
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8", errors="ignore")).hexdigest()


def build_dsn(host: str, port: int, db: str, user: str, password: str, sslmode: str = "prefer") -> str:
    return (
        f"postgresql://{quote_plus(str(user or ''))}:{quote_plus(str(password or ''))}@{str(host or '').strip()}:{int(port)}/{quote_plus(str(db or ''))}"
        f"?sslmode={quote_plus(str(sslmode or 'prefer'))}"
    )


def ensure_auth_schema(dsn: str) -> None:
    create_users = (
        "CREATE TABLE IF NOT EXISTS ui_users ("
        "uid uuid PRIMARY KEY,"
        "username text NOT NULL UNIQUE,"
        "password_hash text NOT NULL,"
        "role text NOT NULL DEFAULT 'admin',"
        "created_at timestamptz NOT NULL DEFAULT now(),"
        "disabled boolean NOT NULL DEFAULT false)"
    )
    create_sessions = (
        "CREATE TABLE IF NOT EXISTS ui_sessions ("
        "sid uuid PRIMARY KEY,"
        "uid uuid NOT NULL REFERENCES ui_users(uid) ON DELETE CASCADE,"
        "token_hash text NOT NULL UNIQUE,"
        "created_at timestamptz NOT NULL DEFAULT now(),"
        "expires_at timestamptz NOT NULL,"
        "last_seen_at timestamptz NOT NULL DEFAULT now(),"
        "ip text NOT NULL DEFAULT '',"
        "user_agent text NOT NULL DEFAULT '',"
        "revoked boolean NOT NULL DEFAULT false,"
        "csrf_hash text NOT NULL DEFAULT '')"
    )
    create_meta = (
        "CREATE TABLE IF NOT EXISTS ui_meta ("
        "key text PRIMARY KEY,"
        "value text NOT NULL DEFAULT '',"
        "updated_at timestamptz NOT NULL DEFAULT now())"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(create_users)
            cur.execute(create_sessions)
            cur.execute(create_meta)
            cur.execute("ALTER TABLE ui_sessions ADD COLUMN IF NOT EXISTS csrf_hash text NOT NULL DEFAULT ''")
        conn.commit()


def _get_meta(dsn: str, key: str) -> str:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM ui_meta WHERE key=%s LIMIT 1", (str(key or ""),))
            row = cur.fetchone() or {}
    return str(row.get("value") or "")


def _set_meta(dsn: str, key: str, value: str) -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ui_meta(key,value,updated_at) VALUES (%s,%s,now()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()",
                (str(key or ""), str(value or "")),
            )
        conn.commit()


def bootstrap_status(dsn: str) -> dict[str, Any]:
    ensure_auth_schema(dsn)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*)::int AS n FROM ui_users")
            users = int((cur.fetchone() or {}).get("n") or 0)
            cur.execute("SELECT value FROM ui_meta WHERE key IN ('user_confiured','user_configured') ORDER BY updated_at DESC LIMIT 1")
            row = cur.fetchone() or {}
            configured_tag = bool(str(row.get("value") or "").strip())
            cur.execute("SELECT value FROM ui_meta WHERE key='initialized' LIMIT 1")
            row2 = cur.fetchone() or {}
            initialized = bool(str(row2.get("value") or "").strip())
    configured = bool(configured_tag or users > 0)
    return {"configured": configured, "initialized": initialized, "user_count": users}


def register_first_admin(dsn: str, username: str, password: str, pepper: str = "") -> dict[str, Any]:
    user = str(username or "").strip()
    if len(user) < 3:
        raise ValueError("username must be at least 3 characters")
    status = bootstrap_status(dsn)
    if bool(status.get("configured")):
        raise PermissionError("admin has already been configured")
    encoded = _hash_password(password, pepper=pepper)
    uid = str(uuid.uuid4())
    now = _utcnow()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ui_users(uid, username, password_hash, role, created_at) VALUES (%s,%s,%s,%s,%s)",
                (uid, user, encoded, "admin", now),
            )
            for key in ("user_confiured", "user_configured"):
                cur.execute(
                    "INSERT INTO ui_meta(key,value,updated_at) VALUES (%s,%s,now()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()",
                    (key, "1"),
                )
        conn.commit()
    return {"uid": uid, "username": user, "role": "admin", "registered_at": now.isoformat()}


def authenticate_user(dsn: str, username: str, password: str, pepper: str = "") -> dict[str, Any] | None:
    user = str(username or "").strip()
    if not user:
        return None
    ensure_auth_schema(dsn)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uid::text AS uid, username, password_hash, role, created_at, disabled FROM ui_users WHERE username=%s LIMIT 1",
                (user,),
            )
            row = cur.fetchone() or {}
    if not row or bool(row.get("disabled")):
        return None
    if not _verify_password(password, str(row.get("password_hash") or ""), pepper=pepper):
        return None
    return {
        "uid": str(row.get("uid") or ""),
        "username": str(row.get("username") or ""),
        "role": str(row.get("role") or "user"),
        "created_at": row.get("created_at"),
    }


def create_session(dsn: str, uid: str, ttl_hours: int, ip: str = "", user_agent: str = "") -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(24)
    sid = str(uuid.uuid4())
    now = _utcnow()
    expire = now.timestamp() + max(1, int(ttl_hours)) * 3600
    expires_at = datetime.fromtimestamp(expire, tz=timezone.utc)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ui_sessions(sid,uid,token_hash,created_at,expires_at,last_seen_at,ip,user_agent,revoked) VALUES (%s,%s::uuid,%s,%s,%s,%s,%s,%s,false)",
                (sid, uid, _token_hash(token), now, expires_at, now, str(ip or ""), str(user_agent or "")[:512]),
            )
            cur.execute("UPDATE ui_sessions SET csrf_hash=%s WHERE sid=%s::uuid", (_token_hash(csrf), sid))
        conn.commit()
    return token, {"sid": sid, "expires_at": expires_at.isoformat(), "csrf_token": csrf}


def get_session_user(dsn: str, token: str) -> dict[str, Any] | None:
    h = _token_hash(token)
    now = _utcnow()
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.sid::text AS sid, s.uid::text AS uid, s.expires_at, s.revoked, u.username, u.role, u.disabled "
                "FROM ui_sessions s JOIN ui_users u ON u.uid=s.uid "
                "WHERE s.token_hash=%s LIMIT 1",
                (h,),
            )
            row = cur.fetchone() or {}
            if not row:
                return None
            if bool(row.get("revoked")) or bool(row.get("disabled")):
                return None
            exp = row.get("expires_at")
            if not isinstance(exp, datetime) or exp <= now:
                return None
            cur.execute("UPDATE ui_sessions SET last_seen_at=now() WHERE sid=%s::uuid", (str(row.get("sid") or ""),))
        conn.commit()
    return {
        "sid": str(row.get("sid") or ""),
        "uid": str(row.get("uid") or ""),
        "username": str(row.get("username") or ""),
        "role": str(row.get("role") or "user"),
        "expires_at": exp.isoformat() if isinstance(exp, datetime) else "",
    }


def revoke_session(dsn: str, token: str) -> None:
    h = _token_hash(token)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE ui_sessions SET revoked=true WHERE token_hash=%s", (h,))
        conn.commit()


def issue_csrf_token(dsn: str, token: str) -> str:
    h = _token_hash(token)
    csrf = secrets.token_urlsafe(24)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE ui_sessions SET csrf_hash=%s WHERE token_hash=%s", (_token_hash(csrf), h))
        conn.commit()
    return csrf


def verify_csrf(dsn: str, token: str, csrf_token: str) -> bool:
    h = _token_hash(token)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT csrf_hash FROM ui_sessions WHERE token_hash=%s LIMIT 1", (h,))
            row = cur.fetchone() or {}
    expected = str(row.get("csrf_hash") or "")
    if not expected:
        return False
    return hmac.compare_digest(expected, _token_hash(str(csrf_token or "")))


def update_username(dsn: str, uid: str, username: str) -> dict[str, Any]:
    name = str(username or "").strip()
    if len(name) < 3:
        raise ValueError("username must be at least 3 characters")
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE ui_users SET username=%s WHERE uid=%s::uuid RETURNING uid::text AS uid, username, role, created_at", (name, uid))
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise ValueError("user not found")
    return dict(row)


def change_password(dsn: str, uid: str, old_password: str, new_password: str, pepper: str = "") -> None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM ui_users WHERE uid=%s::uuid LIMIT 1", (uid,))
            row = cur.fetchone() or {}
            old_hash = str(row.get("password_hash") or "")
            if not old_hash or not _verify_password(old_password, old_hash, pepper=pepper):
                raise ValueError("old password is invalid")
            new_hash = _hash_password(new_password, pepper=pepper)
            cur.execute("UPDATE ui_users SET password_hash=%s WHERE uid=%s::uuid", (new_hash, uid))
            cur.execute("UPDATE ui_sessions SET revoked=true WHERE uid=%s::uuid", (uid,))
        conn.commit()


def delete_account(dsn: str, uid: str, password: str, pepper: str = "") -> None:
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM ui_users WHERE uid=%s::uuid LIMIT 1", (uid,))
            row = cur.fetchone() or {}
            old_hash = str(row.get("password_hash") or "")
            if not old_hash or not _verify_password(password, old_hash, pepper=pepper):
                raise ValueError("password is invalid")
            cur.execute("DELETE FROM ui_users WHERE uid=%s::uuid", (uid,))
            cur.execute("DELETE FROM ui_sessions WHERE uid=%s::uuid", (uid,))
            _set_meta(dsn, "user_confiured", "")
            _set_meta(dsn, "user_configured", "")
            _set_meta(dsn, "initialized", "")
        conn.commit()


def set_initialized(dsn: str, value: bool = True) -> None:
    _set_meta(dsn, "initialized", "1" if bool(value) else "")


def check_login_rate_limit(ip: str, username: str, *, max_attempts: int = 5, window_s: int = 600, block_s: int = 900) -> tuple[bool, int]:
    key = f"{str(ip or '').strip()}|{str(username or '').strip().lower()}"
    now = time.time()
    with _RATE_LOCK:
        until = float(_RATE_BLOCK_UNTIL.get(key) or 0.0)
        if until > now:
            return False, int(until - now)
        arr = [x for x in (_RATE_MAP.get(key) or []) if now - x <= int(window_s)]
        _RATE_MAP[key] = arr
        if len(arr) >= int(max_attempts):
            _RATE_BLOCK_UNTIL[key] = now + int(block_s)
            return False, int(block_s)
    return True, 0


def record_login_failure(ip: str, username: str) -> None:
    key = f"{str(ip or '').strip()}|{str(username or '').strip().lower()}"
    now = time.time()
    with _RATE_LOCK:
        arr = _RATE_MAP.get(key) or []
        arr.append(now)
        _RATE_MAP[key] = arr[-20:]


def clear_login_failures(ip: str, username: str) -> None:
    key = f"{str(ip or '').strip()}|{str(username or '').strip().lower()}"
    with _RATE_LOCK:
        _RATE_MAP.pop(key, None)
        _RATE_BLOCK_UNTIL.pop(key, None)


def auth_pepper() -> str:
    return str(os.getenv("DATA_UI_AUTH_PEPPER", "")).strip()

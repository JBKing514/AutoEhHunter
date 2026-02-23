import threading
import time
from typing import Any
from urllib.parse import quote_plus, urlparse

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..core.config_values import normalize_value as _normalize_value

# ---------------------------------------------------------------------------
# resolve_config() TTL cache — avoids a DB round-trip on every query_rows()
# call.  TTL is intentionally short (5 s) so config changes propagate quickly
# while eliminating the "5-15 independent DB connections per API request"
# problem described in the architecture review.
# ---------------------------------------------------------------------------
_cfg_lock = threading.Lock()
_cfg_cache: dict[str, Any] = {"ts": 0.0, "dsn": ""}
_CFG_TTL_S: float = 5.0


def _cached_dsn() -> str:
    now = time.monotonic()
    with _cfg_lock:
        if now - _cfg_cache["ts"] < _CFG_TTL_S and _cfg_cache["dsn"]:
            return str(_cfg_cache["dsn"])
    # Import here to avoid circular imports at module load time.
    from .config_service import resolve_config

    cfg, _ = resolve_config()
    dsn = str(cfg.get("POSTGRES_DSN", "")).strip()
    with _cfg_lock:
        _cfg_cache["ts"] = time.monotonic()
        _cfg_cache["dsn"] = dsn
    return dsn


# ---------------------------------------------------------------------------
# Module-level connection pool — shared across all webapi request handlers.
# Lazy-initialised on first use so the webapi starts even when Postgres is
# temporarily unavailable.
# ---------------------------------------------------------------------------
_pool_lock = threading.Lock()
_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool | None:
    global _pool
    dsn = _cached_dsn()
    if not dsn:
        return None
    with _pool_lock:
        # Re-check under lock; another thread may have initialised it.
        if _pool is not None:
            # If the DSN changed (e.g. config was updated) recreate the pool.
            try:
                existing_dsn = _pool.conninfo
            except Exception:
                existing_dsn = ""
            if existing_dsn == dsn:
                return _pool
            # DSN changed — close old pool gracefully, replace it.
            try:
                _pool.close()
            except Exception:
                pass
            _pool = None

        try:
            _pool = ConnectionPool(
                conninfo=dsn,
                min_size=1,
                max_size=8,
                open=True,
            )
        except Exception:
            _pool = None
    return _pool


# ---------------------------------------------------------------------------
# DSN / connection string helpers (unchanged from original)
# ---------------------------------------------------------------------------


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
    out["POSTGRES_PORT"] = str(u.port or 5432)
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


def db_dsn() -> str:
    return _cached_dsn()


def query_rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    pool = _get_pool()
    if pool is not None:
        try:
            with pool.connection() as conn:
                conn.row_factory = dict_row
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    return [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            pass
    # Fallback: direct connection (e.g. pool unavailable during startup).
    dsn = _cached_dsn()
    if not dsn:
        return []
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in (cur.fetchall() or [])]

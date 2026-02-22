from __future__ import annotations

from typing import Any

import psycopg
import requests

from .auth_service import build_dsn


def validate_db_connection(host: str, port: int, db: str, user: str, password: str, sslmode: str = "prefer") -> tuple[bool, str, str]:
    dsn = build_dsn(host=host, port=port, db=db, user=user, password=password, sslmode=sslmode)
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "ok", dsn
    except Exception as e:
        return False, str(e), dsn


def validate_lrr(base: str, api_key: str, timeout_s: int = 8) -> tuple[bool, str]:
    b = str(base or "").strip().rstrip("/")
    if not b:
        return True, "empty base (optional)"
    if not b.startswith("http://") and not b.startswith("https://"):
        b = f"http://{b}"
    url = f"{b}/api/info"
    headers: dict[str, Any] = {}
    key = str(api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
        headers["X-API-Key"] = key
    try:
        r = requests.get(url, headers=headers, timeout=max(2, int(timeout_s)))
        if 200 <= int(r.status_code) < 300:
            return True, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False, str(e)

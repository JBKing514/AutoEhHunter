from __future__ import annotations

from typing import Any
from pathlib import Path

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


def init_core_schema(dsn: str, schema_path: str = "") -> tuple[bool, str]:
    s = str(dsn or "").strip()
    if not s:
        return False, "missing dsn"

    candidates: list[Path] = []
    if str(schema_path or "").strip():
        candidates.append(Path(str(schema_path).strip()))
    candidates.extend(
        [
            Path("/app/textIngest/schema.sql"),
            Path(__file__).resolve().parents[2] / "textIngest" / "schema.sql",
        ]
    )

    schema_file = next((p for p in candidates if p.exists() and p.is_file()), None)
    if not schema_file:
        return False, "schema.sql not found"

    try:
        sql = schema_file.read_text(encoding="utf-8")
        with psycopg.connect(s, connect_timeout=15) as conn:
            conn.execute("SET statement_timeout = '5min'")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        return True, "schema initialized"
    except Exception as e:
        return False, str(e)

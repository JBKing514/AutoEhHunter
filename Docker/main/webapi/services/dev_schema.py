from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg


def schema_file_path(runtime_dir: Path) -> Path:
    return runtime_dir / "dev" / "db_schema.sql"


def schema_status(runtime_dir: Path) -> dict[str, Any]:
    p = schema_file_path(runtime_dir)
    exists = bool(p.exists() and p.is_file())
    size = 0
    updated_at = ""
    if exists:
        try:
            st = p.stat()
            size = int(st.st_size)
            updated_at = datetime.fromtimestamp(float(st.st_mtime)).isoformat(timespec="seconds")
        except Exception:
            size = 0
            updated_at = ""
    return {
        "path": str(p),
        "exists": exists,
        "size_bytes": size,
        "size_kb": round(size / 1024, 2),
        "updated_at": updated_at,
    }


def save_schema_upload(runtime_dir: Path, body: bytes) -> dict[str, Any]:
    if not body:
        raise ValueError("empty schema file")
    p = schema_file_path(runtime_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    status = schema_status(runtime_dir)
    return {"ok": True, "status": status}


def inject_schema_sql(dsn: str, runtime_dir: Path) -> dict[str, Any]:
    s = str(dsn or "").strip()
    if not s:
        raise ValueError("POSTGRES_DSN is empty")
    p = schema_file_path(runtime_dir)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError("schema file not found")
    sql = p.read_text(encoding="utf-8", errors="replace").strip()
    if not sql:
        raise ValueError("schema file is empty")
    with psycopg.connect(s) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    return {"ok": True, "status": schema_status(runtime_dir)}

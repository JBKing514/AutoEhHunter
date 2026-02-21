#!/usr/bin/env bash
set -euo pipefail

# Initialize DB schema once per persisted runtime volume.
# This script is best-effort by default: it logs failures for troubleshooting
# and allows non-DB commands (like eh-fetch) to continue.

as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

DB_INIT_ON_START=${DB_INIT_ON_START:-1}
DB_INIT_FAIL_HARD=${DB_INIT_FAIL_HARD:-0}
DB_INIT_MARKER=${DB_INIT_MARKER:-/app/runtime/.db_schema_initialized}
DB_INIT_LOG=${DB_INIT_LOG:-/app/runtime/logs/db_init.log}
DB_INIT_SCHEMA=${DB_INIT_SCHEMA:-/app/textIngest/schema.sql}
DB_INIT_CONNECT_TIMEOUT=${DB_INIT_CONNECT_TIMEOUT:-15}

if ! as_bool "$DB_INIT_ON_START"; then
  exit 0
fi

mkdir -p "$(dirname "$DB_INIT_LOG")"
mkdir -p "$(dirname "$DB_INIT_MARKER")"

if [[ -f "$DB_INIT_MARKER" ]]; then
  exit 0
fi

if [[ -z "${POSTGRES_DSN:-}" ]]; then
  {
    echo "[$(date -Is)] WARN db-init skipped: POSTGRES_DSN is empty"
  } >> "$DB_INIT_LOG"
  exit 0
fi

if [[ ! -f "$DB_INIT_SCHEMA" ]]; then
  {
    echo "[$(date -Is)] ERROR db-init failed: schema file missing: $DB_INIT_SCHEMA"
  } >> "$DB_INIT_LOG"
  if as_bool "$DB_INIT_FAIL_HARD"; then
    exit 1
  fi
  exit 0
fi

export DB_INIT_SCHEMA
export DB_INIT_MARKER
export DB_INIT_LOG
export DB_INIT_CONNECT_TIMEOUT

if python - <<'PY'
import os
import re
import sys
from pathlib import Path

dsn = os.environ.get("POSTGRES_DSN", "")
schema_path = Path(os.environ["DB_INIT_SCHEMA"])
marker = Path(os.environ["DB_INIT_MARKER"])
log_path = Path(os.environ["DB_INIT_LOG"])
timeout = int(os.environ.get("DB_INIT_CONNECT_TIMEOUT", "15"))

def sanitize_dsn(raw: str) -> str:
    # postgresql://user:pass@host/db -> postgresql://user:***@host/db
    return re.sub(r":([^:@/]+)@", r":***@", raw)

def log(msg: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")

try:
    import psycopg
except Exception as e:
    log(f"[{__import__('datetime').datetime.now().isoformat()}] ERROR db-init: psycopg import failed: {e}")
    raise

safe_dsn = sanitize_dsn(dsn)
try:
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = psycopg.connect(dsn, connect_timeout=timeout)
    conn.execute("SET statement_timeout = '5min'")
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    conn.close()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("initialized\n", encoding="utf-8")
    log(f"[{__import__('datetime').datetime.now().isoformat()}] INFO db-init success: schema applied, marker={marker}")
except Exception as e:
    log(f"[{__import__('datetime').datetime.now().isoformat()}] ERROR db-init failed: dsn={safe_dsn} schema={schema_path} err={type(e).__name__}: {e}")
    raise
PY
then
  exit 0
else
  if as_bool "$DB_INIT_FAIL_HARD"; then
    exit 1
  fi
  exit 0
fi

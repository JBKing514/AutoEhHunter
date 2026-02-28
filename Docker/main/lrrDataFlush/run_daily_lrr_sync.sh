#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

SYNC_PY=${SYNC_PY:-"${SCRIPT_DIR}/sync_lrr_to_postgres.py"}
VENV_PY=${VENV_PY:-python3}

if [[ ! -f "$SYNC_PY" ]]; then
  echo "ERROR: lrr sync script not found: $SYNC_PY" >&2
  exit 1
fi

_as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

usage() {
  cat >&2 <<'EOF'
Usage: run_daily_lrr_sync.sh

Environment variables:
  POSTGRES_DSN                            required
  LRR_BASE or split vars LRR_SCHEME/LRR_HOST/LRR_PORT/LRR_BASE_PATH
  LRR_API_KEY
  LRR_SYNC_FILTER                         default: LRR_EXPORT_FILTER
  LRR_SYNC_TIMEOUT                        default: 30
  LRR_SYNC_SLEEP                          default: 0
  LRR_READS_HOURS                         default: 24
  LRR_READS_INCLUDE_TANKS                 default: 1
  LRR_SYNC_INCLUDE_LASTREAD_AS_EVENT      default: 0
  TEXT_INGEST_PRUNE_NOT_SEEN              default: 1
  TEXT_INGEST_BATCH_SIZE                  default: 1000
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

POSTGRES_DSN=${POSTGRES_DSN:-${DSN:-${PG_DSN:-}}}
if [[ -z "$POSTGRES_DSN" ]]; then
  echo "ERROR: POSTGRES_DSN is required." >&2
  exit 2
fi

LRR_BASE=${LRR_BASE:-}
LRR_HOST=${LRR_HOST:-}
LRR_PORT=${LRR_PORT:-}
LRR_SCHEME=${LRR_SCHEME:-}
LRR_BASE_PATH=${LRR_BASE_PATH:-}
LRR_API_KEY=${LRR_API_KEY:-}

if [[ -n "$LRR_BASE" ]]; then
  if PARSED=$(
    "$VENV_PY" - "$LRR_BASE" <<'PY'
import sys
from urllib.parse import urlparse

raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
u = urlparse(raw)
scheme = (u.scheme or "").strip()
host = (u.hostname or "").strip()
port = u.port
path = (u.path or "").strip()
if path == "/":
    path = ""
print(scheme)
print(host)
print(str(port or ""))
print(path)
PY
  ); then
    mapfile -t _lrr_parts <<<"$PARSED"
    _lrr_scheme=${_lrr_parts[0]:-}
    _lrr_host=${_lrr_parts[1]:-}
    _lrr_port=${_lrr_parts[2]:-}
    _lrr_path=${_lrr_parts[3]:-}
    if [[ -z "$LRR_SCHEME" && -n "$_lrr_scheme" ]]; then LRR_SCHEME=$_lrr_scheme; fi
    if [[ -z "$LRR_HOST" && -n "$_lrr_host" ]]; then LRR_HOST=$_lrr_host; fi
    if [[ -z "$LRR_PORT" && -n "$_lrr_port" ]]; then LRR_PORT=$_lrr_port; fi
    if [[ -z "$LRR_BASE_PATH" && -n "$_lrr_path" ]]; then LRR_BASE_PATH=$_lrr_path; fi
  fi
fi

LRR_SCHEME=${LRR_SCHEME:-http}
LRR_HOST=${LRR_HOST:-lanraragi}
if [[ -z "$LRR_PORT" ]]; then
  if [[ "$LRR_SCHEME" == "https" ]]; then
    LRR_PORT=443
  else
    LRR_PORT=3000
  fi
fi
LRR_BASE_PATH=${LRR_BASE_PATH:-}
if [[ -n "$LRR_BASE_PATH" && "${LRR_BASE_PATH:0:1}" != "/" ]]; then
  LRR_BASE_PATH="/${LRR_BASE_PATH}"
fi

LRR_SYNC_TIMEOUT=${LRR_SYNC_TIMEOUT:-${LRR_EXPORT_TIMEOUT:-30}}
LRR_SYNC_SLEEP=${LRR_SYNC_SLEEP:-${LRR_EXPORT_SLEEP:-0}}
LRR_SYNC_FILTER=${LRR_SYNC_FILTER:-${LRR_EXPORT_FILTER:-}}
LRR_READS_HOURS=${LRR_READS_HOURS:-24}
LRR_READS_INCLUDE_TANKS=${LRR_READS_INCLUDE_TANKS:-1}
LRR_SYNC_INCLUDE_LASTREAD_AS_EVENT=${LRR_SYNC_INCLUDE_LASTREAD_AS_EVENT:-0}
TEXT_INGEST_PRUNE_NOT_SEEN=${TEXT_INGEST_PRUNE_NOT_SEEN:-1}
TEXT_INGEST_BATCH_SIZE=${TEXT_INGEST_BATCH_SIZE:-1000}

BASE_URL="${LRR_SCHEME}://${LRR_HOST}:${LRR_PORT}${LRR_BASE_PATH}"

echo "== LRR sync run ==" >&2
echo "time:   $(date -Is)" >&2
echo "python: $VENV_PY" >&2
echo "target: $BASE_URL" >&2

ARGS=(
  --dsn "$POSTGRES_DSN"
  --base-url "$BASE_URL"
  --apikey "$LRR_API_KEY"
  --timeout "$LRR_SYNC_TIMEOUT"
  --sleep "$LRR_SYNC_SLEEP"
  --filter "$LRR_SYNC_FILTER"
  --reads-hours "$LRR_READS_HOURS"
  --batch-size "$TEXT_INGEST_BATCH_SIZE"
)

if _as_bool "$LRR_READS_INCLUDE_TANKS"; then
  ARGS+=(--include-tanks)
fi
if _as_bool "$LRR_SYNC_INCLUDE_LASTREAD_AS_EVENT"; then
  ARGS+=(--include-lastread-as-event)
fi
if _as_bool "$TEXT_INGEST_PRUNE_NOT_SEEN"; then
  ARGS+=(--prune-not-seen)
fi

exec "$VENV_PY" -u "$SYNC_PY" "${ARGS[@]}" "$@"

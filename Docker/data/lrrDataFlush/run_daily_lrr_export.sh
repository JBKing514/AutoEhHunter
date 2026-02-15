#!/usr/bin/env bash
set -euo pipefail

# Daily LANraragi export runner.
# Runs in order:
# 1) full metadata export
# 2) recent reads export

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

META_PY=${META_PY:-"${SCRIPT_DIR}/export_lrr_metadata.py"}
READS_PY=${READS_PY:-"${SCRIPT_DIR}/export_lrr_recent_reads.py"}
VENV_PY=${VENV_PY:-python3}

if [[ ! -f "$META_PY" ]]; then
  echo "ERROR: metadata export script not found: $META_PY" >&2
  exit 1
fi
if [[ ! -f "$READS_PY" ]]; then
  echo "ERROR: recent reads export script not found: $READS_PY" >&2
  exit 1
fi

_as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

LRR_HOST=${LRR_HOST:-lanraragi}
LRR_PORT=${LRR_PORT:-3000}
LRR_SCHEME=${LRR_SCHEME:-http}
LRR_BASE_PATH=${LRR_BASE_PATH:-}
LRR_API_KEY=${LRR_API_KEY:-}

LRR_METADATA_OUT=${LRR_METADATA_OUT:-/app/runtime/exports/lrr_metadata.jsonl}
LRR_METADATA_FILTER=${LRR_METADATA_FILTER:-${LRR_EXPORT_FILTER:-}}
LRR_METADATA_TIMEOUT=${LRR_METADATA_TIMEOUT:-${LRR_EXPORT_TIMEOUT:-30}}
LRR_METADATA_SLEEP=${LRR_METADATA_SLEEP:-${LRR_EXPORT_SLEEP:-0}}
LRR_METADATA_INCLUDE_RAW_TAGS=${LRR_METADATA_INCLUDE_RAW_TAGS:-${LRR_EXPORT_INCLUDE_RAW_TAGS:-0}}

LRR_READS_OUT=${LRR_READS_OUT:-/app/runtime/exports/lrr_reads_{timestamp}.jsonl}
LRR_READS_HOURS=${LRR_READS_HOURS:-24}
LRR_READS_FILTER=${LRR_READS_FILTER:-${LRR_EXPORT_FILTER:-}}
LRR_READS_TIMEOUT=${LRR_READS_TIMEOUT:-${LRR_EXPORT_TIMEOUT:-30}}
LRR_READS_SLEEP=${LRR_READS_SLEEP:-${LRR_EXPORT_SLEEP:-0}}
LRR_READS_INCLUDE_RAW_TAGS=${LRR_READS_INCLUDE_RAW_TAGS:-${LRR_EXPORT_INCLUDE_RAW_TAGS:-0}}
LRR_READS_INCLUDE_TANKS=${LRR_READS_INCLUDE_TANKS:-1}

# Ensure output parent directories exist before Python scripts write temp files.
mkdir -p "$(dirname "$LRR_METADATA_OUT")"
mkdir -p "$(dirname "$LRR_READS_OUT")"

DO_META=1
DO_READS=1

usage() {
  cat >&2 <<'EOF'
Usage: run_daily_lrr_export.sh [--meta-only|--reads-only]

Environment variables:
  LRR_HOST, LRR_PORT, LRR_SCHEME, LRR_BASE_PATH, LRR_API_KEY

Metadata stage:
  LRR_METADATA_OUT
  LRR_METADATA_FILTER
  LRR_METADATA_TIMEOUT
  LRR_METADATA_SLEEP
  LRR_METADATA_INCLUDE_RAW_TAGS

Reads stage:
  LRR_READS_OUT
  LRR_READS_HOURS
  LRR_READS_FILTER
  LRR_READS_TIMEOUT
  LRR_READS_SLEEP
  LRR_READS_INCLUDE_RAW_TAGS
  LRR_READS_INCLUDE_TANKS
EOF
}

while (( "$#" )); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --meta-only)
      DO_META=1
      DO_READS=0
      shift
      ;;
    --reads-only)
      DO_META=0
      DO_READS=1
      shift
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

echo "== LRR export run ==" >&2
echo "time:   $(date -Is)" >&2
echo "python: $VENV_PY" >&2

if _as_bool "$DO_META"; then
  META_ARGS=(
    --ip "$LRR_HOST"
    --port "$LRR_PORT"
    --scheme "$LRR_SCHEME"
    --base-path "$LRR_BASE_PATH"
    --apikey "$LRR_API_KEY"
    --out "$LRR_METADATA_OUT"
    --timeout "$LRR_METADATA_TIMEOUT"
    --sleep "$LRR_METADATA_SLEEP"
    --filter "$LRR_METADATA_FILTER"
  )
  if _as_bool "$LRR_METADATA_INCLUDE_RAW_TAGS"; then
    META_ARGS+=(--include-raw-tags)
  fi
  "$VENV_PY" -u "$META_PY" "${META_ARGS[@]}"
fi

if _as_bool "$DO_READS"; then
  READS_ARGS=(
    --ip "$LRR_HOST"
    --port "$LRR_PORT"
    --scheme "$LRR_SCHEME"
    --base-path "$LRR_BASE_PATH"
    --apikey "$LRR_API_KEY"
    --out "$LRR_READS_OUT"
    --hours "$LRR_READS_HOURS"
    --timeout "$LRR_READS_TIMEOUT"
    --sleep "$LRR_READS_SLEEP"
    --filter "$LRR_READS_FILTER"
  )
  if _as_bool "$LRR_READS_INCLUDE_RAW_TAGS"; then
    READS_ARGS+=(--include-raw-tags)
  fi
  if _as_bool "$LRR_READS_INCLUDE_TANKS"; then
    READS_ARGS+=(--include-tanks)
  fi
  "$VENV_PY" -u "$READS_PY" "${READS_ARGS[@]}"
fi

echo "LRR export flow done." >&2

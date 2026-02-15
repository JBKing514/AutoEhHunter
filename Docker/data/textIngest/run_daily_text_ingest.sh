#!/usr/bin/env bash
set -euo pipefail

# Daily text ingest runner.
# Consumes JSONL exports and writes works/read_events into Postgres.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

INGEST_PY=${INGEST_PY:-"${SCRIPT_DIR}/ingest_jsonl_to_postgres.py"}
VENV_PY=${VENV_PY:-python3}

if [[ ! -f "$INGEST_PY" ]]; then
  echo "ERROR: ingest script not found: $INGEST_PY" >&2
  exit 1
fi

_as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

POSTGRES_DSN=${POSTGRES_DSN:-${DSN:-${PG_DSN:-}}}
TEXT_INGEST_SCHEMA=${TEXT_INGEST_SCHEMA:-${DATABASE_SCHEMA:-/app/textIngest/schema.sql}}
TEXT_INGEST_INIT_SCHEMA=${TEXT_INGEST_INIT_SCHEMA:-${DATABASE_INIT_FLAGS:-0}}
TEXT_INGEST_BATCH_SIZE=${TEXT_INGEST_BATCH_SIZE:-1000}
TEXT_INGEST_SOURCE_MODE=${TEXT_INGEST_SOURCE_MODE:-basename}
TEXT_INGEST_INCLUDE_LASTREAD_AS_EVENT=${TEXT_INGEST_INCLUDE_LASTREAD_AS_EVENT:-0}
TEXT_INGEST_DRY_RUN=${TEXT_INGEST_DRY_RUN:-0}
TEXT_INGEST_PRUNE_NOT_SEEN=${TEXT_INGEST_PRUNE_NOT_SEEN:-1}
TEXT_INGEST_MIN_FULL_BYTES=${TEXT_INGEST_MIN_FULL_BYTES:-512000}

# Backward-compatible aliases.
READS_JSONL=${READS_JSONL:-}
FULL_JSONL=${FULL_JSONL:-}

# Preferred new variable: comma-separated paths.
TEXT_INGEST_INPUT=${TEXT_INGEST_INPUT:-}

usage() {
  cat >&2 <<'EOF'
Usage: run_daily_text_ingest.sh [--dry-run] [--init-schema]

Environment variables:
  POSTGRES_DSN                            required
  TEXT_INGEST_INPUT                       comma-separated JSONL paths (fallback mode)
  TEXT_INGEST_SCHEMA                      default: /app/textIngest/schema.sql
  TEXT_INGEST_INIT_SCHEMA                 default: 0
  TEXT_INGEST_BATCH_SIZE                  default: 1000
  TEXT_INGEST_SOURCE_MODE                 path|basename (default: basename)
  TEXT_INGEST_INCLUDE_LASTREAD_AS_EVENT   default: 0
  TEXT_INGEST_DRY_RUN                     default: 0
  TEXT_INGEST_PRUNE_NOT_SEEN              default: 1
  TEXT_INGEST_MIN_FULL_BYTES              default: 512000 (500KB)

Backward-compatible aliases:
  DATABASE_SCHEMA, DATABASE_INIT_FLAGS, READS_JSONL, FULL_JSONL
EOF
}

while (( "$#" )); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      TEXT_INGEST_DRY_RUN=1
      shift
      ;;
    --init-schema)
      TEXT_INGEST_INIT_SCHEMA=1
      shift
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$POSTGRES_DSN" ]]; then
  echo "ERROR: POSTGRES_DSN is required." >&2
  exit 2
fi

run_ingest() {
  local input_path=$1
  local do_prune=$2

  local args=(
    --dsn "$POSTGRES_DSN"
    --input "$input_path"
    --schema "$TEXT_INGEST_SCHEMA"
    --batch-size "$TEXT_INGEST_BATCH_SIZE"
    --source-mode "$TEXT_INGEST_SOURCE_MODE"
  )

  if _as_bool "$TEXT_INGEST_INIT_SCHEMA"; then
    args+=(--init-schema)
  fi
  if _as_bool "$TEXT_INGEST_INCLUDE_LASTREAD_AS_EVENT"; then
    args+=(--include-lastread-as-event)
  fi
  if _as_bool "$TEXT_INGEST_DRY_RUN"; then
    args+=(--dry-run)
  fi
  if _as_bool "$do_prune"; then
    args+=(--prune-not-seen)
  fi

  "$VENV_PY" -u "$INGEST_PY" "${args[@]}"
}

echo "== Text ingest run ==" >&2
echo "time:   $(date -Is)" >&2
echo "python: $VENV_PY" >&2

if [[ -n "$READS_JSONL" || -n "$FULL_JSONL" ]]; then
  if [[ -n "$READS_JSONL" ]]; then
    if [[ -f "$READS_JSONL" ]]; then
      echo "step1 reads: $READS_JSONL" >&2
      run_ingest "$READS_JSONL" 0
    else
      echo "WARN: reads file missing, skip step1: $READS_JSONL" >&2
    fi
  fi

  if [[ -z "$FULL_JSONL" ]]; then
    echo "ERROR: FULL_JSONL is required for safe prune flow." >&2
    exit 1
  fi

  if [[ ! -f "$FULL_JSONL" ]]; then
    echo "SKIP full ingest: missing file $FULL_JSONL" >&2
    exit 1
  fi

  size=$(wc -c < "$FULL_JSONL")
  min_bytes=$((TEXT_INGEST_MIN_FULL_BYTES + 0))

  if (( size <= min_bytes )); then
    echo "SKIP full ingest: $FULL_JSONL is too small (${size} bytes <= ${min_bytes})." >&2
    exit 1
  fi

  if _as_bool "$TEXT_INGEST_PRUNE_NOT_SEEN"; then
    echo "step2 full+prune: $FULL_JSONL" >&2
    run_ingest "$FULL_JSONL" 1
  else
    echo "step2 full(no prune): $FULL_JSONL" >&2
    run_ingest "$FULL_JSONL" 0
  fi

  exit 0
fi

INPUTS=()
if [[ -n "$TEXT_INGEST_INPUT" ]]; then
  IFS=',' read -r -a _parts <<< "$TEXT_INGEST_INPUT"
  for p in "${_parts[@]}"; do
    s=$(echo "$p" | xargs)
    if [[ -n "$s" ]]; then
      INPUTS+=("$s")
    fi
  done
fi

if [[ ${#INPUTS[@]} -eq 0 ]]; then
  echo "ERROR: no ingest inputs. Set FULL_JSONL/READS_JSONL or TEXT_INGEST_INPUT." >&2
  exit 2
fi

echo "fallback input mode: ${INPUTS[*]}" >&2
args=(
  --dsn "$POSTGRES_DSN"
  --input "${INPUTS[@]}"
  --schema "$TEXT_INGEST_SCHEMA"
  --batch-size "$TEXT_INGEST_BATCH_SIZE"
  --source-mode "$TEXT_INGEST_SOURCE_MODE"
)
if _as_bool "$TEXT_INGEST_INIT_SCHEMA"; then
  args+=(--init-schema)
fi
if _as_bool "$TEXT_INGEST_INCLUDE_LASTREAD_AS_EVENT"; then
  args+=(--include-lastread-as-event)
fi
if _as_bool "$TEXT_INGEST_DRY_RUN"; then
  args+=(--dry-run)
fi
if _as_bool "$TEXT_INGEST_PRUNE_NOT_SEEN"; then
  args+=(--prune-not-seen)
fi

exec "$VENV_PY" -u "$INGEST_PY" "${args[@]}"

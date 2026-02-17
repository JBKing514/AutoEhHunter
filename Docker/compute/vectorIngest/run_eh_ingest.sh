#!/usr/bin/env bash
set -euo pipefail

# Ingest queued EH gallery URLs via EH API + cover embedding into Postgres.
#
# This script does not source .env files and does not run URL fetch.
# It consumes pending URLs from PostgreSQL table `eh_queue` by default.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

INGEST_PY=${INGEST_PY:-"${SCRIPT_DIR}/ingest_eh_metadata_to_pg.py"}
if [[ ! -f "$INGEST_PY" ]]; then
  echo "ERROR: ingest script not found: $INGEST_PY" >&2
  exit 1
fi

VENV_PY=${VENV_PY:-python3}

_as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

# Ingest config
POSTGRES_DSN=${POSTGRES_DSN:-${DSN:-${PG_DSN:-}}}
EH_QUEUE_TABLE=${EH_QUEUE_TABLE:-eh_queue}
EH_QUEUE_LIMIT=${EH_QUEUE_LIMIT:-2000}
EH_QUEUE_FILE=${EH_QUEUE_FILE:-}
EH_API_URL=${EH_API_URL:-https://api.e-hentai.org/api.php}
EH_INGEST_TIMEOUT=${EH_INGEST_TIMEOUT:-45}
EH_API_BATCH_SIZE=${EH_API_BATCH_SIZE:-25}
EH_REQUEST_SLEEP=${EH_REQUEST_SLEEP:-4}
EH_USER_AGENT=${EH_USER_AGENT:-AutoEhHunter/1.0}
EH_COOKIE=${EH_COOKIE:-}
EH_SIGLIP_MODEL=${EH_SIGLIP_MODEL:-google/siglip-so400m-patch14-384}
EH_SIGLIP_DEVICE=${EH_SIGLIP_DEVICE:-${SIGLIP_DEVICE:-cpu}}
EH_TRANSLATION_URL=${EH_TRANSLATION_URL:-https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json}
EH_TRANSLATION_CACHE=${EH_TRANSLATION_CACHE:-"${SCRIPT_DIR}/cache/db.text.js"}
EH_TRANSLATION_MAX_AGE_HOURS=${EH_TRANSLATION_MAX_AGE_HOURS:-24}
EH_FORCE_REFRESH_TRANSLATION=${EH_FORCE_REFRESH_TRANSLATION:-0}
EH_SCHEMA_PATH=${EH_SCHEMA_PATH:-}
EH_INIT_SCHEMA=${EH_INIT_SCHEMA:-0}
EH_DRY_RUN=${EH_DRY_RUN:-0}

# Hard filters (optional)
EH_FILTER_CATEGORY=${EH_FILTER_CATEGORY:-}
EH_MIN_RATING=${EH_MIN_RATING:-}
EH_FILTER_TAG=${EH_FILTER_TAG:-}

usage() {
  cat >&2 <<'EOF'
Usage: run_eh_ingest.sh [--dry-run] [--init-schema] [--queue-table NAME] [--dsn DSN]

Environment variables:
  POSTGRES_DSN                 PostgreSQL DSN (required)
  DSN / PG_DSN                 Backward-compatible aliases for POSTGRES_DSN
  EH_QUEUE_TABLE               Queue table name (default: eh_queue)
  EH_QUEUE_LIMIT               Max pending rows dequeued per run (default: 2000)
  EH_QUEUE_FILE                [deprecated] file queue fallback path
  EH_API_URL                   Default: https://api.e-hentai.org/api.php
  EH_INGEST_TIMEOUT            Default: 45
  EH_API_BATCH_SIZE            Default: 25
  EH_REQUEST_SLEEP             Default: 4
  EH_USER_AGENT                Default: AutoEhHunter/1.0
  EH_COOKIE                    Optional cookie header
  EH_SIGLIP_MODEL              Default: google/siglip-so400m-patch14-384
  EH_SIGLIP_DEVICE             Default: SIGLIP_DEVICE or cpu
  EH_TRANSLATION_URL           EhTagTranslation db.text.js URL
  EH_TRANSLATION_CACHE         Default: ./cache/db.text.js
  EH_TRANSLATION_MAX_AGE_HOURS Default: 24
  EH_FORCE_REFRESH_TRANSLATION Default: 0
  EH_DRY_RUN                   Default: 0
  EH_INIT_SCHEMA               Default: 0
  EH_SCHEMA_PATH               Required only when init schema is enabled
  EH_FILTER_CATEGORY           Optional blocked categories, comma-separated
  EH_MIN_RATING                Optional minimum rating, e.g. 3.5
  EH_FILTER_TAG                Optional blocked tags, comma-separated
EOF
}

while (( "$#" )); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      EH_DRY_RUN=1
      shift
      ;;
    --init-schema)
      EH_INIT_SCHEMA=1
      shift
      ;;
    --queue-table)
      EH_QUEUE_TABLE=${2:-}
      shift 2
      ;;
    --queue-limit)
      EH_QUEUE_LIMIT=${2:-}
      shift 2
      ;;
    --queue-file)
      EH_QUEUE_FILE=${2:-}
      shift 2
      ;;
    --dsn)
      POSTGRES_DSN=${2:-}
      shift 2
      ;;
    --ingest-only)
      # Backward-compatible no-op after fetch stage removal.
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
  echo "ERROR: POSTGRES_DSN is required for EH ingest." >&2
  exit 2
fi

if _as_bool "$EH_INIT_SCHEMA" && [[ -z "$EH_SCHEMA_PATH" ]]; then
  echo "ERROR: EH_SCHEMA_PATH is required when --init-schema is enabled." >&2
  exit 2
fi

echo "== EH ingest run ==" >&2
echo "time:      $(date -Is)" >&2
echo "python:    $VENV_PY" >&2
echo "queue_table: $EH_QUEUE_TABLE" >&2
echo "queue_limit: $EH_QUEUE_LIMIT" >&2
echo "dry_run:   $EH_DRY_RUN" >&2
echo "init_schema: $EH_INIT_SCHEMA" >&2

INGEST_ARGS=(
  --dsn "$POSTGRES_DSN"
  --api-url "$EH_API_URL"
  --queue-table "$EH_QUEUE_TABLE"
  --queue-limit "$EH_QUEUE_LIMIT"
  --api-batch-size "$EH_API_BATCH_SIZE"
  --timeout "$EH_INGEST_TIMEOUT"
  --sleep-seconds "$EH_REQUEST_SLEEP"
  --user-agent "$EH_USER_AGENT"
  --siglip-model "$EH_SIGLIP_MODEL"
  --siglip-device "$EH_SIGLIP_DEVICE"
  --translation-url "$EH_TRANSLATION_URL"
  --translation-cache "$EH_TRANSLATION_CACHE"
  --translation-max-age-hours "$EH_TRANSLATION_MAX_AGE_HOURS"
)

if [[ -n "$EH_QUEUE_FILE" ]]; then
  INGEST_ARGS+=(--queue-file "$EH_QUEUE_FILE")
fi

if [[ -n "$EH_COOKIE" ]]; then
  INGEST_ARGS+=(--cookie "$EH_COOKIE")
fi
if _as_bool "$EH_FORCE_REFRESH_TRANSLATION"; then
  INGEST_ARGS+=(--force-refresh-translation)
fi
if _as_bool "$EH_INIT_SCHEMA"; then
  INGEST_ARGS+=(--init-schema)
  INGEST_ARGS+=(--schema "$EH_SCHEMA_PATH")
fi
if _as_bool "$EH_DRY_RUN"; then
  INGEST_ARGS+=(--dry-run)
fi
if [[ -n "$EH_FILTER_CATEGORY" ]]; then
  INGEST_ARGS+=(--category "$EH_FILTER_CATEGORY")
fi
if [[ -n "$EH_MIN_RATING" ]]; then
  INGEST_ARGS+=(--rating "$EH_MIN_RATING")
fi
if [[ -n "$EH_FILTER_TAG" ]]; then
  INGEST_ARGS+=(--tag "$EH_FILTER_TAG")
fi

"$VENV_PY" -u "$INGEST_PY" "${INGEST_ARGS[@]}"

echo "EH ingest flow done." >&2

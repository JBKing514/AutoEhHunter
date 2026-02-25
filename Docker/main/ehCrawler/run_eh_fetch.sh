#!/usr/bin/env bash
set -euo pipefail

# Incremental EH URL fetch runner (queue-only).
#
# This script is intended to run frequently (e.g. every 10-30 minutes)
# and append newly discovered gallery URLs into EH_QUEUE_FILE.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

FETCH_PY=${FETCH_PY:-"${SCRIPT_DIR}/fetch_new_eh_urls.py"}
if [[ ! -f "$FETCH_PY" ]]; then
  echo "ERROR: fetch script not found: $FETCH_PY" >&2
  exit 1
fi

VENV_PY=${VENV_PY:-python3}

_as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

EH_BASE_URL=${EH_BASE_URL:-https://e-hentai.org}
EH_FETCH_START_PAGE=${EH_FETCH_START_PAGE:-0}
EH_FETCH_MAX_PAGES=${EH_FETCH_MAX_PAGES:-8}
EH_FETCH_TIMEOUT=${EH_FETCH_TIMEOUT:-30}
EH_REQUEST_SLEEP=${EH_REQUEST_SLEEP:-4}
EH_SAMPLING_DENSITY=${EH_SAMPLING_DENSITY:-1}
EH_FETCH_MAX_RUN_MINUTES=${EH_FETCH_MAX_RUN_MINUTES:-0}
EH_COOKIE=${EH_COOKIE:-}
EH_USER_AGENT=${EH_USER_AGENT:-AutoEhHunter/1.0}
EH_HTTP_PROXY=${EH_HTTP_PROXY:-}
EH_HTTPS_PROXY=${EH_HTTPS_PROXY:-}
EH_STATE_FILE=${EH_STATE_FILE:-"${SCRIPT_DIR}/cache/eh_incremental_state.json"}
EH_QUEUE_FILE=${EH_QUEUE_FILE:-"${SCRIPT_DIR}/eh_gallery_queue.txt"}
EH_RESET_STATE=${EH_RESET_STATE:-0}
POSTGRES_DSN=${POSTGRES_DSN:-${DSN:-${PG_DSN:-}}}

usage() {
  cat >&2 <<'EOF'
Usage: run_eh_fetch.sh [--reset-state]

Environment variables:
  EH_BASE_URL               Default: https://e-hentai.org
  EH_FETCH_START_PAGE       Default: 0
  EH_FETCH_MAX_PAGES        Default: 8 (0 means very large hard cap)
  EH_FETCH_TIMEOUT          Default: 30
  EH_REQUEST_SLEEP          Default: 4
  EH_SAMPLING_DENSITY       Default: 1 (0..1)
  EH_FETCH_MAX_RUN_MINUTES  Default: 0 (0 means no runtime limit)
  EH_COOKIE                 Optional cookie header
  EH_USER_AGENT             Default: AutoEhHunter/1.0
  EH_HTTP_PROXY             Optional HTTP proxy for EH requests
  EH_HTTPS_PROXY            Optional HTTPS proxy for EH requests
  EH_STATE_FILE             Default: ./cache/eh_incremental_state.json
  EH_QUEUE_FILE             [deprecated] legacy queue file path
  EH_RESET_STATE            Default: 0
  POSTGRES_DSN              PostgreSQL DSN (required, writes queue into eh_queue)
EOF
}

while (( "$#" )); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --reset-state)
      EH_RESET_STATE=1
      shift
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

echo "== EH fetch run ==" >&2
echo "time:      $(date -Is)" >&2
echo "python:    $VENV_PY" >&2
echo "base_url:  $EH_BASE_URL" >&2
echo "queue:     pg.eh_queue" >&2

if [[ -z "$POSTGRES_DSN" ]]; then
  echo "ERROR: POSTGRES_DSN is required for EH fetch." >&2
  exit 2
fi

FETCH_ARGS=(
  --dsn "$POSTGRES_DSN"
  --base-url "$EH_BASE_URL"
  --start-page "$EH_FETCH_START_PAGE"
  --max-pages "$EH_FETCH_MAX_PAGES"
  --timeout "$EH_FETCH_TIMEOUT"
  --sleep-seconds "$EH_REQUEST_SLEEP"
  --sampling-density "$EH_SAMPLING_DENSITY"
  --max-run-minutes "$EH_FETCH_MAX_RUN_MINUTES"
  --user-agent "$EH_USER_AGENT"
  --state-file "$EH_STATE_FILE"
)

if [[ -n "$EH_COOKIE" ]]; then
  FETCH_ARGS+=(--cookie "$EH_COOKIE")
fi
if [[ -n "$EH_HTTP_PROXY" ]]; then
  FETCH_ARGS+=(--http-proxy "$EH_HTTP_PROXY")
fi
if [[ -n "$EH_HTTPS_PROXY" ]]; then
  FETCH_ARGS+=(--https-proxy "$EH_HTTPS_PROXY")
fi
if _as_bool "$EH_RESET_STATE"; then
  FETCH_ARGS+=(--reset-state)
fi

exec "$VENV_PY" -u "$FETCH_PY" "${FETCH_ARGS[@]}"

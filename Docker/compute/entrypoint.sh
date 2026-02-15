#!/usr/bin/env bash
set -euo pipefail

APP_HOST=${APP_HOST:-0.0.0.0}
APP_PORT=${APP_PORT:-18080}

show_help() {
  cat <<'EOF'
Usage: entrypoint.sh <command> [args...]

Commands:
  agent               Start FastAPI skill service (default)
  worker              Run vector worker (worker_vl_ingest.py)
  eh-ingest           Run EH metadata ingest to Postgres
  shell               Open bash shell

Examples:
  entrypoint.sh agent
  entrypoint.sh worker --limit 20 --only-missing
  entrypoint.sh eh-ingest --queue-file /app/runtime/eh_gallery_queue.txt
EOF
}

require_dsn() {
  if [[ -z "${POSTGRES_DSN:-}" ]]; then
    echo "ERROR: POSTGRES_DSN is required for this command." >&2
    exit 2
  fi
}

cmd=${1:-agent}
shift || true

case "$cmd" in
  -h|--help|help)
    show_help
    ;;
  agent)
    exec python -m uvicorn hunterAgent.main:app --host "$APP_HOST" --port "$APP_PORT"
    ;;
  worker)
    require_dsn
    exec python /app/vectorIngest/worker_vl_ingest.py --dsn "$POSTGRES_DSN" "$@"
    ;;
  eh-ingest)
    require_dsn
    exec python /app/vectorIngest/ingest_eh_metadata_to_pg.py --dsn "$POSTGRES_DSN" "$@"
    ;;
  shell)
    exec /bin/bash "$@"
    ;;
  *)
    echo "ERROR: unknown command: $cmd" >&2
    show_help >&2
    exit 2
    ;;
esac

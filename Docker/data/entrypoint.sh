#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage: entrypoint.sh <command> [args...]

Commands:
  eh-fetch             Run EH URL queue fetch
  lrr-export-meta      Export LANraragi metadata to JSONL
  lrr-export-reads     Export LANraragi recent reads to JSONL
  lrr-export-daily     Run metadata + recent reads export workflow
  text-ingest          Ingest JSONL into Postgres
  text-ingest-daily    Run text ingest workflow using env-configured inputs
  data-ui              Start Streamlit data web UI
  shell                Open bash shell
  help                 Show this help

Examples:
  entrypoint.sh eh-fetch
  entrypoint.sh lrr-export-meta --out /app/runtime/exports/lrr_full.jsonl
  entrypoint.sh lrr-export-reads --hours 24 --out /app/runtime/exports/lrr_reads_{timestamp}.jsonl
  entrypoint.sh lrr-export-daily
  entrypoint.sh text-ingest --input /app/runtime/exports/lrr_full.jsonl
  entrypoint.sh text-ingest-daily
  entrypoint.sh data-ui
EOF
}

require_dsn() {
  if [[ -z "${POSTGRES_DSN:-}" ]]; then
    echo "ERROR: POSTGRES_DSN is required for this command." >&2
    exit 2
  fi
}

as_bool() {
  local v
  v=$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')
  [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "y" || "$v" == "on" ]]
}

cmd=${1:-help}
shift || true

# First-start schema bootstrap (best-effort by default).
if [[ -x "/app/textIngest/init_schema_once.sh" ]]; then
  /app/textIngest/init_schema_once.sh
fi

case "$cmd" in
  -h|--help|help)
    show_help
    ;;
  eh-fetch)
    exec /app/ehCrawler/run_eh_fetch.sh "$@"
    ;;
  lrr-export-meta)
    ARGS=(
      --ip "${LRR_HOST:-lanraragi}"
      --port "${LRR_PORT:-3000}"
      --scheme "${LRR_SCHEME:-http}"
      --base-path "${LRR_BASE_PATH:-}"
      --apikey "${LRR_API_KEY:-}"
      --out "${LRR_METADATA_OUT:-/app/runtime/exports/lrr_metadata.jsonl}"
      --timeout "${LRR_METADATA_TIMEOUT:-${LRR_EXPORT_TIMEOUT:-30}}"
      --sleep "${LRR_METADATA_SLEEP:-${LRR_EXPORT_SLEEP:-0}}"
      --filter "${LRR_METADATA_FILTER:-${LRR_EXPORT_FILTER:-}}"
    )
    if as_bool "${LRR_METADATA_INCLUDE_RAW_TAGS:-${LRR_EXPORT_INCLUDE_RAW_TAGS:-0}}"; then
      ARGS+=(--include-raw-tags)
    fi
    exec python /app/lrrDataFlush/export_lrr_metadata.py \
      "${ARGS[@]}" \
      "$@"
    ;;
  lrr-export-reads)
    ARGS=(
      --ip "${LRR_HOST:-lanraragi}"
      --port "${LRR_PORT:-3000}"
      --scheme "${LRR_SCHEME:-http}"
      --base-path "${LRR_BASE_PATH:-}"
      --apikey "${LRR_API_KEY:-}"
      --out "${LRR_READS_OUT:-/app/runtime/exports/lrr_reads_{timestamp}.jsonl}"
      --hours "${LRR_READS_HOURS:-24}"
      --timeout "${LRR_READS_TIMEOUT:-${LRR_EXPORT_TIMEOUT:-30}}"
      --sleep "${LRR_READS_SLEEP:-${LRR_EXPORT_SLEEP:-0}}"
      --filter "${LRR_READS_FILTER:-${LRR_EXPORT_FILTER:-}}"
    )
    if as_bool "${LRR_READS_INCLUDE_RAW_TAGS:-${LRR_EXPORT_INCLUDE_RAW_TAGS:-0}}"; then
      ARGS+=(--include-raw-tags)
    fi
    if as_bool "${LRR_READS_INCLUDE_TANKS:-1}"; then
      ARGS+=(--include-tanks)
    fi
    exec python /app/lrrDataFlush/export_lrr_recent_reads.py \
      "${ARGS[@]}" \
      "$@"
    ;;
  lrr-export-daily)
    exec /app/lrrDataFlush/run_daily_lrr_export.sh "$@"
    ;;
  text-ingest)
    require_dsn
    exec python /app/textIngest/ingest_jsonl_to_postgres.py \
      --dsn "$POSTGRES_DSN" \
      "$@"
    ;;
  text-ingest-daily)
    exec /app/textIngest/run_daily_text_ingest.sh "$@"
    ;;
  data-ui)
    exec streamlit run /app/webui/app.py --server.address 0.0.0.0 --server.port "${DATA_UI_PORT:-8501}"
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

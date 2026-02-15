#!/usr/bin/env bash
set -euo pipefail

# Daily runner:
# - Uses process environment only (no .env sourcing)
# - Optionally runs EH ingest from an existing shared queue
# - Runs the Python worker

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

LOG_DIR=${LOG_DIR:-"/app/runtime/logs"}
mkdir -p "$LOG_DIR"

ts=$(date +%Y%m%d_%H%M%S)
log_file="$LOG_DIR/run_${ts}.log"

cleanup() {
  :
}
trap cleanup EXIT

{
  echo "== Daily run =="
  echo "time:      $(date -Is)"
  echo "env_mode:  process-environment"
  echo "log_file:  $log_file"
  echo

  if [[ "${EH_INGEST_ENABLED:-1}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
    echo "== EH ingest from existing queue =="
    echo "NOTE: URL fetch is decoupled. Queue must be produced by data-plane fetch service."
    if [[ "${DRY_RUN:-}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
      EH_DRY_RUN=1 "$SCRIPT_DIR/run_eh_ingest.sh"
    else
      "$SCRIPT_DIR/run_eh_ingest.sh"
    fi
    echo
  else
    echo "== EH incremental ingest skipped (EH_INGEST_ENABLED=${EH_INGEST_ENABLED:-0}) =="
    echo
  fi

  echo "== Run worker =="
  # Pass through any extra args to the worker runner.
  "$SCRIPT_DIR/run_worker.sh" "$@"
  echo

  echo "== Done =="
} 2>&1 | tee -a "$log_file"

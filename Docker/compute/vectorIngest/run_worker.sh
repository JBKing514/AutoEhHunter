#!/usr/bin/env bash
set -euo pipefail

# Runs worker_vl_ingest.py against Postgres + LANraragi + local llama-server endpoints.
#
# Typical usage:
#   ./scripts/start_llama_services.sh
#   ./scripts/run_worker.sh --limit 50
#
# Config is taken from environment variables (recommended) or flags.

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)

WORKER_PY=${WORKER_PY:-}
if [[ -z "$WORKER_PY" ]]; then
  if [[ -f "${REPO_ROOT}/worker_vl_ingest.py" ]]; then
    WORKER_PY="${REPO_ROOT}/worker_vl_ingest.py"
  elif [[ -f "${SCRIPT_DIR}/worker_vl_ingest.py" ]]; then
    WORKER_PY="${SCRIPT_DIR}/worker_vl_ingest.py"
  else
    echo "ERROR: worker_vl_ingest.py not found." >&2
    exit 1
  fi
fi

VENV_PY=${VENV_PY:-}
if [[ -z "$VENV_PY" ]]; then
  if [[ -x "${SCRIPT_DIR}/venv/bin/python3" ]]; then
    VENV_PY="${SCRIPT_DIR}/venv/bin/python3"
  elif [[ -x "${REPO_ROOT}/venv/bin/python3" ]]; then
    VENV_PY="${REPO_ROOT}/venv/bin/python3"
  else
    VENV_PY="python3"
  fi
fi

POSTGRES_DSN=${POSTGRES_DSN:-${DSN:-}}
LRR_BASE=${LRR_BASE:-}
LRR_API_KEY=${LRR_API_KEY:-}
VL_BASE=${VL_BASE:-http://127.0.0.1:8002}
EMB_BASE=${EMB_BASE:-http://127.0.0.1:8001}

# SigLIP GPU pinning
# NOTE: this value is a *physical* GPU index used to set CUDA_VISIBLE_DEVICES for SigLIP
# inside the worker before importing torch.
SIGLIP_CUDA_VISIBLE_DEVICES=${SIGLIP_CUDA_VISIBLE_DEVICES:-2}
SIGLIP_DEVICE=${SIGLIP_DEVICE:-cuda:0}

MODE=${MODE:-incremental}
LIMIT=${LIMIT:-}
DRY_RUN=${DRY_RUN:-}

usage() {
  cat >&2 <<'EOF'
Usage: scripts/run_worker.sh [--mode incremental|full] [--limit N] [--dry-run] [-- ...extra worker args]

Environment variables:
  POSTGRES_DSN         required, e.g. postgresql://user:pass@host:5432/lrr_library
  LRR_BASE             required, e.g. http://{your_lrr_url:port}
  LRR_API_KEY          required, LANraragi API key (raw; worker base64-encodes)
  VL_BASE              optional, default http://127.0.0.1:8002
  EMB_BASE             optional, default http://127.0.0.1:8001
  SIGLIP_CUDA_VISIBLE_DEVICES optional, default 2
  SIGLIP_DEVICE        optional, default cuda:0
  HF_TOKEN             optional, for faster HuggingFace downloads

Examples:
  POSTGRES_DSN=... LRR_BASE=... LRR_API_KEY=... scripts/run_worker.sh --limit 50
  MODE=full POSTGRES_DSN=... LRR_BASE=... LRR_API_KEY=... scripts/run_worker.sh
EOF
}

EXTRA_ARGS=()
while (( "$#" )); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --mode)
      MODE=${2:-}
      shift 2
      ;;
    --limit)
      LIMIT=${2:-}
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$POSTGRES_DSN" || -z "$LRR_BASE" || -z "$LRR_API_KEY" ]]; then
  echo "ERROR: POSTGRES_DSN, LRR_BASE, and LRR_API_KEY are required." >&2
  usage
  exit 2
fi

WORKER_ARGS=(
  --dsn "$POSTGRES_DSN"
  --lrr-base "$LRR_BASE"
  --lrr-api-key "$LRR_API_KEY"
  --vl-base "$VL_BASE"
  --emb-base "$EMB_BASE"
  --siglip-cuda-visible-devices "$SIGLIP_CUDA_VISIBLE_DEVICES"
  --siglip-device "$SIGLIP_DEVICE"
)

if [[ -n "$LIMIT" ]]; then
  WORKER_ARGS+=(--limit "$LIMIT")
fi

if [[ -n "$DRY_RUN" ]]; then
  WORKER_ARGS+=(--dry-run)
fi

case "$MODE" in
  incremental)
    WORKER_ARGS+=(--only-missing)
    ;;
  full)
    # Do not add --only-missing
    ;;
  *)
    echo "ERROR: Invalid MODE: $MODE (expected incremental|full)" >&2
    exit 2
    ;;
esac

echo "== Worker run ==" >&2
echo "time:    $(date -Is)" >&2
echo "python:  $VENV_PY" >&2
echo "worker:  $WORKER_PY" >&2
echo "mode:    $MODE" >&2
echo "vl:      $VL_BASE" >&2
echo "emb:     $EMB_BASE" >&2
echo "siglip:  CUDA_VISIBLE_DEVICES=$SIGLIP_CUDA_VISIBLE_DEVICES device=$SIGLIP_DEVICE" >&2
echo "limit:   ${LIMIT:-<none>}" >&2
echo "dry_run: ${DRY_RUN:-0}" >&2

exec "$VENV_PY" -u "$WORKER_PY" "${WORKER_ARGS[@]}" "${EXTRA_ARGS[@]}"

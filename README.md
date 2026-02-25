# Data Container

This image packages data-plane scripts:

- `ehCrawler/fetch_new_eh_urls.py` (queue fetch)
- `lrrDataFlush/export_lrr_metadata.py`
- `lrrDataFlush/export_lrr_recent_reads.py`
- `lrrDataFlush/run_daily_lrr_export.sh`
- `textIngest/ingest_jsonl_to_postgres.py`
- `textIngest/run_daily_text_ingest.sh`
- `webapi/main.py` (FastAPI backend for Data UI)
- `webapp/` (Vue frontend for Data UI)

## 1) Prepare env

No directory rename is required (`main` -> `data` is obsolete). The build now uses `Docker/main` directly.

```bash
cp Docker/main/.env.example Docker/.env
# edit Docker/.env
```

## 2) Build image

```bash
docker build -t autoeh-data:local -f Docker/main/Dockerfile Docker
```

If your host does not support `docker compose`, create a reusable data container with plain Docker:

```bash
docker run -d \
  --name autoeh-data \
  --restart unless-stopped \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local shell -lc "sleep infinity"
```

Then run jobs via `docker exec`, for example:

```bash
docker exec -it autoeh-data /app/ehCrawler/run_eh_fetch.sh
docker exec -it autoeh-data /app/lrrDataFlush/run_daily_lrr_export.sh
docker exec -it autoeh-data /app/textIngest/run_daily_text_ingest.sh
```

Run Data UI from the same image:

```bash
docker run -d \
  --name autoeh-data-ui \
  --restart unless-stopped \
  --env-file Docker/.env \
  -p 8501:8501 \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  autoeh-data:local data-ui
```

`data-ui` can trigger compute scripts (`run_worker.sh`, `run_eh_ingest.sh`, `run_daily.sh`) via `docker exec`,
so Docker socket mount is required and `COMPUTE_CONTAINER_NAME` must match your compute container.

## 3) Run commands

Fetch EH URLs into PostgreSQL queue table (`eh_queue`):

```bash
docker run --rm \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local eh-fetch
```

Export LANraragi metadata:

```bash
docker run --rm \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local lrr-export-meta
```

Run daily LRR export workflow (metadata -> recent reads):

```bash
docker run --rm \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local lrr-export-daily
```

Ingest JSONL into Postgres:

```bash
docker run --rm \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local text-ingest --input /app/runtime/exports/lrr_metadata.jsonl --init-schema --schema /app/textIngest/schema.sql
```

Run daily text ingest workflow (reads env-configured input list):

```bash
docker run --rm \
  --env-file Docker/.env \
  -v "$(pwd)/Docker/runtime:/app/runtime" \
  autoeh-data:local text-ingest-daily
```

Safety guard in `text-ingest-daily`:

- Default `TEXT_INGEST_PRUNE_NOT_SEEN=1`.
- Prune is only applied in full-ingest step when `FULL_JSONL` exists and file size is greater than `TEXT_INGEST_MIN_FULL_BYTES` (default 500KB).
- If full snapshot is missing or too small, the script exits with error to avoid accidental mass deletion.

## Notes

- EH URL handoff now uses PostgreSQL table `eh_queue`; no cross-container shared queue directory is required.
- `n8nWorkflows` is intentionally excluded from this container and distributed via `Companion`.
- On first container start, schema bootstrap runs once from `/app/textIngest/schema.sql`.
- If DB is unreachable, details are written to `/app/runtime/logs/db_init.log` for troubleshooting.
- Data UI supports online configuration (`Settings` tab): save and apply immediately without redeploying containers.
- Recommended workflow: fill `.env` before first start for baseline stability, then tune configs in WebUI later.
- Secrets/tokens are stored in `app_config` with reversible encryption. If encryption key is lost, re-enter secrets in WebUI and save once to regenerate/re-distribute key material.

# Compute Container

This image merges the compute-side components into one runtime:

- `hunterAgent` FastAPI skill service (`/skill/search`, `/skill/recommendation`, ...)
- `vectorIngest/worker_vl_ingest.py`
- `vectorIngest/ingest_eh_metadata_to_pg.py`

## 1) Prepare env

```bash
cp compute/.env.example compute/.env
# edit compute/.env
```

## 2) Build + start skill API

```bash
docker compose -f compute_docker-compose.yml up -d --build
```

If your host does not support `docker compose`, use plain Docker commands:

```bash
docker build -t autoeh-compute:local -f compute/Dockerfile .

docker run -d \
  --name autoeh-compute \
  --restart unless-stopped \
  --env-file compute/.env \
  -p 18080:18080 \
  -v "$(pwd)/compute/runtime:/app/runtime" \
  -v "$(pwd)/compute/hf_cache:/root/.cache/huggingface" \
  -v "$(pwd)/compute/eh_ingest_cache:/app/runtime/eh_ingest_cache" \
  autoeh-compute:local agent
```

Health check:

```bash
curl http://127.0.0.1:18080/health
```

## 3) One-shot commands

Run vector worker:

```bash
docker compose -f compute_docker-compose.yml run --rm compute worker --limit 20 --only-missing
```

Ingest EH metadata from queue:

```bash
docker compose -f compute_docker-compose.yml run --rm compute eh-ingest --queue-file /app/runtime/eh_gallery_queue.txt
```

Open shell:

```bash
docker compose -f compute_docker-compose.yml run --rm compute shell
```

## Notes

- The container defaults to `command: ["agent"]`; keep it for always-on API service.
- One-shot jobs reuse the same `.env`, so there is only one config surface for compute side.
- `./compute/runtime` is used for runtime logs/state/media cache.
- `./compute/eh_ingest_cache` is the shared queue directory for cross-container EH URL handoff.

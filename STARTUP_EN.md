# AutoEhHunter Quick Start

> 🌐 Language / 语言: [English](STARTUP_EN.md) | [中文](STARTUP.md)

## 0. Prerequisites

- Docker Desktop / Docker Engine (recommended 27+)
- (Optional) an OpenAI-compatible `/v1` model endpoint

## 1. Quick Template (Recommended)

```bash
git clone https://github.com/JBKing514/AutoEhHunter.git
cd AutoEhHunter
docker compose -f Docker/quick_deploy_docker-compose.yml up -d
```

Quick template starts:

- `pg17` (PostgreSQL + pgvector)
- `lanraragi`
- `data-ui` (WebUI + API + scheduler + chat)

> `.env` editing is no longer mandatory before first boot. Configure from WebUI after startup.

## 2. Manual Step-by-Step Templates (Optional)

If you want finer control, launch components separately:

1. PostgreSQL

```bash
docker compose -f Docker/pg17_docker-compose.yml up -d
```

2. LANraragi

```bash
docker compose -f Docker/lanraragi_docker-compose.yml up -d
```

3. Data service

```bash
docker compose -f Docker/main_docker-compose.yml up -d
```

## 3. First WebUI Setup

- Open: `http://<host>:8501`
- In `Settings`, configure:
  - PostgreSQL / LANraragi
  - `INGEST_API_BASE` + models (optional)
  - `LLM_API_BASE` + models (optional)

## 4. First Initialization Order

On `Control` page, run in order:

1. `EH Fetch`
2. `LRR Export`
3. `Text Ingest`
4. `LRR Ingest`
5. `EH Ingest` (optional)

For daily operation, schedule `EH+LRR Ingest`.

## 5. Model Endpoint Notes

- **Single endpoint mode**: one `/v1` for VL/Embedding/LLM.
- **Split endpoint mode**:
  - `INGEST_API_BASE` (ingestion)
  - `LLM_API_BASE` (chat + narrative)
- **No LLM still works**: baseline retrieval/ingestion works; NL-enhanced features are limited.

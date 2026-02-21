# AutoEhHunter Quick Start Guide

> 🌐 Language / 语言: [English](STARTUP_EN.md) | [中文](STARTUP.md)

## 0. Prerequisites

* **Docker**: Docker Desktop / Docker Engine (v27+ recommended)
* **OpenAI-compatible backend (optional)**: any `/v1` endpoint (LM Studio / vLLM / compatible Ollama proxy, etc.)
* **Note**: LLM connectivity is optional; baseline pipeline still works without it.

## 1. Basic Steps

1. **Clone the repo**
   ```bash
   git clone https://github.com/JBKing514/AutoEhHunter.git
   cd AutoEhHunter
   ```

2. **Start with quick template (recommended)**
   ```bash
   docker compose -f Docker/quick_deploy_docker-compose.yml up -d
   ```

   This starts: `pg17`, `lanraragi`, `data-ui`.

3. **Open WebUI**
   * Visit `http://<host>:8501`
   * Configure PostgreSQL/LRR and model endpoints in `Settings`

## 2. Manual Step-by-Step Deployment (Optional)

If you want split startup or cross-host deployment:

1. PostgreSQL
   ```bash
   docker compose -f Docker/pg17_docker-compose.yml up -d
   ```

2. LANraragi
   ```bash
   docker compose -f Docker/lanraragi_docker-compose.yml up -d
   ```

3. Data UI / API
   ```bash
   docker compose -f Docker/main_docker-compose.yml up -d
   ```

## 3. First Initialization (Important)

On the `Control` page, run in order:

1. `[EH Fetch]`
2. `[LRR Export]`
3. `[Text Ingest]`
4. `[LRR Ingest]`
5. `[EH Ingest]` (optional)

> For daily operation, schedule `EH+LRR Ingest`.

## 4. Model Endpoint Strategy

* **Single endpoint mode**: one `/v1` for VL + Embedding + LLM
* **Split endpoint mode**:
  * `INGEST_API_BASE` for ingestion (VL/Embedding)
  * `LLM_API_BASE` for chat/narrative (can use larger model)
* **Without LLM**: baseline retrieval/data pipeline works; NL narrative features are limited.

## 5. Runtime Suggestions

* EH fetch: every 10~30 minutes
* Ingest: once per day (shorten if backlog grows)
* CPU-only works by default; first full ingest can be slower

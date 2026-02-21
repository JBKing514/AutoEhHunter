# AutoEhHunter

> 🌐 Language / 语言: [English](README_EN.md) | [中文](README.md)

Private multimodal retrieval workspace for E-Hentai + LANraragi (Data-Only primary architecture).

## Current State

- Core path is consolidated into the `data` container (WebUI + API + scheduler + chat routing).
- `compute` / `n8n` are no longer required for baseline operation.
- You can start containers first, then configure everything from WebUI Settings.
- Supports either:
  - single `/v1` endpoint for VL + Embedding + LLM
  - split ingest/chat endpoints

## Architecture (English)

```mermaid
flowchart TB

 subgraph Sources["Sources"]
    direction LR
    EH(("E-Hentai API"))
    LRR_Local[("LANraragi Library")]
    Mihon("Mihon APP")
    LRR_Pluggin["Enhanced Metadata Plugin"]
 end

 subgraph DataPlane["Data Plane"]
    direction TB
    UI["Data WebUI + FastAPI"]
    Crawler["Funnel Crawler / Metadata Sync"]
    Extractor["Image/Text Extraction + Ingest Jobs"]
    Agent["Session Gateway + Intent Router + Skills"]
    Plugins["User Plugins (/runtime/webui/plugins)"]
 end

 subgraph ModelEndpoints["Model Endpoints (Optional)"]
    direction TB
    IngestEP["INGEST_API_BASE (/v1)\nVL + Embedding"]
    LlmEP["LLM_API_BASE (/v1)\nChat + Narrative"]
 end

 subgraph Storage["Storage"]
    PG[("PostgreSQL + pgvector")]
 end

 EH -- "URL + Metadata" --> Crawler
 LRR_Local -- "API export / archive read" --> Crawler
 Crawler --> Extractor
 Extractor --> PG

 Extractor -- "optional call" --> IngestEP
 Agent -- "optional call" --> LlmEP

 Agent <--> PG
 UI <--> Agent
 UI <--> Crawler

 Mihon -- "reading history" --> LRR_Local
 LRR_Pluggin -- "EH metadata enhancement" --> LRR_Local
 Plugins --> Agent

 classDef storage fill:#3f3f3f,stroke:#fff,stroke-width:2px,color:#fff
 classDef external fill:#2b2b2b,stroke:#666,stroke-width:2px,color:#fff,stroke-dasharray: 5 5
 classDef data fill:#003366,stroke:#4682B4,stroke-width:2px,color:#fff
 classDef model fill:#4B0082,stroke:#9370DB,stroke-width:2px,color:#fff

 class EH,LRR_Local,Mihon,LRR_Pluggin external
 class UI,Crawler,Extractor,Agent,Plugins data
 class IngestEP,LlmEP model
 class PG storage
```

## Deployment Modes

### 1) Quick Template (one command)

Use `Docker/quick_deploy_docker-compose.yml`:

```bash
docker compose -f Docker/quick_deploy_docker-compose.yml up -d
```

This template launches: `pg17 + lanraragi + data-ui`.

### 2) Manual Templates (step-by-step)

- PostgreSQL: `Docker/pg17_docker-compose.yml`
- LANraragi: `Docker/lanraragi_docker-compose.yml`
- Data service: `Docker/main_docker-compose.yml`

You can start them separately (e.g. run model endpoints on another machine), then point addresses/models in Settings.

## Model Connectivity Strategy

- Single endpoint mode: one `/v1` for ingest + chat.
- Split endpoint mode:
  - `INGEST_API_BASE`: cheaper/faster model stack for VL+embedding
  - `LLM_API_BASE`: larger model stack for chat/NLG
- Without LLM config: baseline retrieval and ingest still work; NL search/report narratives are disabled.

## Docs

- [Quick Start](STARTUP_EN.md)
- [快速启动（中文）](STARTUP.md)
- [Contribution Guide](CONTRIBUTING_EN.md)
- [贡献指南（中文）](CONTRIBUTING.md)

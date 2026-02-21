# AutoEhHunter

> 🌐 Language / 语言: [English](README_EN.md) | [中文](README.md)

### Private Multimodal RAG Retrieval System for E-Hentai and LANraragi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

<p align="center">
  <img src="https://github.com/JBKing514/autoEhHunter/blob/main/Media/ico/AutoEhHunterLogo_256.png" width="256" alt="AutoEhHunter_Ico">
  <br>
  <em>AutoEhHunter</em>
</p>

## Motivation

**"I remember the cover and plot vibe, but still can't find that work because I forgot the exact tag/title."**

AutoEhHunter is built to move from rigid keyword search to semantic + visual retrieval.

## Overview

AutoEhHunter now uses the **Data container** as the primary entry point for:

- EH/LRR sync and metadata cleaning
- SigLIP vector ingestion
- Text / image / hybrid retrieval
- Chat routing, skills, and plugin extension

## Architecture

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

## Core Features

### 1. Multimodal Retrieval
* Visual search (image to vectors)
* Text search with fuzzy tag mapping
* Hybrid search with multi-channel weighting

### 2. Data Pipeline
* EH funnel crawling + LRR export
* Optional metadata enhancement and translation
* Scheduled ingestion jobs

### 3. Recommendation / Profile
* XP clustering and preference estimation
* Tunable strictness and Tag/Visual weights

### 4. Chat + Skills
* Auto/manual intents: chat/profile/search/report/recommendation
* Built-in skills + runtime plugin loading

## Requirements

### `data-ui` container (primary)
* WebUI + FastAPI + scheduler + chat gateway
* CPU-only default is supported

### External model endpoints (optional)
* OpenAI-compatible `/v1`
* Single endpoint for VL/Embedding/LLM, or split ingest/chat endpoints

## Getting Started

* [Quick Start](STARTUP_EN.md)
* [中文启动指南](STARTUP.md)
* [Contribution Guide](CONTRIBUTING_EN.md)

## Config & Persistence

- Priority: `app_config(DB) > JSON fallback > .env`
- You can start first and configure from Settings later
- Without LLM config, baseline features still work

## Tech Stack

* PostgreSQL 17 + pgvector
* FastAPI + Vue 3
* SigLIP (CPU-only default)
* OpenAI-compatible `/v1` endpoints

## Disclaimer

For personal retrieval research and archiving only. Follow site ToS and local regulations.

# AutoEhHunter

> 🌐 Language / 语言: [English](README_EN.md) | [中文](README.md)

### Private Multimodal RAG Agent for E-Hentai and LANraragi

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/) [![Architecture](https://img.shields.io/badge/Architecture-Split%20Plane-purple)](docs/ARCHITECTURE.md)

<p align="center">
  <img src="https://github.com/JBKing514/autoEhHunter/blob/main/Media/ico/AutoEhHunterLogo_256.png" width="256" alt="AutoEhHunter_Ico">
  <br>
  <em>AutoEhHunter</em>
</p>

## Motivation

**"Why do I remember what the cover looks like, and remember the plot, but can't find that book because I can't remember that damn Tag / Title?"**

AutoEhHunter was born out of deep frustration with the existing search mechanisms of E-Hentai and LANraragi. Traditional keyword and boolean logic-based retrieval systems are inherently anti-human—they require users to think like a database, having to hit metadata precisely to get feedback.

But human desire is fuzzy, emotional, and visually dominant.

My original intention in developing **AutoEhHunter** was to break this cognitive barrier. I wanted to build a system that doesn't make me "search for Tags", but understands when I say "find something with this feeling" or "I want to watch something heavy recently". It shouldn't just be a cold archiving tool, but a **tactical adjutant** that can understand images, read plots, and understand my XP better than I do.

## Overview

**AutoEhHunter** is an autonomous cognitive agent running as a **Private RAG (Retrieval-Augmented Generation) System**. It treats your local library and external EH database as a high-dimensional vector space, using **SigLIP** for visual understanding and cooperating with **LLM Agents** for semantic reasoning, transforming passive "browsing" into active, intelligent "tactical interaction".

> **"Stop Searching. Start Aligning."**

## Architecture

<p align="center">
  <img src="/Media/diagram/AutoEhHunter_Diagram_EN.png" width="800" alt="AutoEhHunter_Diagram_EN">
  <br>
  <em>AutoEhHunter Architecture Diagram</em>
</p>

The system adopts a **Split-Plane Architecture**, decoupling heavy computation from persistent storage.

| Plane | Component | Responsibility | Tech Stack |
| :--- | :--- | :--- | :--- |
| **Control** | **Agent** | Intent recognition, persona rendering, workflow orchestration. | **n8n**, Telegram Bot API, LLM |
| **Cortex** | **Compute** | Visual embedding (SigLIP), vector index construction, XP cluster analysis. | **PyTorch**, SigLIP, Scikit-learn, VL Visual Model |
| **Logistics** | **Data** | Funnel crawler, metadata cleaning, persistent storage. | **PostgreSQL** (pgvector), LANraragi |

## Core Features

### 1. Multimodal Semantic Retrieval
* **Visual Search**: Upload an image, and the system finds works with similar composition, style, or features based on SigLIP.
* **Hybrid Query**: Supports complex natural language instructions, such as "find some works with a style like a certain artist but with a pure love plot".
* **Shadow Library**: Before downloading, you can call the crawler to crawl external E-Hentai and perform deep vector retrieval after ingestion.

### 2. Ecological Closed Loop and Data Engineering
AutoEhHunter is not just a searcher, but a complete set of data governance solutions:
* **Funnel Crawler**:
    * Adopts a funnel mechanism of "lightweight metadata crawling -> rule filtering -> compute ingestion".
    * Only calls GPU compute for works matching your Rating/Tag preferences, greatly reducing computational load.
* **Mihon Customized LANraragi Plugin**:
    * Modified Mihon (Tachiyomi) extension, supports calling LANraragi API to report reading records.
    * Whether reading on PC or mobile, your XP behavior data will flow back to the system for correcting recommendation algorithms.
* **Enhanced Ehentai.pm Plugin**:
    * Deeply modified LANraragi built-in plugin, supports extracting metadata from multiple sources such as `metadata`, `comicinfo.xml`, `ehviewer`.
    * Built-in EH API fallback mechanism and **Chinese tag automatic translation**, ensuring metadata consistency and readability.

### 3. XP Clustering Driven Recommendation Mechanism
* **XP Map**: Visualize your reading history as a 2D projection of high-dimensional clusters.
* **Drift Detection**: The Agent monitors your reading habits and generates reports analyzing your preference evolution.
* **Smart Interception**: Uses K-Means clustering to lock your "strike zone" vector, automatically intercepting newly uploaded resources that are mathematically aligned with your taste.

### 4. Tactical Adjutant (Agent)
* **Narrative Report**: Reject boring JSON. Get daily/weekly reports written by a "Cyber Adjutant", with a sharp and to-the-point style.
* **Context Awareness**: Able to understand the difference between "help me find a specific book" and "I'm bored, recommend something".

## Container Specifications and Requirements

This project adopts a microservice design, allowing you to deploy flexibly according to hardware conditions.

### `data` Container (Logistics Plane)
* **Positioning**: Always running, responsible for crawler, database, and Web UI.
* **Resource Requirements**: Extremely low. Can run stably with `RAM < 512MB`.
* **Image Size**: Approx `1.1GB`.
* **Suggested Deployment**: NAS, Raspberry Pi, or low-power server.

### `compute` Container (Cortex Plane)
* **Positioning**: On-demand or always running, responsible for SigLIP visual embedding and vector calculation.
* **CPU Mode**:
    * Default compatibility mode.
    * **Recommended**: `8` core CPU or above, otherwise vector ingestion and image search speed will be significantly slower.
* **GPU Acceleration (Optional)**:
    * Supports CUDA acceleration, need to handle PyTorch version compatibility yourself.
    * **Special Note**: For NVIDIA **RTX 50 Series / Blackwell** architecture graphics cards, you usually need to manually install the latest PyTorch Nightly version and explicitly enable GPU in environment variables.
* **Image Size**: Approx `8.0GB` (including PyTorch and pre-trained models).

## Model Architecture and Configuration Strategy

AutoEhHunter adopts a **"Specialized Models"** strategy to balance performance and VRAM overhead. Although the project supports any OpenAI-compatible backend, to ensure database Schema compatibility and the best experience, please follow the configuration specifications below.

> **⚠️ About Content Safety**:
> Given the nature of the data processed by this project (containing a large amount of NSFW content), standard commercial models or overly aligned models may frequently trigger refusal mechanisms.
> **Strongly recommended** to use locally deployed **Abliterated** or **Uncensored** version models to ensure the stability of visual description and role-playing functions.

### 1. Text Embedding Model - **Mandatory**
* **Designated Model**: `BAAI/bge-m3`
* **Hard Constraint**: **Must use this model** (or a similar model with an output dimension of `1024`).
* **Reason**: The `desc_embedding` field in the database Schema is hardcoded as `vector(1024)`.
    * *Counterexample*: If you use OpenAI `text-embedding-3-small` (1536 dim) or `bge-large` (1024 dim), please verify the dimensions match, otherwise ingestion will report an error.
    * `bge-m3` has SOTA-level performance in multilingual (CJK) semantic retrieval, perfectly fitting the multilingual environment of EH.

### 2. Vision-Language Model (VLM) - **Mandatory**
* **Usage**: Generate high-quality "natural language descriptions" for images in the local library, used to supplement semantics that Tags cannot cover (such as "composition", "atmosphere", "plot speculation").
* **Recommended Configuration**:
    * **Balanced (Dev Environment Benchmark)**: `Huihui-Qwen3-VL-8B-Instruct-abliterated` (or other Qwen2.5/3-VL derivatives).
        * *Features*: Fast speed, accurate description, and after Abliteration processing, it will not avoid describing sensitive images.
    * **High Performance**: `Qwen2.5-VL-72B` or `Llama-3.2-90B-Vision`.
        * *Features*: Provides more literary and detailed descriptions, suitable for users pursuing extreme retrieval accuracy.
    * **All-in-One**: The control plane large model (such as 30B+ VLM) can also serve this role, but prompts need to be fine-tuned to prevent the model from hallucinating or diverging too much when describing.

### 3. Control Plane Large Model (Agent LLM) - **Core**
* **Usage**: Intent Recognition (Router) and Final Narrative Rendering (NLG).
* **Recommended Configuration**:
    * **Best Experience**: `Qwen3-Next-80B-A3B-Instruct` (Quantization chosen during development: IQ4_XS).
        * **Specialized Adaptation**: The Prompts of this project are deeply tuned for the instruction following ability and Chinese language sense of the Qwen series.
        * **Immersion**: 80B-level large parameter models can provide a "Tactical Adjutant" role-playing experience far beyond small models.
        * **Actual Performance**: In development testing, the native Instruct version of this model has extremely high compliance with System Prompt and **rarely refuses users' sensitive requests**, so usually there is no need to find a specialized Abliterated version to get stable output.
    * **Minimum Requirement**: `7B` or above parameter Instruct/Chat model.
        * *Warning*: Models that are too small may not be able to strictly follow the JSON output format, causing intent recognition failure and falling back to the default keyword search mode. Thinking models are not supported yet, and currently Skill cannot extract Context fields.

---

### Prompt Engineering & Localization

The core logic of this project's Agent (Intent Recognition and Narrative Rendering) relies deeply on **Prompt Engineering**. The current prompt library has the following limitations:

* **Benchmark Model Binding**: All System Prompts are fine-tuned for the instruction following paradigm and Attention preference of **`Qwen3-Next-80B-A3B-Instruct`**.
    * **Risk**: When using other model architectures (such as Llama-3, DeepSeek) or smaller parameter models, **JSON output format errors** (causing Router crash) or **Role-playing style collapse** (infinite repetition) may occur.
* **Language Adaptation**: The current version is deeply optimized only for the **Simplified Chinese** environment.
    * Instructions in other languages (English, Japanese) may be misunderstood by the model, or cause mixed Chinese and English in the reply.
    * **n8n Hardcoding**: Some Fallback Responses in the n8n workflow are currently hardcoded in Simplified Chinese and urgently need localization (i18n) transformation.

#### Contribution Guide
We warmly welcome community contributions for Prompt adaptation schemes for other mainstream models (such as `Llama-3.1-70B`, `DeepSeek-V3`) or multilingual environments (English/Japanese).

If you intend to submit a PR, please be sure to refer to the **[Prompt Examples]** in [**CONTRIBUTING_EN.md**](CONTRIBUTING_EN.md).
* **Hard Metric**: Any Prompt modification must pass the **JSON Structure Stability Test** of `Intent Classifier`, ensuring that it can output standard JSON conforming to Schema 100% of the time at `temperature=0` to ensure the robustness of the system's core functions.

---

## Getting Started

AutoEhHunter is designed for Docker environments.

* **[Quick Start Guide (STARTUP_EN.md)](STARTUP_EN.md)** - *Deploy your private Agent in 5 minutes*
* **[Data Container Detailed Configuration Reference](Docker/data/README.md)** - *Advanced Container Instructions*
* **[Compute Container Detailed Configuration Reference](Docker/compute/README.md)** - *Advanced Container Instructions*
* For n8n, LANraragi, pgvector related configurations, please refer to the relevant project documentation.

## Configuration and Persistence Instructions

- It is recommended to fill in `Docker/data/.env` and `Docker/compute/.env` completely before the first deployment.
- After deployment, you can modify core configurations online via the `Settings` page of the Data UI. Saving takes effect immediately, usually without rebuilding containers.
- Configuration Priority: `app_config(DB) > JSON fallback > .env`.
- Secrets/tokens are stored in `app_config` in reversibly encrypted form; currently there is no key rotation function, manual backup of keys is recommended.
- If the key file is lost, historical ciphertext cannot be decrypted, and you need to re-enter the password and token in the WebUI and save it once.
- Under the current architecture, Data and Compute no longer rely on shared queue directories; EH URLs are passed through the PostgreSQL table `eh_queue`.
- You still need to retain persistence directories for each container (e.g., runtime, database volume, n8n data volume).

## Technology Stack

* **Vector Database**: PostgreSQL 17 + `pgvector`
* **Visual Model**: Google `SigLIP-SO400M`, Qwen Series VL Models
* **Orchestration Engine**: n8n (Workflow Automation)
* **Mobile**: Mihon (Android) + Custom LANraragi Plugin
* **Backend Framework**: FastAPI (Python 3.10), OpenAI Compatible Backend

## Disclaimer

This tool is for **Information Retrieval Research and Personal Archiving** only. Users are solely responsible for all content accessed, downloaded, or stored using this software. Please be sure to comply with the Terms of Service (ToS) of any external websites you access.

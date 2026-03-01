# AutoEhHunter Quick Start Guide

> 🌐 Language / 语言: [English](STARTUP_EN.md) | [中文](STARTUP.md)

## 0. Prerequisites

* **Docker Environment**: Docker Desktop / Docker Engine (v27+) recommended.
* **OpenAI-Compatible Backend (Optional)**: Supports `/v1` interfaces (LM Studio / vLLM / Ollama compatible layer, etc.) to drive multimodal model description generation, Agent routing, and text-enhanced retrieval.
* **Note**: LLM connection is optional; when unconfigured, the system can still run SigLIP-based visual retrieval, cluster recommendations, and basic data pipelines.

## 1. Basic Steps
1. **Clone the Project**
   ```bash
   git clone https://github.com/JBKing514/AutoEhHunter.git
   cd AutoEhHunter
   ```

2. **Quick Template Startup (Recommended)**
   ```bash
   docker compose -f Docker/quick_deploy_docker-compose.yml up -d
   ```

   This template will spin up: `pg17`, `lanraragi`, `main`.
   Currently, all backend APIs, Agents, scheduled tasks, and WebUI have been unified into the `Docker/main` container.

3. **Access WebUI**
   * Open `http://<host>:8501` in your browser.
   * **Upon first entry, the system will guide you into the Setup Wizard.** You simply need to seamlessly complete the database connection, create the first admin account, and bind LRR / EH credentials directly in the Web interface, **without manually modifying any `.env` files.**

## 2. Manual Step-by-Step Deployment (Optional)

Suitable for scenarios where you want to spin up containers individually or deploy across multiple hosts:

1. PostgreSQL (Must include the `pgvector` extension)
   ```bash
   docker compose -f Docker/pg17_docker-compose.yml up -d
   ```

2. LANraragi
   ```bash
   docker compose -f Docker/lanraragi_docker-compose.yml up -d
   ```

3. AutoEhHunter (Core Service)
   ```bash
   docker compose -f Docker/main_docker-compose.yml up -d
   ```

## 3. First Initialization and Data Synchronization

After completing the Setup Wizard, it is recommended to sequentially execute the following operations on the `Control` page to establish basic vector indices and a data baseline:

1. `[Fetch EH URLs Now]` (Full pull)
2. `[Run EH Ingest]` (Recommendation features are now available; calling SigLIP to compute cover vectors will take some time)
3. `[Export LRR Metadata]`（Includes gallarys and reading history)
4. `[Ingest LRR Text Data]`
5. `[Run LRR Ingest]`(Needs to configure the VL model, otherwise the script will fallback to SigLIP-Only mode, degrade the NLP searching accuracy)

> For daily maintenance, it is recommended to use the system's built-in **Schedule** page to configure automatic ingestion and exports. More detailed crawler filtering rules can be set on the configuration page; tags support fuzzy matching, or you can press Enter to input tags not yet in the library.
> To achieve the most complete data closed loop, we strongly recommend installing the custom LANraragi script located in `Companion/lrrMihonExtentionHistory`. This script reports reading records to LRR by calling the LRR API. The plugin in this repository is just a single fork and will not update frequently with the upstream; please do not submit PRs related to it here.

## 4. Model Connection Strategy

This system provides highly flexible routing configurations for Large Language Models and Embeddings (all dynamically modifiable in the `Settings` page):

* **Single Endpoint Mode**: Configure a powerful `/v1` endpoint (like a large vLLM instance) to simultaneously handle Image Description Generation (VL) + Semantic Vectors (Embedding) + Conversational Interaction (LLM).
* **Split/Multi-Endpoint Mode**:
  * `INGEST_API_BASE` (Ingestion Channel): Dedicated to gallery metadata and image cleaning (VL/Embedding). Can be configured with dedicated lightweight models.
  * `LLM_API_BASE` (Interaction Channel): Used for Agent chat, XP parsing reports, and search intent routing (can be connected to other local high-IQ closed-source models).
* **Minimum Practical Suggestion**: A `/v1` endpoint (Ollama, LM Studio, etc.) loaded with a 4B VL model + BGE-M3. There is no strict limit on model size, but models that are too small may generate inaccurate visual descriptions and low-quality Agent generated text; please consider this carefully.
* **Built-in SigLIP**: Visual feature vectors (Image-to-Image / Text-to-Image core) are run directly by the model loaded inside the `main` container, supporting 0-config automatic download and warmup, and can be cleared at any time to release memory.
* **Precautions**: Due to the sensitivity of this project's data, it is not recommended to use cloud APIs, and censored models (non-abliterated models) may frequently trigger security restrictions, affecting VL ingestion text description accuracy and Agent personality.

> **⚠️ Note for English Users (Agent & Prompts):**
> The default system prompts for the LLM Agent (used in Chat, XP Analysis, and Summaries) are written in Chinese. To get optimal English responses, you will need to manually translate or adjust these prompts to English in the `Settings` page under the LLM config section.

## 5. Runtime Suggestions

* EH Crawling Frequency: Recommended every 15~30 minutes.
* EH Filtered Ingestion Frequency: Recommended once every 1 hour.
* LRR Data Export and Vector Ingestion Frequency: Recommended once a day.
* The system defaults to using the CPU to run the SigLIP model, so the first full ingestion (tens of thousands of books) may take a long time, but daily incremental ingestion is effortless. Considering the complexity introduced by ROCm, CUDA, and other graphical acceleration dependencies, hardware acceleration using GPUs is temporarily not considered, but you can try to force GPU usage by modifying `Docker/main/requirements.txt` and environment variables. No technical support is provided for this.
* If you encounter difficulties getting metadata from LANraragi, please use the enhanced metadata script in `Companion/lrrMetadataPlugin`.

## 6. Sudo Privilege Escalation and Disaster Recovery

Considering that configuration is uniformly managed by the database, this system has designed a robust disaster recovery mechanism:

* **Sudo Lock**: Modifying dangerous operations like database connections in `Settings -> General` mandatorily requires verifying the current user's login password to unlock.
* **Configuration Backup**:
  * In the danger zone, you can download a runtime `app_config.json` backup with one click.
  * If configurations are lost due to database migration, you can upload and restore them here.
* **Recovery Codes**: During initialization/reset, the system will generate and print 10 burn-after-reading recovery keys (saved as SHA256) in the logs. When you forget your password or accidentally modify the database IP incorrectly making login impossible, you can use any recovery code on the login page to enter "Recovery Mode" to force correct configurations and reset the admin password.

## 7. Network Configuration Advice

The container supports configuring simple HTTP/HTTPS proxies, but due to the complexity of network environments, it is still highly recommended to use a VPN container (such as Gluetun). You can connect the container's network to the VPN container (e.g., using `network_mode: "container:<gluetun_container_name>"` in `docker-compose.yml` and enabling port forwarding on the Gluetun container), or use an independent `macvlan` / `ipvlan` network setup to ensure the stability of the system's crawler and library communications.

## 8. Troube-Shoot

* If you encounter problems downloading the SigLIP model or with environment dependencies (such as network issues), you can use the runtime pre-packaged [here](https://drive.google.com/drive/folders/1_xcQ3P2rFd8wqk_znCGlTHmVfyo9O5ma?usp=sharing). After extracting it to your host machine, simply point the container's runtime directory to this folder.
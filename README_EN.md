<p align="center">
  <img src="https://github.com/JBKing514/autoEhHunter/blob/main/Media/ico/AutoEhHunterLogo_256.png" width="256" alt="AutoEhHunter_Ico">
  <br>
</p>

# AutoEhHunter
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL-3.0-blue.svg)](https://opensource.org/licenses/MIT) [![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/) [![Vue 3](https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg)](https://vuejs.org/) [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

> 🌐 Language / 语言: [English](README_EN.md) | [中文](README.md)

### Private Multimodal RAG Retrieval & Analysis System for E-Hentai and LANraragi

<p align="center">
  <img src="Media/diagram/AutoEhHunter_Desktop_Webui.png" width="800" alt="AutoEhHunter_Ico">
  <br>
</p>

## Abstract
AutoEhHunter is a locally hosted Retrieval-Augmented Generation (RAG) and user preference analysis system. Based on E-Hentai (external data source) and LANraragi (local library), it introduces computer vision (SigLIP), Large Language Models (LLM), and rigorous mathematical statistics to build a closed-loop digital asset governance and recommendation system. The core goal of this project is to eliminate the high cognitive load brought by traditional Boolean logic-based tag retrieval systems, transforming library management into an intuitive process based on high-dimensional vectors and natural language interaction.

## Motivation
Human memory of visual and narrative content is fuzzy and emotional, but existing gallery systems require users to think like SQL parsers. When you want to find "a pure love doujin with a dark tone and a style similar to a certain author," traditional tag searches are often powerless.

Developing this project is not to pitch an "ultimate artifact" to the masses, but purely out of the self-salvation of someone with engineering OCD: I can't stand incomplete metadata, missing covers, nor the "Cyber ED" of facing thousands of books but not knowing what to read. If I'm going to do it, I'll use the most rigorous tech stack and treat "reading doujins" as a serious engineering and statistical subject to solve.

---

## Core Features

### 1. Multimodal Fusion Recommendation Based on Energy Re-ranking
Abandoning simple linear scoring mechanisms, the system adopts a recommendation algorithm inspired by physical energy models.
* **Principle**: The user's reading history (like/dislike/reading duration) is treated as "gravity sources" or "repulsion sources" in the vector space. During runtime, the algorithm dynamically fuses visual vectors (SigLIP), semantic vectors (BGE-M3, etc.), and metadata, introducing Interaction Decay Factors (e.g., impression penalty and misclick penalty). The system calculates the "potential energy" of candidate works in the current user's feature field and introduces Thermal Jitter based on the Boltzmann distribution for sampling. Works with lower potential energy (better fit) have a higher probability of being drawn, achieving a highly dynamic balance between personalized recommendation and exploratory discovery.

### 2. Academic-Grade XP Clustering Analysis

<p align="center">
  <img src="Media/diagram/AutoEhHunter_3dpca.png" width="800" alt="AutoEhHunter_Ico">
  <br>
</p>

Refusing meaningless word cloud statistics, it uses data science methods to strictly deconstruct your preferences.
* **Gaussian Kernel Density Estimation (KDE)**: Performs Principal Component Analysis (PCA) on 1024-dimensional feature vectors to reduce them to 2D/3D space. It generates a smooth probability density topology map via the KDE algorithm, visually displaying the distribution of your "strike zone".
* **Hierarchical Clustering**: Generates a Dendrogram based on SciPy, automatically discovering potential XP subclasses that you might not even realize exist, and supports dynamic cutting thresholds.

### 3. Multimodal Hybrid Search
Breaking the physical isolation between language and tags.
* **Visual & VL Fusion**: Supports native SigLIP image feature extraction (search by image) and combines with Vision-Language large models for deep image-text understanding of galleries.
* **NLP & Fuzzy Matching**: You can input natural language directly. The system's built-in Agent router will map natural language into high-dimensional vectors and combine it with LLM-driven Fuzzy Matching to perform millisecond-level hybrid weight retrieval in the local database.

### 4. Enterprise-Grade Security
For a system containing highly private information, security should not be an elective.
* **Cryptographic Standards**: Sensitive information (like E-Hentai Cookies, API keys) is strictly encrypted before storage (dynamic Salt, flexible hash iterations, independent Pepper, HKDF key derivation).
* **Configuration Convergence**: Global configuration is uniformly managed by PostgreSQL (supports emergency fallback to JSON/Env).
* **Minimized Attack Surface**: Completely abandoned exposed unauthenticated HTTP API ports. All high-compute tasks (e.g., SigLIP inference, crawling) are entirely contained within the backend Worker processes, triggered by the WebUI via secure internal routing.
* **Sudo Escalation Mechanism**: Sensitive operations in the WebUI (e.g., modifying database connections, clearing cache) force a Sudo secondary password verification.

### 5. Ops-Friendly Design
Considering the complexity of self-hosted environments, the system is designed with extremely high fault tolerance.
* **Global Exception Catching**: Underlying Traceback stack information is elegantly caught and sent to the frontend notification center, completely saying goodbye to the dilemma of "needing to SSH into the container to read logs to know what broke."
* **Stateless Recovery Codes**: Generates "burn-after-reading" Recovery Codes during initialization. Even if you forget the admin password or encounter a database connection failure, you can seamlessly enter emergency recovery mode using a recovery code.

### 6. Agent Functionality & Tiered Context
The system is not just a search engine, but a tactical adjutant that "understands you".
* **Context Awareness**: Built-in basic Agent routing; the AI will automatically call the local vector database to get context (RAG) based on your questions, supporting free chat regarding your library and statistical profile.
* **Extensible Interfaces**: A standard Tool Call plugin interface is reserved at the bottom layer, laying the foundation for integrating more complex automated workflows in the future.

> **⚠️ Note for English Users:** The current default System Prompts for the Agent are written in Chinese. English-speaking users may need to manually translate or adjust these prompts in the WebUI Settings to ensure the Agent outputs English responses seamlessly.

### 7. Mobile Optimization & Cross-Platform Support

<p align="center">
  <img src="Media/diagram/AutoEhHunter_Mobile_Webui.png" width="400" alt="AutoEhHunter_Ico">
  <br>
</p>

* The frontend is built on Vue 3 + Vuetify, adopting a responsive layout with extensive optimizations for mobile touch screens (swiping, misclick prevention, gestures).
* Supports **PWA (Progressive Web App)**, allowing it to be directly added to the phone desktop for an immersive borderless experience comparable to native apps.

### 8. Full-Chain Data Governance
A good model is built on good data. This project provides a complete suite for data cleaning and collection:
* **Enhanced LANraragi EH Plugin**: Deeply customized based on regular expressions, perfectly compatible with and repairing non-standard `.xml` or incomplete metadata left by early Ehviewer versions.
* **Custom Mihon (Tachiyomi) Plugin**: Automatically sends back reading history via the LANraragi API while reading on mobile, ensuring every page turn becomes real nutrients for the recommendation algorithm.

---

## System Architecture

<p align="center">
  <img src="Media/diagram/AutoEhHunter_Arch.png" width="800" alt="AutoEhHunter_Arch">
  <br>
</p>

---

## Requirements & Quick Start

The system uses containerized deployment and supports Zero-Config Cold Start.

* **Minimum Requirements**: 4 Core CPU / 4GB RAM / Any system that supports Docker (NAS / Linux / Windows).
* **External Dependencies**: A running PostgreSQL 17+ database (**the `pgvector` extension must be enabled**).
* **Optional Dependencies**: Local LANraragi library, used to provide user profiles based on local reading history. If not installed, recommendation features are still available, but data analysis, Agent, and other services relying on closed-loop data pipelines will be unavailable.

### Model Configuration
This system provides highly flexible routing configurations for Large Language Models and Embeddings (all dynamically modifiable in the WebUI):
* **Recommended Configuration**: 8 Core CPU / 16GB RAM / A backend running an OpenAI-compatible (`/v1`) interface (e.g., LM Studio, vLLM, Ollama). It should support a Vision-Language (VL) model with at least 8B parameters for generating precise text descriptions of gallery images, as well as a conventional LLM for Agent chat and analysis.
* **Single Endpoint Mode**: Configure a powerful `/v1` endpoint (like a large vLLM instance) to handle Image Description Generation (VL) + Semantic Vectors (Embedding) + Conversational Interaction (LLM) simultaneously.
* **Split/Multi-Endpoint Mode**:
  * `INGEST_API_BASE` (Ingestion Channel): Dedicated to gallery metadata and image processing (VL/Embedding). Can be configured with dedicated lightweight models.
  * `LLM_API_BASE` (Interaction Channel): Used for Agent chat, XP analysis reports, and search intent routing (can be connected to other local high-IQ closed-source models).
* **Minimum Practical Suggestion**: A `/v1` endpoint (Ollama, LM Studio, etc.) loaded with a 4B parameter VL model and a BGE-M3 model. There is no strict limit on model size, but models that are too small may generate inaccurate visual descriptions and low-quality Agent text. Please consider this carefully.
* **Privacy & Censorship Limits**: Due to the sensitive nature of this project's data, using cloud-based APIs is highly discouraged; additionally, censored models (non-abliterated models) may frequently trigger safety limits, affecting the accuracy of ingestion text descriptions and Agent persona.

**Quick Start:**
1. Prepare a standard `docker-compose.yml` (refer to `/docs/docker-compose.example.yml`).
2. Run `docker-compose up -d`.
3. Visit `http://<Your IP>:<Port>` and follow the smooth **Setup Wizard** on the screen to fill in the database and API information. No manual modification of `.env` files is needed.

> For detailed deployment instructions, proxy configurations, and advanced network settings (Macvlan/Gluetun), please refer to [**STARTUP_EN.md**](STARTUP_EN.md).

---

## Development & Contribution

The code generation part of this project deeply integrates AI-assisted programming ("Vibe Coding"). But rest assured, the overall architectural design, mathematical model derivations, security arguments, and every Git Commit are reviewed and controlled by a real human with strict engineering standards (a PhD student researching electromagnetic fields and antennas).

Due to the geeky nature of the system and domain-specific constraints, we are not actively seeking large-scale community spread at the moment. If you happen to have the same OCD and approve of this architectural philosophy, you are welcome to submit Issues or PRs.

* Frontend Stack: Vue 3 (Composition API), Pinia, Vuetify, Vite
* Backend Stack: FastAPI, Psycopg 3, HTTPX, PyTorch, Transformers
* Algorithm Stack: SciPy, Scikit-learn

## ⚠️ Disclaimer

This tool is strictly for **information retrieval technology research and personal library archiving**. Users assume full responsibility for all content accessed, downloaded, or stored using this software. Please be sure to comply with the Terms of Service (ToS) of any external websites you access, and configure crawling frequencies reasonably.
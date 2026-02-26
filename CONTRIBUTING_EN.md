# Contribution Guide

> 🌐 Language / 语言: [English](CONTRIBUTING_EN.md) | [中文](CONTRIBUTING.md)

Thank you for your interest in contributing to **AutoEhHunter**!

This project has evolved from a simple automation script into a complex RAG system encompassing large vision models, recommendation algorithms, multimodal hybrid retrieval, and a modern frontend. We welcome developers with the same **"engineering OCD"** to join us in polishing this self-hosted digital asset governance hub.

---

## Philosophy & Development Guidelines

Before submitting any code, please understand the core development philosophy of this project:

1. **Rigorous Mathematical & Logical Control**:
   The core code of this project deeply integrates AI-assisted programming ("Vibe Coding"). However, we have extremely strict manual review standards. For any PRs involving modifications to recommendation algorithms (like energy re-ranking) or XP clustering (KDE, PCA), **please provide the derivation process or mathematical principles in the description**. Do not submit AI-generated code that you cannot explain yourself.
2. **Zero-Config Cold Start**:
   We highly value the user's deployment experience. The introduction of any new feature **absolutely must not** add mandatory `.env` environment variable requirements. All configuration items must be converged into the WebUI's Setup Wizard and the `app_config` database table.
3. **Security First**:
   The system handles highly private local data. Please do not compromise security for convenience. We insist on:
   * Zero external unauthenticated HTTP API ports (all converted to in-process Worker calls).
   * Strict anti-CSRF mechanisms (Double Submit Cookie + SameSite=Strict).
   * Sensitive operations must be integrated with the global Sudo secondary authentication lock.
4. **Ultimate Frontend Elegance**:
   For UI/UX modifications, we pursue a smoothness comparable to commercial software (such as Apple-style fluid Gaussian blur scaling and ghost loading mechanisms). We reject stiff DOM jumps and synchronous requests that block the main thread.

---

## Where We Need Help

Although the system framework is stable, we still need the wisdom of the community in the following deep waters:

### 1. Algorithms & RAG
* **Hybrid Retrieval Weight Tuning**: Currently, the RRF (Reciprocal Rank Fusion) weights for visual (SigLIP), semantic (BGE-M3), and metadata are set based on experience. We welcome more scientific dynamic weight allocation strategies.
* **Recommendation Potential Energy Model**: This project currently uses a physics-inspired potential energy model and Boltzmann distribution for recommendations, combining **Touch/Impression Penalties** and **Thermal Jitter** to introduce exploration. We **do not use** crude linear Time Decay. We welcome everyone to research Concept Drift detection mechanisms based on this, or to propose more elegant mathematical tuning schemes for normalizing the weights of multiple potential fields (tags, visual, long-term profile).

### 2. Frontend & UI/UX
* **Tech Stack**: Vue 3 (Composition API), Pinia, Vuetify
* **Optimization Directions**: Mobile gesture optimization (like swipe to return, waterfall misclick prevention), deep PWA integration, more advanced CSS physical easing animations.

### 3. Data Pipeline & Scrapers
* **Tech Stack**: Python 3.11, HTTPX, requests
* **Optimization Directions**: Enhance E-Hentai/ExHentai metadata parsing regex; perfect automatic backoff and polling retry mechanisms under various extreme network environments (basic async ghost loading and multi-CDN polling have been implemented, but there is still room for tuning).
* **LANraragi Plugin**: Improve the customized Mihon plugin's reading history reporting logic. Currently, it only triggers a report when opening a gallery, and cannot record detailed information such as reading duration and page count.

### 4. LLM & VL Integration
* **API & Hardware Config Isolation**: Architecturally, we strictly distinguish the calling links and endpoint configurations between **Vision-Language (VL) models** and **standard Large Language Models (LLM)**. VL models (like image tagging analysis) and pure text LLMs (like summary generation) are completely different in terms of API rate, concurrency cost, and hardware requirements. When adding new features, please ensure the configurations for both are independent and clarify the different hardware/API needs in the documentation.
* **Dynamic Prompt Management**: All core System Prompts have been migrated from hardcoding to a unified configuration flow. When adding or tuning Prompts, please map them centrally in `constants.py` (default values) and the database table, ensuring users can hot-reload them instantly in the WebUI. Writing magic strings in business Workers is prohibited.
* **VL Model Semantic Description Generation**: The current VL prompts are mainly oriented towards describing single-image features rather than overall plot summarization. We can further improve image input and add plot description fields to the system prompts to achieve more precise semantic descriptions and improve the accuracy of natural language retrieval.

---

## Development Setup

The project uses a monolithic architecture with the frontend and backend originating from the same source (frontend is hosted by FastAPI after building), but they can be separated during local development.

1. **Infrastructure Deployment**:
   You need a PostgreSQL database with `pgvector`. It is recommended to use the provided `docker-compose.example.yml` to start only the `db` service.
2. **Backend (FastAPI)**:
   ```bash
   cd main
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   # Start the backend service (listens on 8501 by default)
   uvicorn webapi.main:app --reload --port 8501
   ```
3. **Frontend (Vue 3)**:
   ```bash
   cd main/webui
   npm install
   # Start the Vite dev server (with HMR)
   npm run dev
   ```
   *Note: You need to configure a proxy in the frontend's `vite.config.js` to proxy `/api` requests to your local FastAPI port to maintain a strict same-origin policy.*

---

## Pull Request Checklist

Before initiating a Pull Request, please check the following items:

* [ ] **Code Formatting**: Does the Python code conform to `black` and `isort` specifications? Have necessary Type Hints been added?
* [ ] **Cold Start Test**: After completely clearing the database and without any old configurations, can the WebUI's Setup Wizard be successfully invoked and initialized smoothly?
* [ ] **Security Boundary Test**: Have any interfaces requiring cross-origin access been introduced? If a new API is added, is it correctly integrated with the `app.authUser` dependency and authentication middleware?
* [ ] **Exception Catching**: Are there any blocking operations (like synchronous large file downloads) that could cause the FastAPI main thread (Threadpool Exhaustion) to freeze? Please be sure to use `anyio` to offload to the background or use `httpx.AsyncClient`.

Whether you are submitting a fix for a small bug or introducing a complex statistical algorithm, we sincerely thank you for your support of AutoEhHunter!
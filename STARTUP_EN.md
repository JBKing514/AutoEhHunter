# AutoEhHunter Quick Start Guide

> 🌐 Language / 语言: [English](STARTUP_EN.md) | [中文](STARTUP.md)

## 0. Prerequisites

* **Docker Environment**: Recommended to install Docker Desktop or Docker Engine (v27+).
* **OpenAI Compatible Backend**: You need an available `/v1` interface (such as `ollama`, `vLLM`, `LM Studio`, etc.), this project does not include a large model backend, configuration recommendation is in [README_EN.md](README_EN.md).
* **Network Environment**:
    * Compute container needs to connect to HuggingFace to download the SigLIP visual model at startup.
    * Data container needs to be able to access E-Hentai (if crawler is enabled).

## 1. Basic Configuration

1.  **Clone Project**
    ```bash
    git clone https://github.com/JBKing514/AutoEhHunter.git
    cd AutoEhHunter
    ```

2.  **Create Configuration Files**
    Create `.env` files in `compute` and `data` directories respectively:
    ```bash
    cp Docker/compute/.env.example Docker/compute/.env
    cp Docker/data/.env.example Docker/data/.env
    ```
    > **Tip**: Please be sure to edit the `.env` file and fill in your Postgres password, LLM API address, and Key.
    Important variables are listed as follows:
    Compute container: Database, LANraragi, OpenAI-compatible endpoints are required, EH_COOKIE= in EH incremental ingest is recommended, but EH API can be called without it.
    Data container: Database, Data UI, LANraragi are required, EH_COOKIE= in EH queue fetch is recommended, but EH API can be called without it.
    If you have ExHentai access permissions, after filling in the COOKIE, you can try to replace EH_BASE_URL with the ExHentai address to get ExHentai results.

3.  **Configuration Strategy Suggestions**
    * Before the first startup, it is recommended to fill in `.env` completely (most stable).
    * After startup, you can modify the configuration online in the `Settings` page of the Data UI, and it will take effect immediately after saving without rebuilding the container.
    * Secrets/Token will be written to `app_config` with reversible encryption. Currently, there is no key rotation function; if the key file is lost, you need to re-enter the password and token and save it once to regenerate and distribute the key, manual backup of keys is recommended.


## 2. Choose Deployment Mode (Select One)

Please choose a deployment method according to your hardware conditions.

### Option A: High Performance AIO (All-In-One)
*Applicable scenario: Own a workstation with sufficient VRAM/RAM, hope all services run together.*

1.  **Modify Configuration**: Open `docker-compose.aio.yml` in the project root directory.
    * Check `volumes` mapping paths.
2.  **Start**:
    ```bash
    docker compose -f docker-compose.aio.yml up -d
    ```

### Option B: Split Plane
*Applicable scenario: NAS (running crawler/database) + Main PC (running visual model/LLM).*

**1. Data Side (NAS/Low-power device):**
* Modify `docker-compose.data-plane.yml`.
* Start:
    ```bash
    docker compose -f docker-compose.data-plane.yml up -d
    ```

**2. Compute Side (High Performance PC):**
* Modify `Docker/compute_docker-compose.yml`.
* Start:
    ```bash
    docker compose -f Docker/compute_docker-compose.yml up -d
    ```

### Option C: Manual Deployment
*Applicable scenario: No Docker Compose environment (such as some Unraid) or need deep customization.*

Please refer to the `docker run` commands in `Docker/compute/README.md` and `Docker/data/README.md` to start containers manually one by one.

> Note: The current version defaults to passing EH URLs via PostgreSQL `eh_queue`, containers do not need to share queue directories. Please ensure that the 5 containers (`pg17`, `lanraragi`, `n8n`, `data`, `compute`) are visible to each other on the network, and can all connect to pgvector; otherwise manual triggering, scheduled tasks, EH URL fetching, and ingestion in WebUI may not work.

## 3. First Initialization (Critical Step)

After the container starts, the database is empty by default. Please initialize the data in the following order:

1.  **Access Data UI Console**:
    * Open `http://<Data Container IP>:8501` in browser.

2.  **Execute Initialization Tasks** (Click in order on the `Control` page):
    1.  `[Immediate Crawl EH]`: Get incremental URL queue.
    2.  `[Export LRR]`: Get local LANraragi metadata.
    3.  `[Text Ingest]`: Write metadata from LANraragi into PostgreSQL.
    4.  `[Vector Ingest run_worker]`: **Time-consuming operation**. Start calling GPU/CPU to calculate image vectors. Note to delete the default parameters below run_worker to perform full ingestion. The first run will download the SigLIP visual model (about 1GB+) weights, which may take 2-10 minutes depending on network conditions, please check container logs to determine download progress and weight loading status.
    5.  `[EH Ingest run_eh_ingest]`: Call EH API to read metadata in the URL queue, and perform metadata and image vector ingestion for items meeting filtering conditions (can be set in .env in compute container).
    6.  Set Scheduler and save automatic tasks to ensure crawling and ingestion operations can be executed automatically.
 > `[Daily Ingest run_daily]` executes vector ingestion and EH ingestion sequentially, recommended to set Scheduler to execute periodically.

## 4. Connect Brain (n8n & Telegram)

1.  **Configure n8n HTTPS Access**:
    * Accessing n8n webui defaults to requiring HTTPS protocol, it is recommended to use Cloudflare Tunnel or Tailscale Funnel to expose n8n port as HTTPS. For detailed steps, please refer to [n8n official documentation](https://docs.n8n.io/hosting/).
2.  **Enter n8n**:
    * Open `https://<n8n Container IP/Tunnel Address>:5678` in browser.

3.  **Import Workflow**:
    * Import `./Companion/n8nWorkflows/Main Agent.json` (Main Intent Recognition).
    * Import `./Companion/n8nWorkflows/hunterAgent_sub.json` (Tool Call).

4.  **Authentication Configuration**:
    * Configure Credentials for `OpenAI Chat Model` in n8n (pointing to your LLM backend).
    * Configure Bot Token for `Telegram`.

5.  **Webhook Notes**:
    * **HTTPS Required**: Telegram Bot API requires Webhook callback address to be public HTTPS, otherwise Webhook cannot be registered.

## 5. Optional Steps: Build Complete Data Loop (Optional)

To obtain the best recommendation effect and metadata quality, it is recommended to configure the following components to connect reading data and metadata links.

### A. Mobile Reading Record Return (Mihon)
* **Installation**: Please install the customized LANraragi plugin under `./Companion/lrrMihonExtentionHistory` directory (`tachiyomi-all.lanraragi-v1.4.20-debug.apk`) to your Mihon/Tachiyomi client.
* **Function**: This plugin will automatically call LRR API to report progress when you read, thereby feeding the system's **XP Clustering**.
* **Declaration**: The plugin source code contained in this repository is for reference only (single Fork), **will not frequently follow upstream updates**.
    * If you intend to contribute code to the plugin (such as accessing more APIs), please go to the [**Original Plugin Repository**](https://github.com/keiyoushi/extensions-source) to submit PR, **DO NOT** submit related Extension code merge requests in this repository.

### B. Enhanced Metadata Acquisition (LANraragi)
* **Installation**: Upload the `EhViewerFile.pm` script under `./Companion/lrrMetadataPlugin` to LANraragi's `Plugins` -> `Upload Custom Plugin`.
* **Function**: Enhance parsing capabilities for non-standard EH metadata (such as `metadata` text, `comicinfo.xml`, `ehviewer` database), and support directly completing missing metadata from EH API. Supports translating tags to Chinese via EhTagTranslation, principle reference: [ETagCN](https://github.com/zhy201810576/ETagCN?tab=readme-ov-file).
* **⚠️ Persistence Warning**:
    When deploying LANraragi using Docker, **be sure** to map the plugin directory inside the container to the host.
    * **Path**: `/home/koyomi/lanraragi/lib/LANraragi/Plugin/Sideloaded`
    * **Consequence**: If this directory is not mapped, **custom plugins you uploaded will be lost after container restart**, causing metadata acquisition function failure.
    * *Docker Compose Example*:
        ```yaml
        volumes:
          - ./your_local_lrr_plugins:/home/koyomi/lanraragi/lib/LANraragi/Plugin/Sideloaded
        ```

## 6. Long-term Operation Guide

To maintain data timeliness and system stability, the following are recommended configuration parameters and operation suggestions based on long-term testing.

### Crawler Strategy
* **Run Frequency**: Recommended to run `EH Fetch` task every **10~30 minutes**.
* **Page Depth**: Under current site activity, update rate is about **1 book/minute**, setting environment variable `EH_FETCH_MAX_PAGES=8` usually has a large margin (covering about 200 items/round).
    * **Monitoring Indicator**: If `checkpoint_not_reached=true` is continuously observed in logs, it means new content generation speed exceeds crawling frequency, please **increase** `EH_FETCH_MAX_PAGES` value or **shorten** run interval.
* **Network Isolation and Risk Control**:
    * Since `Data` and `Compute` containers of this project need to access EH API, if you want to minimize the risk of IP Ban, it is recommended to route the network stack of both containers through VPN containers like **Gluetun**.

### Stability Suggestions
* **Cookie Configuration**: **Strongly recommended** to configure `EH_COOKIE`. This not only unlocks restricted content (ExHentai), but also significantly improves crawl connection stability and metadata parsing consistency.

### Ingestion and Compute Planning
* **Run Frequency**: Recommended to run full ingestion task every **24 hours**.
    * If you find background tasks can't catch up with new progress, please appropriately shorten the interval.
* **Compute Benchmark (CPU vs GPU)**:
    * **Measured Data**: Tested in **AMD Ryzen 7 (H Series) 255** (8 core 16 threads) pure CPU environment:
        * **SigLIP Cover Vectorization**: Approx **2-3 seconds** / image.
        * **LRR Visual Vector Ingestion** (Cover + 3 inner pages): Approx **10-20 seconds** / book.
    * **Conclusion**: For daily incremental maintenance, **pure CPU operation is completely sufficient**, there is no mandatory need to use GPU temporarily.
* **VL Model Strategy**:
    * The processing speed of the visual language model depends on the inference Token generation speed.
    * Since ingestion is performed **offline asynchronously**, as long as thousands of new archives are not injected in a short time (large-scale import), running once every 24 hours is completely sufficient to "digest" the day's increment. Please configure model parameters according to your hardware conditions.
---
**Now, try sending an image to your Bot and start experiencing!**

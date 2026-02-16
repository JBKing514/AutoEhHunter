# AutoEhHunter 快速启动指南

## 0. 前提条件

* **Docker 环境**：推荐安装 Docker Desktop 或 Docker Engine (v27+)。
* **OpenAI 兼容后端**：你需要一个可用的 `/v1` 接口（如 `ollama`, `vLLM`, `LM Studio` 等），本项目不包含大模型后端，配置推荐在[README.md](README.md)。
* **网络环境**：
    * Compute 容器启动时需连接 HuggingFace 下载 SigLIP 视觉模型。
    * Data 容器需能访问 E-Hentai (如果启用了爬虫)。

## 1. 基础配置

1.  **克隆项目**
    ```bash
    git clone [https://github.com/YourRepo/AutoEhHunter.git](https://github.com/YourRepo/AutoEhHunter.git)
    cd AutoEhHunter
    ```

2.  **创建配置文件**
    分别在 `compute` 和 `data` 目录创建 `.env` 文件：
    ```bash
    cp Docker/compute/.env.example Docker/compute/.env
    cp Docker/data/.env.example Docker/data/.env
    ```
    > **提示**：请务必编辑 `.env` 文件，填入你的 Postgres 密码、LLM API 地址和 Key。
    重要变量分列如下：
    compute容器：Database，LANraragi，OpenAI-compatible endpoints必填，EH incremental ingest中的EH_COOKIE=建议填写，但不填也能调用EH API
    data容器： Database，Data UI，LANraragi必填，EH queue fetch中的EH_COOKIE=建议填写，但不填也能调用EH API
    如果您有里站访问权限，填写COOKIE后可尝试将EH_BASE_URL替换为里站地址以获取里站结果


## 2. 选择部署模式 (三选一)

请根据你的硬件条件选择一种部署方式。

### 选项 A：高性能单机 (AIO)
*适用场景：拥有一台显存/内存充足的工作站，希望所有服务跑在一起。*

1.  **修改配置**：打开项目根目录的 `docker-compose.aio.yml`。
    * 检查 `volumes` 映射路径。
    * **关键**：确保 `data` 和 `compute` 容器映射了**同一个**宿主机目录到 `/app/runtime/eh_ingest_cache`。
2.  **启动**：
    ```bash
    docker compose -f docker-compose.aio.yml up -d
    ```

### 选项 B：存算分离 (Split)
*适用场景：NAS (运行爬虫/数据库) + 主力 PC (运行视觉模型/LLM)。*

**1. Data 端 (NAS/低功耗设备):**
* 修改 `docker-compose.data-plane.yml`。
* 启动：
    ```bash
    docker compose -f docker-compose.data-plane.yml up -d
    ```

**2. Compute 端 (高性能 PC):**
* 修改 `Docker/compute_docker-compose.yml`。
* **关键**：需挂载与 Data 端共享的 `eh_ingest_cache` 目录（通过 SMB/NFS 或同步工具），否则无法读取爬下来的URL。
* 启动：
    ```bash
    docker compose -f Docker/compute_docker-compose.yml up -d
    ```

> **⚠️ 权限警告**：跨容器/跨机共享目录时，请确保宿主机上的 `eh_ingest_cache` 文件夹具有**读写权限**（建议 `chmod 777`），避免因权限不足导致 Compute 容器无法读取URL列表进行基于元数据的入库筛选和后续图片向量计算。

### 选项 C：手动部署
*适用场景：无 Docker Compose 环境 (如部分 Unraid) 或需深度定制。*

请参考 `Docker/compute/README.md` 和 `Docker/data/README.md` 中的 `docker run` 命令手动逐个拉起容器。

## 3. 首次初始化 (关键步骤)

容器启动后，数据库默认为空。请按以下顺序初始化数据：

1.  **访问 Data UI 控制台**：
    * 浏览器打开 `http://<Data容器IP>:8501`。

2.  **执行初始化任务** (在 `Control` 页面依次点击)：
    1.  `[立即爬取 EH]`：获取增量 URL 队列。
    2.  `[导出 LRR]`：获取本地 LANraragi 的元数据。
    3.  `[文本入库]`：将来自LANraragi的元数据写入 PostgreSQL。
    4.  `[向量入库 run_worker]`：**耗时操作**。开始调用 GPU/CPU 计算图片向量。注意删除下方的run_worker默认参数以进行全量入库。首次运行时容器会下载SigLIP 视觉模型（约 1GB+）权重，视网络情况可能需要等待2-10分钟，请查看容器日志以确定下载进度和权重加载情况
    5.  `[EH入库 run_eh_ingest]`: 调用EH API读取URL队列中的元数据，对符合筛选条件的（可在compute容器中的.env中设置）项目进行元数据和图片向量入库
    6.  设置Scheduler并保存自动任务，确保爬取和入库操作能自动执行
 > `[日常入库 run_daily]`为按顺序执行向量入库和EH入库，推荐设置Scheduler定时执行

## 4. 连接大脑 (n8n & Telegram)

1.  **配置 n8n https访问**：
    * 访问n8n webui默认需要HTTPS协议，建议使用 Cloudflare Tunnel 或 Tailscale Funnel 将 n8n 端口暴露为 HTTPS。详细步骤请参考[n8n官方文档](https://docs.n8n.io/hosting/)
2.  **进入 n8n**：
    * 浏览器打开 `https://<n8n容器IP/telnet地址>:5678`。

3.  **导入工作流**：
    * 导入 `./Companion/n8nWorkflows/Main Agent.json` (主意图识别)。
    * 导入 `./Companion/n8nWorkflows/hunterAgent_sub.json` (工具调用)。

4.  **鉴权配置**：
    * 在 n8n 中配置 `OpenAI Chat Model` 的 Credentials (指向你的 LLM 后端)。
    * 配置 `Telegram` 的 Bot Token。

5.  **Webhook 注意事项**：
    * **HTTPS 必须**：Telegram Bot API 要求 Webhook 回调地址必须是公网 HTTPS，否则无法注册Webhook。

## 5. 可选步骤：构建完整数据闭环 (Optional)

为了获得最佳的推荐效果和元数据质量，建议配置以下组件以打通阅读数据与元数据链路。

### A. 移动端阅读记录回传 (Mihon)
* **安装**：请安装 `./Companion/lrrMihonExtentionHistory` 目录下的定制版 LANraragi 插件 (`tachiyomi-all.lanraragi-v1.4.20-debug.apk`) 到您的 Mihon/Tachiyomi 客户端。
* **作用**：该插件会在您阅读时自动调用 LRR API 回传进度，从而喂养系统的 **XP 聚类**。
* **声明**：本仓库包含的插件源码仅供参考（单次 Fork），**不会频繁跟随上游更新**。
    * 如果您有意为插件贡献代码（如接入更多 API），请前往[**原始插件仓库**](https://github.com/keiyoushi/extensions-source)提交 PR，**请勿**在本仓库提交相关 Extension 的代码合并请求。

### B. 增强型元数据获取 (LANraragi)
* **安装**：将 `./Companion/lrrMetadataPlugin` 下的 `EhViewerFile.pm` 脚本上传至 LANraragi 的 `Plugins` -> `Upload Custom Plugin`。
* **作用**：增强对非标准 EH 元数据（如 `metadata` 文本, `comicinfo.xml`, `ehviewer` 数据库）的解析能力，并支持直接从 EH API 补全缺少的元数据。支持通过EhTagTranslation将标签翻译为中文，原理参考：[ETagCN](https://github.com/zhy201810576/ETagCN?tab=readme-ov-file)
* **⚠️ 持久化警告**：
    在使用 Docker 部署 LANraragi 时，**务必**将容器内的插件目录映射到宿主机。
    * **路径**：`/home/koyomi/lanraragi/lib/LANraragi/Plugin/Sideloaded`
    * **后果**：如果未映射该目录，**容器重启后您上传的定制插件将会丢失**，导致元数据获取功能失效。
    * *Docker Compose 示例*:
        ```yaml
        volumes:
          - ./your_local_lrr_plugins:/home/koyomi/lanraragi/lib/LANraragi/Plugin/Sideloaded
        ```

## 6. 长期运行指南 (Long-term Operation Guide)

为了保持数据的实时性与系统的稳定性，以下是基于长期实测的推荐配置参数与运维建议。

### 🕷️ 爬虫策略 (Crawler)
* **运行频率**：建议每 **10~30 分钟** 运行一次 `EH Fetch` 任务。
* **页面深度**：在当前站点活跃度下更新速率约为**1本/分钟**，设置环境变量 `EH_FETCH_MAX_PAGES=8` 通常有较大余量（约覆盖 200 条/轮）。
    * **监控指标**：如果在日志中连续观察到 `checkpoint_not_reached=true`，说明新内容的产生速度超过了抓取频率，请 **提高** `EH_FETCH_MAX_PAGES` 值或 **缩短** 运行间隔。
* **网络隔离与风控**：
    * 本项目的 `Data` 和 `Compute`容器由于需要访问EH API，如果您想最小化 IP 被 Ban 的风险，建议将两容器的网络堆栈通过 **Gluetun** 等 VPN 容器进行路由。

### 🛡️ 稳定性建议
* **Cookie 配置**：**强烈建议** 配置 `EH_COOKIE`。这不仅能解锁受限内容（ExHentai），还能显著提升抓取连接的稳定性与元数据解析的一致性。

### ⚙️ 入库与算力规划 (Ingestion)
* **运行频率**：建议每 **24 小时** 运行一次全量入库任务。
    * 如果发现后台任务追不上新增进度，请适当缩短间隔。
* **算力基准 (CPU vs GPU)**：
    * **实测数据**：在 **AMD Ryzen 7 (H系列) 255** （8核16线程）纯 CPU 环境下测试：
        * **SigLIP 封面向量化**：约 **2-3秒** / 张。
        * **LRR 视觉向量入库** (封面 + 3张内页)：约 **10-20秒** / 本。
    * **结论**：对于日常增量维护，**纯 CPU 运行已完全足够**，暂时没有强制使用 GPU 的必要。
* **VL 模型策略**：
    * 视觉语言模型的处理速度取决于推理 Token 生成速度。
    * 由于入库是**离线异步**进行的，只要不是短时间内注入数千本新档案（大规模导入），每 24 小时运行一次完全足以“消化”当天的增量。请根据您的硬件条件量力配置模型参数。
---
**现在，试着给你的 Bot 发一张图片，开始体验吧！**
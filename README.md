# AutoEhHunter

一个面向 LANraragi + EH 数据源的全栈多模态 RAG 项目，包含：

- 数据面（Data Plane）：LRR 元数据/阅读记录导出、EH 增量 URL 抓取、文本入库。
- 算力面（Compute Plane）：`hunterAgent` 技能服务、向量入库 worker、EH 元数据入库与封面 SigLIP 向量化。
- 编排与客户端（Companion）：n8n 工作流模板、Mihon 定制 LRR 插件源码与构建产物。

当前仓库已按部署职责拆分为 `Docker/` 与 `Companion/`。

## 项目结构

```text
AutoEhHunter/
  Docker/
    compute/                      # hunterAgent + vectorIngest
    data/                         # ehCrawler + lrrDataFlush + textIngest
    compute_docker-compose.yml
    data_docker-compose.yml
    pg17_docker-compose.yml
    n8n_docker-compose.yml
  Companion/
    n8nWorkflows/                 # 工作流模板（独立分发）
    lrrMihonExtentionHistory/     # Mihon 插件源码/构建产物
```

## 功能总览

- `Data` 容器
  - EH 增量 URL 抓取：`ehCrawler/fetch_new_eh_urls.py`
  - LRR 全量元数据导出：`lrrDataFlush/export_lrr_metadata.py`
  - LRR 最近阅读导出：`lrrDataFlush/export_lrr_recent_reads.py`
  - JSONL 入库 PG：`textIngest/ingest_jsonl_to_postgres.py`
  - Data UI：`webui/app.py`（Dashboard/Control/Audit/XP Map）
  - 首次启动自动 schema 初始化（一次性）
- `Compute` 容器
  - `hunterAgent` 技能服务（search/profile/report/recommendation/chat）
  - 向量 worker：`vectorIngest/worker_vl_ingest.py`
  - EH 元数据入库：`vectorIngest/ingest_eh_metadata_to_pg.py`

## 部署前准备

- Docker 27+（无 `docker compose` 也可部署，见下文纯 Docker 命令）
- 可访问的 PostgreSQL（建议 pgvector）
- 可访问的 OpenAI 兼容后端（`/v1`）：可用 `ollama`、`llama.cpp`、`LM Studio` 等
- LANraragi 服务可访问

## 硬件需求

- `data` 容器
  - 资源要求低，`RAM < 512MB` 也可运行
  - 镜像体积约 `1.1GB`
- `compute` 容器
  - 会调用 SigLIP；当前默认走 CPU 兼容路径
  - 推荐 `8` 核以上 CPU，否则向量入库/搜图可能明显变慢
  - 可选 GPU 加速（需自行处理 PyTorch 版本与 CUDA 兼容）
  - 特别提示：`50 系 / Blackwell` 架构通常需要手动安装匹配版本，并在环境变量中启用 GPU
  - 镜像体积约 `8.0GB`
- LLM 侧
  - 需使用 OpenAI 兼容 API（`/v1`）
  - 当前提示词主要针对 `Qwen3-Next-80B-A3B-Instruct` 调优
  - 其他模型可能出现输出质量下降，后续需要单独调 prompt
  - 搜索/推荐核心流程为代码逻辑驱动，即使无 LLM 或提示词效果较差，仍可运行基础检索推荐

建议先建 private 仓库验证，再公开。

## 当前状态评估

- 功能链路：已形成完整闭环（抓取/导出 -> 清洗入库 -> 向量检索与推荐 -> Agent -> n8n/Telegram -> 阅读回流）
- 工程状态：容器化完成（`data` + `compute` + 可选 `data-ui`），支持 compose 与非 compose 部署
- 安全状态：敏感信息已模板化；当前扫描未发现明显 token/私网硬编码残留
- 发布建议：可以推 private repo 做第一轮外部验证，再根据反馈整理公开版本

## 1) 配置文件

在 `Docker/` 目录执行：

```bash
cp compute/.env.example compute/.env
cp data/.env.example data/.env
```

重点配置项：

- `compute/.env`
  - `POSTGRES_DSN`
  - `LRR_BASE` / `LRR_API_KEY`
  - `LLM_API_BASE` / `EMB_API_BASE` / `LLM_MODEL` / `EMB_MODEL`
  - `VL_BASE` / `EMB_BASE` / `VL_MODEL_ID` / `EMB_MODEL_ID`
- `data/.env`
  - `POSTGRES_DSN`
  - `LRR_HOST` / `LRR_PORT` / `LRR_API_KEY`
  - `EH_COOKIE`（需要抓取 EH 时）

## 2) 启动 PostgreSQL（示例）

`Docker/pg17_docker-compose.yml` 已改为读取环境变量密码：

```bash
export POSTGRES_PASSWORD='your_strong_password'
docker compose -f pg17_docker-compose.yml up -d
```

若无 `docker compose`，请用你现有的容器管理方式（Unraid UI 或 `docker run` 等价配置）。

## 3) 启动 Compute（两种方式）

### A. compose

```bash
docker compose -f compute_docker-compose.yml up -d --build
```

### B. 纯 Docker（推荐给无 compose 环境）

```bash
docker build -t autoeh-compute:local -f compute/Dockerfile .

docker run -d \
  --name autoeh-compute \
  --restart unless-stopped \
  --env-file compute/.env \
  -p 18080:18080 \
  -v "$(pwd)/compute/runtime:/app/runtime" \
  -v "$(pwd)/compute/hf_cache:/root/.cache/huggingface" \
  -v "$(pwd)/compute/eh_ingest_cache:/app/runtime/eh_ingest_cache" \
  autoeh-compute:local agent
```

健康检查：

```bash
curl http://127.0.0.1:18080/health
```

## 4) 启动 Data（两种方式）

### A. compose

```bash
docker compose -f data_docker-compose.yml up -d --build
```

### B. 纯 Docker（推荐给无 compose 环境）

```bash
docker build -t autoeh-data:local -f data/Dockerfile .

docker run -d \
  --name autoeh-data \
  --restart unless-stopped \
  --env-file data/.env \
  -v "$(pwd)/data/runtime:/app/runtime" \
  -v "$(pwd)/data/eh_ingest_cache:/app/runtime/eh_ingest_cache" \
  autoeh-data:local shell -lc "sleep infinity"
```

Data UI（同镜像独立服务）：

```bash
docker run -d \
  --name autoeh-data-ui \
  --restart unless-stopped \
  --env-file data/.env \
  -p 8501:8501 \
  -v "$(pwd)/data/runtime:/app/runtime" \
  -v "$(pwd)/data/eh_ingest_cache:/app/runtime/eh_ingest_cache" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  autoeh-data:local data-ui
```

说明：Data UI 支持手动触发 compute 侧脚本（`run_worker.sh` / `run_eh_ingest.sh` / `run_daily.sh`）
以及定时执行 `run_daily.sh`。需确保 `COMPUTE_CONTAINER_NAME` 与实际容器名一致。

## 5) 运行日常任务

在 Data 容器执行：

```bash
docker exec -it autoeh-data /app/ehCrawler/run_eh_fetch.sh
docker exec -it autoeh-data /app/lrrDataFlush/run_daily_lrr_export.sh
docker exec -it autoeh-data /app/textIngest/run_daily_text_ingest.sh
```

在 Compute 容器执行：

```bash
docker exec -it autoeh-compute /app/vectorIngest/run_worker.sh --limit 20 --only-missing
docker exec -it autoeh-compute /app/vectorIngest/run_eh_ingest.sh
docker exec -it autoeh-compute /app/vectorIngest/run_daily.sh
```

## 5.1) Data UI（Streamlit）能力

- Dashboard：库规模、最近抓取时间、LRR/Compute/LLM 健康状态
- Control：手动触发 Data/Compute 侧任务（含 `run_worker`、`run_eh_ingest`、`run_daily`）
- Scheduler：定时触发 Data 侧流程与 Compute `run_daily`
- Audit：任务运行历史 + 日志预览
- XP Map：基于阅读记录标签的聚类可视化（PCA 2D）

## 6) 跨容器 EH 队列共享（关键）

Data 与 Compute 必须共享同一宿主目录并映射到容器内同一路径：

- 宿主机：`./data/eh_ingest_cache` 与 `./compute/eh_ingest_cache` 可指向同一实际目录（推荐软链接或统一挂载）
- 容器内统一：`/app/runtime/eh_ingest_cache`

并保证：

- Data 写：`EH_QUEUE_FILE=/app/runtime/eh_ingest_cache/eh_gallery_queue.txt`
- Compute 读：`EH_QUEUE_FILE=/app/runtime/eh_ingest_cache/eh_gallery_queue.txt`

**⚠️ 警告：`eh_ingest_cache` 共享目录绝对不能配置错。**
**⚠️ 一旦 Data 写入目录与 Compute 读取目录不一致，EH 增量抓取 -> 入库闭环会直接断开。**

## 网络拓扑（Split 部署）

- 支持存算分离：`Data` 与 `Compute` 可以部署在不同机器
- 需要确保以下网络连通性：
  - Data -> PostgreSQL
  - Compute -> PostgreSQL
  - Compute -> OpenAI 兼容后端（LLM / Embedding / VLM）
  - n8n -> hunterAgent（compute）
  - Data UI -> Compute（health）
- 若跨机器，优先使用固定内网 IP + 明确端口映射，避免容器名解析依赖

## 重要环境变量

### Data 容器（`Docker/data/.env`）

- 数据库
  - `POSTGRES_DSN`
  - `DB_INIT_ON_START` / `DB_INIT_SCHEMA` / `DB_INIT_LOG`
- LRR 导出
  - `LRR_HOST` / `LRR_PORT` / `LRR_SCHEME` / `LRR_API_KEY`
  - `LRR_METADATA_OUT` / `LRR_READS_OUT` / `LRR_READS_HOURS`
- EH 抓取
  - `EH_COOKIE` / `EH_QUEUE_FILE` / `EH_STATE_FILE`
- Text Ingest
  - `TEXT_INGEST_INPUT` / `TEXT_INGEST_PRUNE_NOT_SEEN` / `TEXT_INGEST_MIN_FULL_BYTES`
- Data UI
  - `DATA_UI_PORT` / `DATA_UI_RUNTIME_DIR`
  - `COMPUTE_HEALTH_URL` / `COMPUTE_CONTAINER_NAME`

### Compute 容器（`Docker/compute/.env`）

- 数据库与 LRR
  - `POSTGRES_DSN`
  - `LRR_BASE` / `LRR_API_KEY`
- OpenAI 兼容接口
  - `LLM_API_BASE` / `LLM_MODEL` / `LLM_API_KEY`
  - `EMB_API_BASE` / `EMB_MODEL` / `EMB_API_KEY`
  - `VL_BASE` / `VL_MODEL_ID`
- SigLIP
  - `SIGLIP_MODEL` / `SIGLIP_DEVICE`
- EH 入库
  - `EH_QUEUE_FILE` / `EH_API_URL` / `EH_COOKIE`

## 7) Companion 说明

- `Companion/n8nWorkflows/` 提供工作流模板，不是 Docker 镜像的一部分。
- 导入 n8n 前请替换占位符：
  - `{your_bot_token}`
  - `{your_openai_url:port}`
  - `{your_hunterAgent_url:port}`
- 工作流名称已对齐为 `hunterAgent_sub`。

## 常见问题（踩坑记录）

- `docker compose` 不可用（Unraid 常见）
  - 现象：`docker: 'compose' is not a docker command`
  - 处理：用本 README 的纯 `docker build/run/exec` 流程。

- `run_daily_lrr_export.sh` 报输出路径异常或花括号错误
  - 现象：`Single '}' encountered in format string` / 文件名出现 `}.jsonl`
  - 处理：已改为安全替换逻辑；仍建议检查 `LRR_READS_OUT` 格式。

- 24h 阅读导出为 0
  - 原因：LRR `lastread` 排序方向与直觉可能相反，已按当前项目实践处理。
  - 建议：若异常，直接调用 `/api/search` 验证 `sortby=lastread` + `order` 行为后再调整。

- Data 容器首次导出报目录不存在
  - 处理：导出脚本已补目录自动创建；确保挂载目录存在且可写。

- 首次启动 schema 初始化失败
  - 查看：`/app/runtime/logs/db_init.log`
  - 常见原因：`POSTGRES_DSN` 错误、数据库未启动、网络不可达。

- `text-ingest-daily` 误删风险
  - 已有防护：默认 `prune` 开启，但仅当 `FULL_JSONL` 存在且大于 `TEXT_INGEST_MIN_FULL_BYTES`（默认 500KB）才会执行。

- 搜图/向量接口地址统一时 404
  - 注意 `hunterAgent` 与 worker 的 base URL 拼接规则可能不同；不要盲目统一为同一字符串（是否带 `/v1` 要按脚本约定）。

- Telegram 输出出现 thinking 内容
  - 建议：工作流使用 instruct/chat 模型；避免 reasoning/thinking 直接透传。

## 安全与发布建议

- 推 GitHub 前二次检查：
  - 无 `.env` 实文件
  - 无 Bot Token/API Key/私网地址硬编码
  - n8n 工作流 `pinData` 为空
- 密钥一律使用环境变量注入，且定期轮换。
- 建议先 private repo 试跑 1-2 轮，再公开。

## 后续可选增强

- 搜索增强：接入 OCR（内页文本提取）提升对白/剧情向检索召回
- 搜索增强：接入 WD14 Tagger（看社区反馈决定默认开关）补充视觉标签语义
- 入库增强：接入 ESRGAN / Anime4K 自动超分后再做特征抽取（可选 pipeline）/自动高清入库
- 运营增强：A/B 对比不同模型与提示词模板，沉淀可回滚的 prompt 版本策略
- 工程增强：增加 CI（JSON 校验、shellcheck、敏感信息扫描）与发布前自动检查

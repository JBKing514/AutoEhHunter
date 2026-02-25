# AutoEhHunter 快速启动指南

> 🌐 语言 / Language: [中文](STARTUP.md) | [English](STARTUP_EN.md)

## 0. 前提条件

* **Docker 环境**：推荐 Docker Desktop / Docker Engine (v27+)。
* **OpenAI 兼容后端（可选）**：支持 `/v1` 接口（LM Studio / vLLM / Ollama兼容层等）。
* **说明**：LLM 连接是可选项；未配置时系统仍可运行基础链路。

## 1. 基础步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/JBKing514/AutoEhHunter.git
   cd AutoEhHunter
   ```

2. **快速模板启动（推荐）**
   ```bash
   docker compose -f Docker/quick_deploy_docker-compose.yml up -d
   ```

   该模板会拉起：`pg17`、`lanraragi`、`data-ui`。
   无需将目录名从 `main` 重命名为 `data`，当前 Compose 与 Dockerfile 已统一使用 `Docker/main`。

3. **访问 WebUI**
   * 浏览器打开 `http://<host>:8501`。
   * 在 `Settings` 里配置 PostgreSQL/LRR 以及模型端点。

## 2. 手动分步部署（可选）

适用于想逐个拉起容器或跨机部署：

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

## 3. 首次初始化 (关键步骤)

在 `Control` 页面建议依次执行：

1. `[立即爬取 EH]`
2. `[导出 LRR]`
3. `[文本入库]`
4. `[LRR入库]`
5. `[EH入库]`（可选）

> 日常维护推荐使用 `EH+LRR入库` 定时任务。

## 4. 模型连接策略

* **单端点模式**：一个 `/v1` 同时承担 VL + Embedding + LLM。
* **双端点模式**：
  * `INGEST_API_BASE` 用于入库（VL/Embedding）
  * `LLM_API_BASE` 用于聊天/叙事（可接更大模型）
* **不配置 LLM**：基础检索与数据链路可用，智能叙事与自然语言增强不可用。

## 5. 运行建议

* EH 抓取：每 10~30 分钟
* 入库：每天 1 次（按增量可缩短）
* CPU-only 默认可用，首轮全量入库耗时更长

## 6. 配置备份（新增）

在 `Settings -> General -> 危险区域` 中可下载/恢复运行时 `app_config.json`：

* 下载：导出当前运行时 JSON 备份
* 恢复：上传本地 `app_config.json` 覆盖运行时文件（**不会修改数据库 app_config**）

# AutoEhHunter 快速启动

> 🌐 语言 / Language: [中文](STARTUP.md) | [English](STARTUP_EN.md)

## 0. 前提

- Docker Desktop / Docker Engine（推荐 27+）
- （可选）OpenAI-compatible `/v1` 模型服务

## 1. 快速模板启动（推荐）

```bash
git clone https://github.com/JBKing514/AutoEhHunter.git
cd AutoEhHunter
docker compose -f Docker/quick_deploy_docker-compose.yml up -d
```

快速模板会拉起：

- `pg17`（PostgreSQL + pgvector）
- `lanraragi`
- `data-ui`（WebUI + API + 调度 + 聊天）

> 不再强制先写 `.env`。启动后可直接在 WebUI 配置。

## 2. 手动模板分步启动（可选）

如果你希望逐个组件控制，使用以下模板：

1. PostgreSQL

```bash
docker compose -f Docker/pg17_docker-compose.yml up -d
```

2. LANraragi

```bash
docker compose -f Docker/lanraragi_docker-compose.yml up -d
```

3. Data 服务

```bash
docker compose -f Docker/main_docker-compose.yml up -d
```

## 3. 首次进入 WebUI

- 访问：`http://<host>:8501`
- 在 `Settings` 中完成：
  - PostgreSQL / LANraragi 参数
  - `INGEST_API_BASE` + 模型（可选）
  - `LLM_API_BASE` + 模型（可选）

## 4. 初始化任务顺序

建议在 `Control` 页按顺序执行：

1. `立即爬取 EH`
2. `导出 LRR`
3. `文本入库`
4. `LRR入库`
5. `EH入库`（可选）

日常建议用 `EH+LRR入库` 定时任务。

## 5. 模型连接说明

- **单端点模式**：一个 `/v1` 同时承担 VL/Embedding/LLM。
- **双端点模式**：
  - `INGEST_API_BASE`（入库）
  - `LLM_API_BASE`（聊天与叙事）
- **不配置 LLM 也可运行**：基础检索与数据链路可用；自然语言增强能力会受限。

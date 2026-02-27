# AutoEhHunter 快速启动指南

> 🌐 语言 / Language: [中文](STARTUP.md) | [English](STARTUP_EN.md)

## 0. 前提条件

* **Docker 环境**：推荐 Docker Desktop / Docker Engine (v27+)。
* **OpenAI 兼容后端（可选）**：支持 `/v1` 接口（LM Studio / vLLM / Ollama兼容层等），用于驱动多模态模型的描述生成、Agent 路由及文本增强检索。
* **说明**：LLM 连接是可选项；未配置时系统仍可运行基于 SigLIP 的视觉检索、聚类推荐及基础的数据链路。

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

   该模板会拉起：`pg17`、`lanraragi`、`main`。
   当前所有的后端 API、Agent、定时任务与 WebUI 都已经统一收束进了 `Docker/main` 容器中。

3. **访问 WebUI**
   * 浏览器打开 `http://<host>:8501`。
   * **首次进入时，系统将引导您进入 Setup Wizard（初始化向导）**，您只需在 Web 界面中无缝完成数据库连接、建立首个管理员账号、绑定 LRR / EH 凭据即可，**无需手动修改任何 `.env` 文件**。

## 2. 手动分步部署（可选）

适用于想逐个拉起容器或跨机部署的场景：

1. PostgreSQL (需带有 `pgvector` 扩展)
   ```bash
   docker compose -f Docker/pg17_docker-compose.yml up -d
   ```

2. LANraragi
   ```bash
   docker compose -f Docker/lanraragi_docker-compose.yml up -d
   ```

3. AutoEhHunter (核心服务)
   ```bash
   docker compose -f Docker/main_docker-compose.yml up -d
   ```

## 3. 首次初始化与数据同步

完成 Setup Wizard（初始设置向导） 后，在 `Control`（控制台）页面建议依次执行以下操作，以建立基础的向量索引和数据基线：

1. `[立刻爬取 E-Hentai]` (全量拉取)
2. `[E-Hentai筛选数据入库]`（推荐功能此时可用，调用SigLIP计算封面向量需要一定时间）
3. `[导出画廊数据以及历史记录]`
4. `[画廊数据以及历史记录入库]`
5. `[画廊数据向量化]`（需要配置VL模型，否则会退回SigLIP-Only模式，自然语言检索精度会下降）

> 日常维护推荐使用系统内置的 **Schedule（定时任务）** 页面配置自动入库和导出。更详细的爬虫筛选规则可在配置页面设置，标签支持模糊匹配，也可回车输入库内暂时没有的标签。
> 为了实现最完整的数据闭环，我们强烈建议安装`Companion/lrrMihonExtentionHistory`中的LANraragi定制脚本，该脚本通过调用LRR API来将阅读记录上报给LRR。本仓库的插件仅为单次Fork，不会随上游频繁更新，请勿在本仓库提交相关PR。

## 4. 模型连接策略

本系统针对大语言模型和 Embedding 提供了高自由度的路由配置（均可在 `Settings` 页面动态修改）：

* **单端点模式**：配置一个强大的 `/v1` 端点（如大型 vLLM 实例），同时承担 图像描述生成(VL) + 语义向量(Embedding) + 对话交互(LLM)。
* **双端点/多端点模式**：
  * `INGEST_API_BASE` (入库通道)：专用于画廊的元数据与图像清洗（VL/Embedding），可配置专用的轻量化模型。
  * `LLM_API_BASE` (交互通道)：用于 Agent 聊天、XP 解析报告、搜索意图路由（可对接其他本地高智商闭源模型）。
* **最小实践建议**：：一个`/v1` 端点（Ollama，LM Studio等）装载一个4B VL模型+BGE-M3, 模型规模本身没有限制，但太小的模型可能会生成不准确的视觉描述，和低质量的Agent生成文本，请自行斟酌。
* **内置 SigLIP**：视觉特征向量（Image-to-Image / Text-to-Image 核心）由本容器 `main` 内部直接加载模型运行，支持 0 配置自动下载热身，可随时清理释放内存。
* **注意事项**：基于本项目数据的敏感性，不建议使用云端API，且带审查模型（非abliterated模型）可能会频繁触发安全限制，影响VL入库文本描述精度和Agent性格

## 5. 运行建议

* EH 抓取频率：建议每 15~30 分钟。
* EH 筛选入库频率：建议每 1 小时一次。
* LRR 数据导出及向量入库频率：建议每天 1 次。
* 系统默认使用 CPU 运行 SigLIP 模型，因此首轮全量入库（几十上万本）耗时可能会较长，但日常增量入库毫无压力。考虑到引入ROCm，CUDA等图形加速依赖带来的复杂性，暂时不考虑使用GPU硬件加速，但可以尝试通过修改`Docker/main/requirements.txt`和环境变量来强制使用GPU，为此不提供技术支持。
* 如果在LANraragi的元数据获取上遇到困难，请使用`Companion/lrrMetadataPlugin`中的增强型元数据脚本

## 6. Sudo 提权与灾难恢复

考虑到配置统一由数据库管理，本系统设计了完善的容灾机制：

* **Sudo 锁**：在 `Settings -> General` 中修改数据库连接等危险操作时，强制要求验证当前用户的登录密码解锁。
* **配置备份**：
  * 在危险区域内可一键**下载运行时 `app_config.json` 备份**。
  * 若因数据库迁徙导致配置丢失，可在此处**上传恢复**。
* **急救码 (Recovery Codes)**：系统在初始化/重置时会生成并在日志中打印 10 个用后即焚的恢复密钥（SHA256 保存）。当您忘记密码或不慎修改错了数据库 IP 导致无法登录时，可在登录页面使用任意一条急救码进入“恢复模式（Recovery Mode）”以强制纠正配置并重置管理员密码。

## 7. 网络配置建议

容器支持配置简单的 HTTP/HTTPS 代理，但由于网络环境的复杂性，仍强烈建议使用 VPN 容器（如 Gluetun 等），通过将容器网络连接到 VPN 容器（例如在 `docker-compose.yml` 中使用 `network_mode: "container:<gluetun_container_name>"`，并开启 Gluetun 容器的端口转发），或使用独立的 `macvlan` / `ipvlan` 网络方式运行，以保证系统爬虫与图库通讯的稳定性。

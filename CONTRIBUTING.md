# 贡献指南 (Contribution Guide)

> 🌐 语言 / Language: [中文](CONTRIBUTING.md) | [English](CONTRIBUTING_EN.md)

感谢您有兴趣为 **AutoEhHunter** 做出贡献！

本项目已经从一个简单的自动化脚本，演进为一个包含视觉大模型、推荐算法、多模态混合检索以及现代化前端的复杂 RAG 系统。我们非常欢迎那些有着同样**“工程强迫症”**的开发者加入，共同打磨这个本地部署的数字资产治理中枢。

---

## 架构哲学与开发准则 (Philosophy)

在提交任何代码之前，请理解本项目的核心开发哲学：

1. **严谨的数学与逻辑把控**：
   本项目的核心代码深度融合了 AI 辅助编程（"Vibe Coding"）。但我们有着极其严格的人工审查标准。任何涉及推荐算法（如能量重排序）、XP 聚类（KDE、PCA）修改的 PR，**请在描述中给出推导过程或数学原理**。不要提交连你自己都解释不清楚的 AI 生成代码。
2. **零配置冷启动 (Zero-Config Cold Start)**：
   我们极其看重用户的部署体验。任何新功能的引入，**绝对不允许**增加强制性的 `.env` 环境变量要求。所有的配置项必须收敛于 WebUI 的 Setup Wizard（初始向导）和数据库 `app_config` 表中。
3. **安全至上 (Security First)**：
   系统处理着高度隐私的本地数据。请不要为了方便而妥协安全性。我们坚持：
   * 零外部无鉴权 HTTP API 端口（全部转为进程内 Worker 调用）。
   * 严格的防 CSRF 机制（双提交 Cookie + SameSite=Strict）。
   * 敏感操作必须接入全局 Sudo 二次鉴权锁。
4. **极致的前端优雅**：
   对于 UI/UX 的修改，我们追求媲美商业软件的平滑感（如 Apple 风格的流体高斯模糊缩放、幽灵加载机制）。拒绝生硬的 DOM 跳变和阻塞主线程的同步请求。

---

## 重点欢迎贡献的领域 (Where We Need Help)

虽然系统框架已经稳定，但在以下几个深水区，我们依然需要社区的智慧：

### 1. 算法与推荐引擎 (Algorithms & RAG)
* **混合检索权重调优**：目前视觉（SigLIP）、语义（BGE-M3）与元数据的 RRF (Reciprocal Rank Fusion) 权重基于经验设定，欢迎提出更科学的动态权重分配策略。
* **推荐势能模型**：本项目目前使用基于物理启发的势能模型与玻尔兹曼分布进行推荐，结合了**交互衰减（Touch/Impression Penalties）**与**热噪音（Thermal Jitter）**来引入探索性。我们**不使用**粗暴的线性时间衰减（Time Decay）。欢迎各位在此基础上研究兴趣漂移（Concept Drift）的检测机制，或是对多势能场（标签、视觉、长期画像）的归一化权重提出更优雅的数学调优方案。

### 2. 前端与交互体验 (Frontend & UI/UX)
* **技术栈**: Vue 3 (Composition API), Pinia, Vuetify
* **优化方向**：移动端手势优化（如滑动返回、瀑布流防误触）、PWA 深度集成、更高级的 CSS 物理缓行动画。

### 3. 数据治理与鲁棒爬虫 (Data Pipeline & Scrapers)
* **技术栈**: Python 3.11, HTTPX, requests
* **优化方向**：增强 E-Hentai/ExHentai 的元数据解析正则；完善各种极端网络环境下的自动退避与轮询重试机制（目前已实现基础的异步幽灵加载与多 CDN 轮询，但仍有调优空间）。
* **LANraragi 插件**：完善定制化 Mihon 插件的历史记录上报逻辑，目前仅在打开画廊时会触发汇报，无法记录阅读时间长度，页数等详细信息。

### 4. 大模型集成 (LLM & VL Integration)
* **API 与硬件配置隔离**：在架构上，我们严格区分了**视觉语言模型 (Vision-Language, VL)** 与**标准大语言模型 (LLM)** 的调用链路与端点配置。VL 模型（如图片打标分析）与纯文本 LLM（如摘要生成）在 API 速率、并发成本和硬件要求上截然不同。新增功能时，请务必保证两者配置独立，并在文档中阐明不同的硬件/API 需求。
* **Prompt 动态管理**：所有核心 System Prompt 均已从硬编码迁移至统一的配置流。新增或调优 Prompt 时，请集中在 `constants.py`（默认值）与数据库表进行映射，确保用户可以在 WebUI 中即时热重载，禁止在业务 Worker 中写入魔法字符串。
* **VL模型语义描述生成**：当前VL提示词主要面向单图特征描述而非整体剧情梳理，可以继续完善图像输入并添加剧情描述字段，系统提示词以实现更精准的语义描述，提高自然语言检索的准确性

---

## 本地开发环境设置 (Development Setup)

项目采用前后端同源的单体架构（前端打包后由 FastAPI 托管），在本地开发时可以拆分开来。

1. **基础设施部署**：
   您需要一个包含 `pgvector` 的 PostgreSQL 数据库。推荐使用项目提供的 `docker-compose.example.yml` 仅启动 `db` 服务。
2. **后端 (FastAPI)**：
   ```bash
   cd main
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   # 启动后端服务 (默认监听 8501)
   uvicorn webapi.main:app --reload --port 8501
   ```
3. **前端 (Vue 3)**：
   ```bash
   cd main/webui
   npm install
   # 启动 Vite 开发服务器 (自带 HMR)
   npm run dev
   ```
   *注意：需要在前端的 `vite.config.js` 中配置 proxy，将 `/api` 请求代理到你本地的 FastAPI 端口，以保持严格的同源策略。*

---

## 提交 PR 的自测清单 (Pull Request Checklist)

在发起 Pull Request 之前，请核对以下项目：

* [ ] **代码格式**：Python 代码是否符合 `black` 和 `isort` 规范？是否添加了必要的 Type Hint？
* [ ] **冷启动测试**：彻底清空数据库，在没有任何旧配置的情况下，是否能正常唤起 WebUI 的 Setup Wizard 并顺畅完成初始化？
* [ ] **安全边界测试**：是否引入了需要跨域访问的接口？如果添加了新的 API，是否正确接入了 `app.authUser` 依赖与鉴权中间件？
* [ ] **异常捕获**：是否有可能会导致 FastAPI 主线程（Threadpool Exhaustion）假死的阻塞操作（如大文件同步下载）？请务必使用 `anyio` 抛至后台或使用 `httpx.AsyncClient`。

无论您提交的是修复一个小 Bug，还是引入了一个复杂的统计算法，我们都由衷地感谢您对 AutoEhHunter 的支持！
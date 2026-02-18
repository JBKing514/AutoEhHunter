# AutoEhHunter

### 面向 E-Hentai 与 LANraragi 的私有化多模态 RAG 智能体

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/) [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/) [![Architecture](https://img.shields.io/badge/Architecture-Split%20Plane-purple)](docs/ARCHITECTURE.md)

<p align="center">
  <img src="https://github.com/JBKing514/autoEhHunter/blob/main/Media/ico/AutoEhHunterLogo_256.png" width="256" alt="AutoEhHunter_Ico">
  <br>
  <em>Project Logo</em>
</p>

## 开发初衷 (Motivation)

**“为什么我记得封面长什么样，记得剧情，却因为想不起那个该死的 Tag / 标题 而找不到那本书？”**

AutoEhHunter 诞生于对现有 E-Hentai 和 LANraragi 搜索机制的深深沮丧。传统的基于关键词和布尔逻辑的检索系统，本质上是反人类的——它要求用户像数据库一样思考，必须精确命中元数据才能获得反馈。

但人类的欲望是模糊的、感性的、视觉主导的。

我开发 **AutoEhHunter** 的初衷，就是为了打破这种认知的隔阂。我想构建一个不是让我去“搜 Tag”，而是能听懂我说“找点这种感觉的”或者“最近想看点重口的”系统。它不应该只是一个冷冰冰的归档工具，而应该是一个能理解画面、读懂剧情、甚至比我更懂我自己 XP 的**战术副官**。

## 项目概览 (Overview)

**AutoEhHunter** 是一个自主认知智能体，作为 **私有化 RAG (检索增强生成) 系统** 运行。它将您的本地库和外部 EH 数据库视为一个高维向量空间，利用 **SigLIP** 进行视觉理解，并配合 **LLM Agents** 进行语义推理，将被动的“浏览”转化为主动的、智能化的“战术交互”。

> **"停止搜索。开始对齐。"**

## 系统架构 (Architecture)

<p align="center">
  <img src="/Media/diagram/AutoEhHunter_Diagram_ZH.png" width="800" alt="AutoEhHunter_Diagram_ZH">
  <br>
  <em>AutoEhHunter架构图</em>
</p>

系统采用 **分离平面架构 (Split-Plane Architecture)**，将重型计算与持久化存储解耦。

| 平面 (Plane) | 组件 (Component) | 职责 | 技术栈 |
| :--- | :--- | :--- | :--- |
| **控制面 (Control)** | **Agent** | 意图识别、人格渲染、工作流编排。 | **n8n**, Telegram Bot API, LLM |
| **算力面 (Cortex)** | **Compute** | 视觉嵌入 (SigLIP)、向量索引构建、XP 聚类分析。 | **PyTorch**, SigLIP, Scikit-learn，VL视觉模型 |
| **数据面 (Logistics)** | **Data** | 漏斗爬虫、元数据清洗、持久化存储。 | **PostgreSQL** (pgvector), LANraragi |

## 核心特性 (Core Features)

### 1. 多模态语义检索
* **视觉搜索**：上传一张图片，系统基于 SigLIP 寻找构图、画风或特征相似的作品。
* **混合查询**：支持复杂的自然语言指令，如“找一些画风像某画师但剧情纯爱的作品”。
* **影子库 (Shadow Library)**：在下载之前，即可调用爬虫针对外部 E-Hentai 进行爬取入库后进行深度向量检索。

### 2. 生态闭环与数据工程
AutoEhHunter 不仅仅是一个搜索器，更是一整套数据治理方案：
* **漏斗式 EH 爬虫 (Funnel Crawler)**：
    * 采用“轻量级元数据抓取 -> 规则过滤 -> 算力入库”的漏斗机制。
    * 仅对符合您 Rating/Tag 偏好的作品调用 GPU 算力，极大降低计算负载。
* **Mihon 定制 LANraragi 插件**：
    * 修改版 Mihon (Tachiyomi) 扩展，支持调用 LANraragi API 回传阅读记录。
    * 无论是在 PC 还是手机阅读，您的 XP 行为数据都会回流至系统，用于修正推荐算法。
* **增强型 Ehentai.pm 插件**：
    * 深度改造 LANraragi 内置插件，支持从 `metadata`, `comicinfo.xml`, `ehviewer` 等多种来源提取元数据。
    * 内置 EH API 回落机制与**中文标签自动翻译**，确保元数据的一致性与可读性。

### 3. XP 聚类驱动的推荐机制
* **XP 地图**：将您的阅读历史可视化为高维簇的 2D 投影。
* **漂移检测**：Agent 会监控您的阅读习惯，并生成报告分析您的偏好演变。
* **智能截击**：利用 K-Means 聚类锁定您的“好球区”向量，自动拦截数学上与您口味对齐的新上传资源。

### 4. 战术副官（Agent）
* **叙事报告**：拒绝枯燥的 JSON。获取由“赛博副官”撰写的日报/周报，风格毒舌且切中要害。
* **情境感知**：能够理解“帮我找某本特定的书”与“我无聊了，推点东西”之间的区别。

## 容器规格与资源需求 (Requirements)

本项目采用微服务设计，您可以根据硬件条件灵活部署。

### `data` 容器 (数据面)
* **定位**：常驻运行，负责爬虫、数据库与 Web UI。
* **资源要求**：极低。`RAM < 512MB` 即可稳定运行。
* **镜像体积**：约 `1.1GB`。
* **建议部署**：NAS、树莓派或低功耗服务器。

### `compute` 容器 (算力面)
* **定位**：按需或常驻，负责 SigLIP 视觉嵌入与向量计算。
* **CPU 模式**：
    * 默认兼容模式。
    * **推荐**：`8` 核以上 CPU，否则向量入库与搜图速度会明显变慢。
* **GPU 加速 (可选)**：
    * 支持 CUDA 加速，需自行处理 PyTorch 版本兼容性。
    * **特别提示**：对于 NVIDIA **RTX 50 系列 / Blackwell** 架构显卡，通常需要手动安装最新的 PyTorch Nightly 版本，并在环境变量中显式启用 GPU。
* **镜像体积**：约 `8.0GB` (包含 PyTorch 与预训练模型)。

## 模型架构与配置策略 (Model Architecture)

AutoEhHunter 采用 **"专人专用" (Specialized Models)** 的策略来平衡性能与显存开销。虽然项目支持任意 OpenAI 兼容后端，但为了确保数据库 Schema 兼容性和最佳体验，请遵循以下配置规范。

> **⚠️ 关于内容合规性 (Content Safety)**：
> 鉴于本项目处理的数据性质（包含大量 NSFW 内容），标准商业模型或过度对齐的模型可能会频繁触发拒绝机制。
> **强烈建议** 采用本地部署的 **Abliterated (去审查)** 或 **Uncensored (无限制)** 版本模型，以确保视觉描述和角色扮演功能的稳定性。

### 1. 文本嵌入模型 (Embedding Model) - **必选**
* **指定模型**: `BAAI/bge-m3`
* **硬性约束**: **必须使用此模型**（或输出维度为 `1024` 的同类模型）。
* **原因**: 数据库 Schema 中 `desc_embedding` 字段被硬编码为 `vector(1024)`。
    * *反例*: 如果使用 OpenAI `text-embedding-3-small` (1536 dim) 或 `bge-large` (1024 dim)，请务必确认维度匹配，否则入库会报错。
    * `bge-m3` 在多语言（中日韩）语义检索上具有 SOTA 级别的表现，完美契合 EH 的多语言环境。

### 2. 视觉-语言模型 (VLM) - **必选**
* **用途**: 为本地库的图片生成高质量的“自然语言描述”，用于补充 Tag 无法覆盖的语义（如“构图”、“氛围”、“剧情推测”）。
* **推荐配置**:
    * **均衡型 (开发环境基准)**: `Huihui-Qwen3-VL-8B-Instruct-abliterated` (或其他 Qwen2.5/3-VL 衍生版)。
        * *特点*: 速度快，描述准确，且经 Abliteration 处理后不会回避对敏感画面的描述。
    * **高配型**: `Qwen2.5-VL-72B` 或 `Llama-3.2-90B-Vision`。
        * *特点*: 提供更文学化、细节更丰富的描述，适合追求极致检索精度的用户。
    * **All-in-One**: 控制面的大模型（如 30B+ VLM）也可兼任此职，但需精调 Prompt 以防止模型在描述时产生幻觉或过度发散。

### 3. 控制面大模型 (Agent LLM) - **核心**
* **用途**: 意图识别 (Router) 与 最终叙事渲染 (NLG)。
* **推荐配置**:
    * **最佳体验**: `Qwen3-Next-80B-A3B-Instruct` (开发时选择量化: IQ4_XS)。
        * **特化适配**: 本项目 Prompt 针对 Qwen 系列的指令遵循能力与中文语感进行了深度调优。
        * **沉浸感**: 80B 级别的大参数模型能提供远超小模型的“战术副官”扮演体验。
        * **实测表现**: 在开发测试中，该模型的原生 Instruct 版本对 System Prompt 的依从性极高，**极少拒绝用户的敏感请求**，因此通常无需寻找专门的 Abliterated 版本即可获得稳定的输出。
    * **最低要求**: `7B` 以上参数量的 Instruct/Chat 模型。
        * *警告*: 过小的模型可能无法严格遵循 JSON 输出格式，导致意图识别失败并回退到默认的关键词搜索模式。Thinking模型暂不支持，目前Skill无法提取Context字段。
  
---

### 提示词工程与本地化 (Prompt Engineering & Localization)

本项目的 Agent 核心逻辑（意图识别与叙事渲染）深度依赖于 **Prompt Engineering**。目前的提示词库存在以下限制：

* **基准模型绑定**: 所有 System Prompts 均针对 **`Qwen3-Next-80B-A3B-Instruct`** 的指令遵循范式与 Attention 偏好进行了微调。
    * **风险**: 使用其他模型架构（如 Llama-3, DeepSeek）或较小参数模型时，可能会出现 **JSON 输出格式错误**（导致 Router 崩溃）或 **角色扮演风格崩坏**（无限复读）。
* **语言适配**: 当前版本仅针对 **简体中文** 环境进行了深度优化。
    * 其他语言（英语、日语）的指令可能会被模型误解，或导致回复中出现中英夹杂的情况。
    * **n8n 硬编码**: n8n 工作流中的部分兜底回复（Fallback Responses）目前为简体中文硬编码，亟待本地化 (i18n) 改造。

#### 贡献指南
我们热烈欢迎社区贡献针对其他主流模型（如 `Llama-3.1-70B`, `DeepSeek-V3`）或多语言环境（English/Japanese）的 Prompt 适配方案。

如果您有意提交 PR，请务必参考 [**CONTRIBUTING.md**](CONTRIBUTING.md) 中的 **[提示词示例]**。
* **硬性指标**: 任何 Prompt 修改必须通过 `Intent Classifier` 的 **JSON 结构稳定性测试**，确保在 `temperature=0` 时能 100% 输出符合 Schema 的标准 JSON，以保障系统核心功能的鲁棒性。

---

## 快速开始 (Getting Started)

AutoEhHunter 专为 Docker 环境设计。

* **[快速启动指南 (STARTUP.md)](STARTUP.md)** - *5分钟内部署您的私人 Agent*
* **[data容器详细配置参考](Docker/data/README.md)** - *进阶容器说明*
* **[compute容器详细配置参考](Docker/compute/README.md)** - *进阶容器说明*
* n8n，LANraragi，pgvector相关配置参考，请参考相关项目文档
* 

## 配置与持久化说明

- 首次部署建议先完整填写 `Docker/data/.env` 与 `Docker/compute/.env`。
- 部署后可通过 Data UI 的 `Settings` 页面在线修改核心配置，保存后立即生效，通常无需重建容器。
- 配置优先级：`app_config(DB) > JSON fallback > .env`。
- Secrets/token 以可逆加密形式存入 `app_config`；当前无密钥轮换功能。
- 若密钥文件丢失，历史密文无法解密，需要在 WebUI 重新填写密码与 token 并保存一次。
- 当前架构下，Data 与 Compute 之间不再依赖共享队列目录；EH URL 通过 PostgreSQL 表 `eh_queue` 传递。
- 仍需保留各容器运行时持久化目录（例如 runtime、数据库卷、n8n数据卷）。

## 技术栈 (Technology Stack)

* **向量数据库**: PostgreSQL 17 + `pgvector`
* **视觉模型**: Google `SigLIP-SO400M`, Qwen系列VL模型
* **编排引擎**: n8n (Workflow Automation)
* **移动端**: Mihon (Android) + Custom LANraragi Plugin
* **后端框架**: FastAPI (Python 3.10)，OpenAI兼容后端

## 免责声明 (Disclaimer)

本工具仅供 **信息检索研究与个人归档** 使用。用户需对使用本软件访问、下载或存储的所有内容承担全部责任。请务必遵守您所访问的任何外部网站的服务条款 (ToS)。

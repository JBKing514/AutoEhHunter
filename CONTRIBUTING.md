# 贡献指南

> 🌐 语言 / Language: [中文](CONTRIBUTING.md) | [English](CONTRIBUTING_EN.md)

感谢你为 AutoEhHunter 贡献代码！

## 贡献方向

- 检索质量（权重、召回策略、语言适配）
- Agent 技能与插件生态
- WebUI 交互体验
- 文档与部署体验

## 开发原则

- 以 `data` 容器为主链路（当前主架构）。
- 新能力优先通过 Settings 可配置，避免硬编码。
- 保持“LLM 可选”：未配置 LLM 时基础功能不应崩溃。

## Prompt 调试（当前推荐方式）

现在可以直接在容器内快速验证提示词，不需要额外编排器：

1. 启动容器并打开 WebUI。
2. 在 `Settings -> LLM` 修改以下字段：
   - `PROMPT_SEARCH_NARRATIVE_SYSTEM`
   - `PROMPT_PROFILE_SYSTEM`
   - `PROMPT_REPORT_SYSTEM`
   - `PROMPT_TAG_EXTRACT_SYSTEM`
3. 保存后立即在聊天/搜索中验证效果。

## 技能与插件规范

- 内置技能放在：`Docker/data/hunterAgent/skills/builtin/`
- 注册表：`Docker/data/hunterAgent/skills/registry.py`
- 插件目录：`/app/runtime/webui/plugins`（WebUI 支持上传）
- 插件请使用统一上下文 `SkillContext`，不要自行重复构造底层连接。

## 提交前检查

- Python：`python -m py_compile` 覆盖你修改的模块
- 前端：确保 `App.vue` 与 i18n JSON 语法正确
- 文档：中英文文档保持同步更新
- 若修改检索逻辑，请至少验证：
  - 中文 UI + 中文 tag
  - 英文 UI + 英文 tag
  - 标签硬过滤开/关两种模式

## PR 建议内容

- 改动动机（为什么）
- 关键设计点（怎么做）
- 验证结果（如何确认生效）
- 兼容性说明（是否影响无 LLM 模式）

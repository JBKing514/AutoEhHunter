# Contribution Guide

> 🌐 Language / 语言: [English](CONTRIBUTING_EN.md) | [中文](CONTRIBUTING.md)

Thanks for contributing to AutoEhHunter!

## Contribution Areas

- Retrieval quality (weights, recall strategy, language robustness)
- Agent skills and plugin ecosystem
- WebUI interaction and UX
- Docs and deployment DX

## Development Principles

- Treat `data` container as the primary architecture path.
- New behavior should be configurable in Settings whenever possible.
- Keep LLM optional: baseline features must still work without LLM config.

## Prompt Iteration (Recommended Workflow)

You can now test prompt changes directly inside the running container/UI:

1. Start containers and open WebUI.
2. Edit these fields in `Settings -> LLM`:
   - `PROMPT_SEARCH_NARRATIVE_SYSTEM`
   - `PROMPT_PROFILE_SYSTEM`
   - `PROMPT_REPORT_SYSTEM`
   - `PROMPT_TAG_EXTRACT_SYSTEM`
3. Save and immediately validate in chat/search flows.

## Skill & Plugin Conventions

- Built-in skills: `Docker/data/hunterAgent/skills/builtin/`
- Global registry: `Docker/data/hunterAgent/skills/registry.py`
- Runtime plugin folder: `/app/runtime/webui/plugins` (upload supported in WebUI)
- Use unified `SkillContext`; avoid duplicating low-level connection setup in plugins.

## Pre-PR Checklist

- Python: run `python -m py_compile` on changed modules
- Frontend: keep `App.vue` and i18n JSON syntactically valid
- Docs: update both Chinese and English docs together
- If retrieval logic changed, validate at least:
  - zh UI + zh tags
  - non-zh UI + English tags
  - hard tag filter on/off

## What to Include in PR Description

- Motivation (why)
- Key design choices (how)
- Validation steps/results
- Compatibility notes (especially no-LLM mode)

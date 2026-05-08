---
name: weibo-01h-local-delivery
description: Use for the local 01H Weibo digest workflow in F:\Workspaces\weibo, including scheduled slot execution, prepared digest validation, source-tail/video/image format safety, historical high-read calibration, DeepSeek API ablation harness work, and format-safe Weibo rewriting. Trigger on requests mentioning 01H, 微博, 今视频长天新闻, hot-search digest, prepared_digest, DeepSeek 消融, or local Weibo automations.
---

# Weibo 01H Local Delivery

Use this skill for the migrated local 01H Weibo digest project at `F:\Workspaces\weibo`.

## Hard Boundaries

- Never print, copy, migrate, summarize, or commit secret contents.
- Weibo and SMTP secrets stay path-referenced only; DeepSeek API keys must come from environment variables.
- Keep the workflow local Codex automation; do not reconnect Hermes/OpenClaw.
- Treat reading count as the hard KPI. Engagement is diagnostic only.
- DeepSeek output is advisory. Codex/GPT-5.5 must audit before changing prompts, ranking, or send gates.

## Task Router

- **Scheduled/manual slot run**: read `references/send-gate.md`.
- **Weibo rewriting or prepared digest editing**: read `references/rewrite-format.md`.
- **Historical calibration or DeepSeek ablation**: read `references/deepseek-calibration.md`.
- **Automation schedule edits**: read `references/automation.md`.

Only load the reference needed for the current task.

## Default Project

Run commands from:

```powershell
cd F:\Workspaces\weibo
```

Core verification commands:

```powershell
python -m py_compile .\scripts\weibo_digest.py .\scripts\send_prepared_digest.py .\scripts\ablate_01h_changes.py
python -m json.tool .\config\weibo_digest_config.json
.\scripts\run_weibo_digest.ps1 -DryRun
```

---
name: codex-review-helper
description: "Single-packet read-only review helper for Codex. Use only for one bounded snippet, diff, log, config, or short prose packet when Codex needs an external second opinion verifiable from the packet alone. Do not use for implementation, full-repo review, architecture, security-owned decisions, migrations, secrets, broad conversation handoff, native Codex subagent work, training/evaluation datasets, bulk or batch delegation, model routing, data collection, A/B ablation, or calibration."
---

# Codex Review Helper

Delegate one explicit packet to the user's configured local review CLI for advisory review while Codex keeps final judgment, file edits, and local verification. The current transport can call the `deepseek` command installed by the third-party Hmbown/DeepSeek-TUI client and pass `deepseek-v4-pro`; that is an unofficial client dependency, not a DeepSeek official agent or trigger surface.

## Contract

- Use the external CLI only as a bounded helper reviewer, not an authority, owner, trainer, or data collection target.
- Use the configured review CLI as a single external reviewer. Do not add cheap-model routing in this helper.
- Send only the smallest explicit packet that contains the task, constraints, and evidence.
- The external CLI receives only `task`, optional `context_text`, contents of listed `context_files`, and helper framing. It does not receive Codex hidden prompts, GPT conversation history, memory, repo files not attached, environment variables, credentials, cookies, or browser/session data.
- Keep all calls read-only and non-interactive. Do not drive the visual TUI, browser UI, OCR, screenshots, or terminal screen scraping.
- Never pass secrets, credential files, cookies, unrelated personal data, broad conversation history, training/evaluation datasets, collected model outputs, or bulk task queues.
- Do not use this skill for batch review, map/reduce delegation, automated scoring, or repeated corpus processing.
- Prefer native Codex subagents for true parallel repo work, isolated implementation, or tasks that need the full tool surface.

## When To Delegate

Good fits:

- Compact diffs, snippets, configs, logs, plans, or short prose that can be reviewed from the packet alone.
- Second-pass code or wording review where findings can cite packet evidence.
- One-off Chinese prose review when the text section is small, explicit, and safe to disclose to the configured external CLI.

Bad fits:

- Implementation, broad refactors, full-repo review, architecture, migrations, or user-facing conclusions Codex cannot verify.
- Any packet that would sever context Codex must reason over as one workflow.
- Any task that needs hidden conversation state, secrets, live credentials, or mutating shell access.
- Batch jobs, corpus review, model comparison/evaluation datasets, repeated social-media or workflow calibration, or anything that could look like training another model on GPT/Codex output.

## How To Call

Default to the installed helper with a JSON request file for larger packets. Use `--structured-result` for new automation and keep `--json-result` for the machine-readable envelope.

```powershell
python "$env:USERPROFILE\.codex\skills\codex-review-helper\scripts\review_helper.py" `
  --input-json .\packet.review-helper.json `
  --structured-result `
  --json-result `
  --out .\review-helper-output.md
```

The optional `scripts/review_helper_mcp.py` wrapper exposes one narrow MCP tool for hosts that require stdio JSON. Do not register it as a broad, always-on agent tool when the CLI JSON path is enough.

If the helper reports `setup_error`, `timeout`, `partial`, missing structured fields, or sensitive-content rejection, shrink or clarify the packet, or do the work in Codex. Treat every finding as a hypothesis until Codex checks the cited evidence.

## Reference Router

Load `references/index.md` when the packet type or integration pattern is not obvious. It routes to:

- `references/result-contract.md` for structured result schema and status handling.
- `references/privacy-boundary.md` for data exposure, non-training, and no-batch constraints.
- `references/packet-types.md` for packet shapes and minimum evidence.
- `references/codex-side-routing.md` for deciding whether Codex should use this skill, native subagents, or no delegate.
- `references/agent-cli-delegation.md` for MCP, native subagent, and CLI-adapter comparison.
- `references/transport-patterns.md` for JSON input, MCP wrapper, and single-packet transport decisions.
- `references/chinese-prose.md` for bounded Chinese prose review.

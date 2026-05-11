---
name: deepseek-delegate
description: "Pro-only packet-local advisory review via DeepSeek TUI CLI using deepseek-v4-pro. Use for bounded snippets, diffs, logs, short prose, or independent review chunks when Codex wants a second opinion verifiable from the packet alone. Do not use for implementation, full-repo review, architecture, security-owned decisions, migrations, secrets, broad conversation handoff, native Codex subagent work, or cheap-model routing."
---

# DeepSeek Delegate

Delegate a small packet to DeepSeek TUI `deepseek-v4-pro` for advisory review while Codex keeps final judgment, file edits, and local verification.

## Contract

- Use DeepSeek only as a bounded reviewer, not an authority or owner.
- Use `deepseek-v4-pro` for real delegate calls. Do not add cheap-model routing in this helper.
- Send the smallest packet that contains the task, constraints, and evidence.
- Keep all calls read-only and non-interactive. Do not drive the visual TUI, browser UI, OCR, screenshots, or terminal screen scraping.
- Never pass secrets, credential files, cookies, unrelated personal data, or broad conversation history.
- Prefer native Codex subagents for true parallel repo work, isolated implementation, or tasks that need the full tool surface.

## When To Delegate

Good fits:

- Compact diffs, snippets, configs, logs, plans, or short prose that can be reviewed from the packet alone.
- Second-pass code or wording review where findings can cite packet evidence.
- Independent chunks in a map/reduce review where Codex can merge duplicate findings and verify them locally.
- Domain packets routed by `references/index.md`, such as bounded Chinese prose review.

Bad fits:

- Implementation, broad refactors, full-repo review, architecture, migrations, or user-facing conclusions Codex cannot verify.
- Any packet that would sever context Codex must reason over as one workflow.
- Any task that needs hidden conversation state, secrets, live credentials, or mutating shell access.

## How To Call

Default to the installed helper with a JSON request file for larger packets. Use `--structured-result` for new automation and keep `--json-result` for the machine-readable envelope.

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --input-json .\packet.deepseek.json `
  --structured-result `
  --json-result `
  --out .\deepseek-review.md
```

The optional `scripts/deepseek_delegate_mcp.py` wrapper exposes one narrow MCP tool for hosts that require stdio JSON. Do not register it as a broad, always-on agent tool when the CLI JSON path is enough.

If the helper reports `setup_error`, `timeout`, `partial`, missing structured fields, or sensitive-content rejection, shrink or clarify the packet, or do the work in Codex. Treat every finding as a hypothesis until Codex checks the cited evidence.

## Reference Router

Load `references/index.md` when the packet type or integration pattern is not obvious. It routes to:

- `references/result-contract.md` for structured result schema and status handling.
- `references/packet-types.md` for packet shapes and minimum evidence.
- `references/codex-side-routing.md` for deciding whether Codex should use this skill, native subagents, or no delegate.
- `references/agent-cli-delegation.md` for MCP, native subagent, and CLI-adapter comparison.
- `references/transport-patterns.md` for JSON input, MCP wrapper, and long-context transport decisions.
- `references/chinese-prose.md` for bounded Chinese prose review.

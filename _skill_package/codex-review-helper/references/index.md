# Codex Review Helper Reference Router

Load this file only when `SKILL.md` is not enough to choose the right packet shape, data boundary, or integration path.

## Routing

- `result-contract.md`: load when changing `--structured-result`, interpreting `--json-result`, reviewing `status`, or diagnosing malformed delegate output.
- `privacy-boundary.md`: load before any new task category, data source, repeated workflow, or host integration is allowed to use this skill.
- `packet-types.md`: load when building a single task packet or deciding what evidence it must contain.
- `codex-side-routing.md`: load when deciding whether Codex should use this skill, keep the task local, or use a native subagent.
- `agent-cli-delegation.md`: load when comparing native Codex subagents, MCP tools, Claude Code/OpenClaw patterns, or the external CLI adapter.
- `transport-patterns.md`: load when choosing `--input-json`, optional MCP wrapper use, or backend transport.
- `chinese-prose.md`: load only for bounded Chinese wording, tone, fluency, ambiguity, or fact-risk review.

## Default Path

For ordinary snippet, diff, log, or prose review:

1. Build the smallest packet with goal, constraints, evidence, and "Do not modify files."
2. Prefer `--input-json <file>` with `--structured-result --json-result`; use direct flags only for tiny packets.
3. Accept only `result.status=ok` and a single structured result with no schema errors.
4. Verify every finding locally before using it in a user-facing answer.

Do not load Chinese prose guidance or agent-comparison notes unless the active task matches the route above.
Do not use this skill for social workflow calibration, A/B ablation, batch review, corpus processing, model evaluation, or any workflow that repeatedly transfers Codex/GPT-produced packets to another model.

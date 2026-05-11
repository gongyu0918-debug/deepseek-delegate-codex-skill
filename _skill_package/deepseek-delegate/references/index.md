# DeepSeek Delegate Reference Router

Load this file only when `SKILL.md` is not enough to choose the right packet shape or reference.

## Routing

- `result-contract.md`: load when changing `--structured-result`, interpreting `--json-result`, reviewing `status`, or diagnosing malformed delegate output.
- `packet-types.md`: load when building a task packet, choosing chunk boundaries, or deciding what evidence a packet must contain.
- `codex-side-routing.md`: load when deciding whether Codex should use this skill, keep the task local, or use a native subagent.
- `agent-cli-delegation.md`: load when comparing native Codex subagents, MCP tools, Claude Code/OpenClaw patterns, or the DeepSeek CLI adapter.
- `transport-patterns.md`: load when choosing `--input-json`, optional MCP wrapper use, backend transport, or long-context chunk policy.
- `chinese-prose.md`: load only for bounded Chinese wording, tone, fluency, ambiguity, or fact-risk review.
- `weibo-batch.md`: load only for 01H Weibo digest candidate selection, source binding, prepared digest, validator, ablation, or calibration packets.
- `weibo-ablation-index.md`: load only for repeated Weibo ablation tests, hotness-controlled historical calibration, or map/reduce batch review.

## Default Path

For ordinary snippet, diff, log, or prose review:

1. Build the smallest packet with goal, constraints, evidence, and "Do not modify files."
2. Prefer `--input-json <file>` with `--structured-result --json-result`; use direct flags only for tiny packets.
3. Accept only `result.status=ok` and structured chunks with no schema errors.
4. Verify every finding locally before using it in a user-facing answer.

Do not load Weibo references, Chinese prose guidance, or agent-comparison notes unless the active task matches the route above.

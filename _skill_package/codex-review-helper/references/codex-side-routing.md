# Codex-Side Routing

Load this file when deciding whether Codex should use Codex Review Helper, keep the task local, or use a native subagent.

## Rule

Routing happens in Codex, not inside `review_helper.py`. Real helper calls use the configured Pro review model; the helper must not choose cheaper models automatically.

## Use Codex Review Helper

- Bounded snippets, diffs, logs, configs, or short prose packets.
- Second opinions where all evidence can fit in the packet.
- One-off helper reviews where the user would be comfortable sending the explicit packet to the configured external CLI.

## Keep In Codex Or Native Subagents

- Implementation, broad refactors, architecture, migrations, deployment, permissions, payment, auth, security-owned decisions, or final acceptance.
- Full-repo review, integrated debugging, long-running work, or tasks needing the current conversation and workspace context.
- Any prompt containing secrets, credential files, cookies, API keys, or unrelated personal data.
- Batch jobs, A/B ablation, calibration runs, benchmark labels, model-output evaluation datasets, or repeated transfers of Codex/GPT-generated packets.

## CodexSaver Lessons

Borrow the conservative boundary: low-risk work may be delegated only when Codex can review the result, high-risk judgment stays in Codex, and structured returns make the handoff observable.

Do not borrow CodexSaver's MVP surface for this skill: no broad MCP server, no direct provider API client, no patch worker, no test runner, no cost estimator, no batch router, and no model routing.

Chinese and English risk terms such as 架构, 安全, 权限, 支付, 迁移, 生产, 密钥, 模糊需求, architecture, security, permission, payment, migration, production, secret, or ambiguous requirements are skill-use signals for Codex. They are not runtime classifier inputs for the helper.

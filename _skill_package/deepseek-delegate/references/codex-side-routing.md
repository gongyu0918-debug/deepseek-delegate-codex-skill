# Codex-Side Routing

Load this file when deciding whether Codex should use DeepSeek Delegate, keep the task local, or use a native subagent.

## Rule

Routing happens in Codex, not inside `deepseek_delegate.py`. Real DeepSeek Delegate calls use `deepseek-v4-pro`; the helper must not choose cheaper models automatically.

## Use DeepSeek Delegate

- Bounded snippets, diffs, logs, configs, short prose, or Weibo packets.
- Second opinions where all evidence can fit in the packet.
- Independent map/reduce chunks that Codex can merge and verify locally.

## Keep In Codex Or Native Subagents

- Implementation, broad refactors, architecture, migrations, deployment, permissions, payment, auth, security-owned decisions, or final acceptance.
- Full-repo review, integrated debugging, long-running work, or tasks needing the current conversation and workspace context.
- Any prompt containing secrets, credential files, cookies, API keys, or unrelated personal data.

## CodexSaver Lessons

Borrow the conservative boundary: low-risk work may be delegated only when Codex can review the result, high-risk judgment stays in Codex, and structured returns make the handoff observable.

Do not borrow CodexSaver's MVP surface for this skill: no MCP server, no direct DeepSeek API client, no patch worker, no test runner, no cost estimator, and no model routing.

Chinese and English risk terms such as 架构, 安全, 权限, 支付, 迁移, 生产, 密钥, 模糊需求, architecture, security, permission, payment, migration, production, secret, or ambiguous requirements are skill-use signals for Codex. They are not runtime classifier inputs for the helper.

# Agent CLI Delegation Patterns

Load this file when changing the DeepSeek Delegate helper, comparing it with community multi-agent patterns, or deciding whether to use MCP, handoff, subagent, or CLI execution.

## Selection Order

Prefer these integration shapes in order:

1. Native host subagent: use when Codex can spawn an isolated reviewer/worker with scoped tools and no external model handoff.
2. MCP tool: use when the external agent exposes a real `tools/list` and `tools/call` interface with a bounded input schema.
3. Agents-as-tools: use when the runtime supports explicit worker agents and structured return values while Codex remains the orchestrator.
4. CLI adapter: use only when the external agent has no usable tool interface. Keep it read-only, non-interactive, bounded, and observable.

Avoid handoff semantics for this skill. A handoff transfers control to another specialist; DeepSeek Delegate is only a tool-like assistant behind Codex.

Current DeepSeek-TUI status on this machine: `deepseek mcp-server` starts, but `tools/list` exposes no delegate/review tool. The helper therefore defaults to `--driver auto`, records the MCP probe result, and falls back to `exec`.

## Adapter Contract

The helper is a restricted tool adapter, not a full agent framework:

- Codex is the supervisor and owns final judgment, file writes, validator execution, and user-facing synthesis.
- DeepSeek is an advisory worker and receives only a task-local packet.
- Delegate only assistant-shaped work: bounded review, sanity checks, extraction, calibration, or proofreading that can be judged from the packet alone.
- Low-cost batch passes are allowed when they are map/reduce-style assistant work: each chunk is independent, cheap-model output is advisory, and Codex merges and verifies results.
- Do not delegate work whose correctness depends on keeping cross-file, workflow, conversation, or product context integrated in Codex.
- Every chunk has a `chunk_id`; DeepSeek must not claim full-workspace or full-document completeness from one chunk.
- Findings are hypotheses until Codex reproduces them or verifies concrete static evidence.
- Missing headings, timeouts, prompt limits, sensitive-content rejection, invalid `--cwd`, or command-line limits must become structured result states.

## Driver Semantics

- `--driver auto`: probe MCP first; use MCP only if a delegate/review-like tool is exposed; otherwise fall back to `exec` and record a warning.
- `--driver exec`: call `deepseek exec` through the resolved installed binary. This is the current reliable path.
- `--driver mcp`: require a matching MCP tool. If none exists, fail closed.
- `--json-result`: print a machine-readable request/result envelope instead of raw Markdown. Use this for smoke tests, automation, and review evidence.

## Result Interpretation

Treat result status as follows:

- `ok`: exit code zero and all required headings present.
- `partial`: output returned but one or more chunks missed required headings.
- `timeout`: the subprocess timed out.
- `setup_error`: local setup, safety guard, MCP probe, cwd, prompt-size, or command-line validation failed before a trustworthy delegate result.
- `error`: delegate call completed with a nonzero exit code.

Raw DeepSeek output is advisory evidence. The JSON envelope is operational evidence about whether the delegation call itself was trustworthy.

## Trigger Description Guidance

Keep trigger text narrow:

- Prefer phrases such as `bounded`, `packet-local`, `second-pass review`, `independent chunks`, and `low-cost batch advisory pass`.
- Avoid phrases that imply broad ownership, such as `any review`, `full repo`, `implementation`, `architecture`, `agent handoff`, or `final decision`.
- Mention batch use only with the independence condition; batch size alone is not enough to justify delegation.

## Permission Guidance

Borrow the common CLI/subagent pattern: start read-only, grant only the minimum tool surface, and keep sensitive or mutating work with Codex.

- Do not pass API keys, cookies, private files, or full conversation history.
- Do not expose shell/exec/command-style MCP tools as delegate tools.
- Use timeouts, structured status, and audit-friendly warnings for every external call.
- Treat low-cost model output as triage evidence, not acceptance evidence.

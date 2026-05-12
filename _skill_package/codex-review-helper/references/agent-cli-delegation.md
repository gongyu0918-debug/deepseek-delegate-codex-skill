# Agent CLI Delegation Patterns

Load this file when changing transport behavior or comparing Codex Review Helper with Codex, Claude Code, Gemini CLI, OpenClaw, or other agent CLI integrations.

## Selection Order

1. Native host subagent: use when Codex can spawn a read-only reviewer or worker with scoped tools, isolated context, and lifecycle tracking.
2. MCP tool: use when an external agent exposes a real `tools/list` and `tools/call` interface with a bounded input schema and structured return value.
3. Structured CLI adapter: use when no MCP delegate tool exists, but the CLI supports non-interactive one-shot prompts and deterministic stdout.
4. Visual TUI automation: forbidden for this skill. Do not use screen scraping, screenshots, OCR, browser control, or terminal UI driving as glue.

## Community Patterns To Borrow

- Codex skills: keep `description` short, front-load trigger terms, and route optional detail through references.
- Codex subagents: use native agents for full repo exploration, implementation, or parallel work instead of pretending a CLI adapter has the same lifecycle.
- Claude Code subagents: delegate only self-contained work that can return a concise summary; use tool restrictions and explicit foreground/background semantics for real subagents.
- Gemini CLI in OpenClaw: prefer one-shot non-interactive calls and avoid dangerous all-permission modes such as `--yolo`.
- OpenClaw coding-agent plugins: keep cwd, permission mode, lifecycle, cost/budget, and observable status explicit when a wrapper launches another coding harness.

## Codex-Side Routing

- Native Codex or Codex subagent: repo work, implementation, full-repo review, architecture, parallel workers, or any task that needs integrated workspace context.
- Codex Review Helper: one bounded advisory packet where a configured external CLI can provide a second opinion from packet evidence only.
- MCP tool: use only when a real delegate/review tool is exposed through `tools/list`.
- CLI JSON adapter: preferred default for this skill because it avoids extra MCP tool-schema overhead while still keeping large packets out of shell argv.
- CLI exec adapter: backend fallback when MCP has no delegate/review tool and the configured CLI has no prompt-file/stdin support.

## Helper Boundary

- Codex is the supervisor and owns final judgment, file writes, validators, and user-facing synthesis.
- The external CLI receives only one task-local packet and returns advisory findings.
- The external CLI must not receive batches, A/B ablation packets, training/evaluation datasets, repeated social workflow samples, or collected Codex/GPT outputs.
- Current local status: the configured CLI MCP server may start, but `tools/list` must expose a real delegate/review tool before `--driver mcp` is allowed; otherwise `--driver auto` falls back to `exec`.
- `--driver mcp` must fail closed if no delegate/review tool is exposed.
- `--input-json` should be the normal automation entry for larger packets.
- Optional local MCP wrapper use must stay one-tool and narrow; do not install a broad command bridge for this skill.
- `--driver exec` must stay read-only, non-interactive, timeout-bound, and observable through JSON result metadata.

## Anti-Patterns

- Do not expose shell, terminal, process, or command MCP tools as delegate tools.
- Do not pass full conversation history, repo-wide context, credentials, cookies, or unrelated user data.
- Do not let the external CLI decide acceptance. Local checks and Codex synthesis remain authoritative.
- Do not use batch size as a reason to delegate. Shrink the packet or keep the work in Codex.

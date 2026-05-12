# Transport Patterns

Load this file when changing JSON input, MCP wrapper behavior, or backend prompt transport.

## Default Path

- Prefer `--input-json <file>` for normal automation. It moves `task`, packet text, file list, and options out of the shell command line.
- Keep `--json-result --structured-result` for machine-readable review output.
- Keep `--driver auto` unless explicitly testing MCP fail-closed behavior.
- Keep MCP discovery short. `--mcp-probe-timeout-seconds` is separate from the real delegate timeout so auto fallback does not hang on `tools/list`.

Example request:

```json
{
  "task": "Review this bounded packet for correctness risks. Do not modify files.",
  "mode": "review",
  "packet_profile": "long-review",
  "context_text": "packet text here",
  "context_files": ["packet.md"],
  "options": {
    "structured_result": true,
    "json_result": true
  }
}
```

## MCP Wrapper

Use `scripts/review_helper_mcp.py` only when a host needs stdio JSON tools. It exposes one tool, `codex_review_helper_review`, and delegates through the same helper.

Borrowed community constraints:

- CodexSaver: thin JSON-RPC stdio server with `initialize`, `tools/list`, and `tools/call`.
- Safe Agent CLI MCP: no generic shell, no arbitrary command tool, and realpath checks for context files under `cwd`.
- OpenClaw MCP: stdio transport is a local child process communicating through stdin/stdout.

Do not register this wrapper as a broad always-on MCP suite. A single narrow tool keeps prompt/tool-schema overhead lower than a general CLI bridge. Tool failures should return the helper-style `status=setup_error` or `status=timeout` envelope instead of protocol-level internal errors whenever possible.

## Backend Transport

- Current default: `exec-argv`, because the current supported CLI exposes only an argv prompt path.
- Reserved only: `exec-file` and `exec-stdin`. Enable them only after the configured CLI advertises prompt-file or stdin support.
- MCP probing is valid only when the configured CLI exposes a real delegate/review tool through `tools/list`.

## Packet Size

- Attempt one explicit packet only.
- With current `exec-argv`, keep the conservative prompt-size guard.
- If a packet is too large, shrink it or keep the review in Codex. Do not fall back to repeated external CLI calls.
- Treat `chunk_reason` in the JSON envelope as a setup-failure explanation, not permission to batch.

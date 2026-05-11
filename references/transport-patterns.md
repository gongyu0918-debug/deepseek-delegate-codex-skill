# Transport Patterns

Load this file when changing JSON input, MCP wrapper behavior, backend prompt transport, or long-context chunking.

## Default Path

- Prefer `--input-json <file>` for normal automation. It moves `task`, packet text, file list, and options out of the shell command line.
- Keep `--json-result --structured-result` for machine-readable review output.
- Keep `--driver exec` for normal automation. Use `--driver auto` only when explicitly testing a real MCP delegate/review tool.
- If `--driver auto` is used, keep MCP discovery short. `--mcp-probe-timeout-seconds` is separate from the real delegate timeout so auto fallback does not hang on `tools/list`.

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
    "json_result": true,
    "chunk_chars": 18000
  }
}
```

## MCP Wrapper

Use `scripts/deepseek_delegate_mcp.py` only when a host needs stdio JSON tools. It exposes one tool, `deepseek_delegate_review`, and delegates through the same helper.

Borrowed community constraints:

- CodexSaver: thin JSON-RPC stdio server with `initialize`, `tools/list`, and `tools/call`.
- Safe Agent CLI MCP: no generic shell, no arbitrary command tool, and realpath checks for context files under `cwd`.
- OpenClaw MCP: stdio transport is a local child process communicating through stdin/stdout.

Do not register this wrapper as a broad always-on MCP suite. A single narrow tool keeps prompt/tool-schema overhead lower than a general CLI bridge. Tool failures should return the helper-style `status=setup_error` or `status=timeout` envelope instead of protocol-level internal errors whenever possible.

## Backend Transport

- Current default: `exec-argv`, because local `deepseek v0.8.26` exposes `deepseek exec [ARGS]...`.
- Current driver default: `exec`, because local DeepSeek MCP probing does not expose a delegate/review tool and unnecessarily starts another DeepSeek process.
- Reserved only: `exec-file` and `exec-stdin`. Enable them only after `deepseek exec --help` advertises prompt-file or stdin support.
- Existing DeepSeek MCP probing remains valid only when `deepseek mcp-server` exposes a real delegate/review tool through `tools/list`.

## Long Context

- Attempt a single packet first when the backend transport can carry it.
- With current `exec-argv`, keep the conservative prompt-size guard and chunk only when the full prompt exceeds that guard.
- Chunk by evidence boundary, not arbitrary byte count. Preserve ids, URLs, paths, timestamps, and source evidence with the claim they support.
- Treat `chunk_reason` in the JSON envelope as the reason a long packet was split.

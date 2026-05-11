# DeepSeek Delegate Codex Skill

Codex skill for bounded second-opinion review through DeepSeek TUI.

## Boundary

- Host: Codex.
- Delegate: DeepSeek TUI, non-interactive `deepseek exec`.
- Model: `deepseek-v4-pro` by default.
- Role: advisory review only.
- Output: structured findings for Codex to verify.

Use it for small packets: snippets, diffs, logs, configs, short prose, or independent long-text chunks.

Do not use it for implementation, full-repo review, architecture decisions, migrations, secrets, broad conversation handoff, or native Codex subagent work.

## Install

Requirements:

- Python 3.10 or newer.
- DeepSeek TUI available as `deepseek`.
- An authenticated DeepSeek TUI profile that can run `deepseek-v4-pro`.

Clone or copy this repository into a Codex skills directory:

```powershell
git clone https://github.com/gongyu0918-debug/deepseek-delegate-codex-skill.git "$env:USERPROFILE\.codex\skills\deepseek-delegate"
```

DeepSeek TUI must already be installed and available as `deepseek`.

```powershell
deepseek --version
```

## Use

Build a packet file:

```json
{
  "task": "Review this bounded packet for correctness risks. Do not modify files.",
  "mode": "review",
  "context_files": ["packet.md"],
  "options": {
    "structured_result": true,
    "json_result": true
  }
}
```

Run the helper:

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --input-json .\packet.deepseek.json `
  --structured-result `
  --json-result
```

Codex should accept only `result.status=ok` and then verify every finding locally.

## Transport

Default path:

```text
Codex -> deepseek_delegate.py --input-json -> deepseek exec -> JSON envelope -> Codex
```

Optional MCP wrapper:

```text
Codex MCP host -> deepseek_delegate_mcp.py -> deepseek_delegate.py -> deepseek exec
```

The MCP wrapper exposes one tool: `deepseek_delegate_review`. It is not a general shell bridge.

## Security Model

- Local-only stdio/CLI workflow. Do not expose the MCP wrapper as a network service.
- No generic shell tool, patch worker, test runner, direct API client, provider router, or background job lifecycle.
- Context files are read before delegation; the downstream DeepSeek process is launched from an isolated temp cwd, not the target repo.
- Review defaults are advisory and read-oriented; Codex owns file edits, verification, and final judgment.
- Context files should be bounded packet inputs. Do not pass secrets, credential files, cookies, or broad conversation history.
- Redaction is pattern-based and conservative. Treat it as a guardrail, not a DLP system.

## Files

- `SKILL.md`: trigger boundary and operating contract.
- `scripts/deepseek_delegate.py`: JSON input, safety guard, chunking, DeepSeek transport, result validation.
- `scripts/deepseek_delegate_mcp.py`: narrow stdio MCP wrapper.
- `references/`: transport notes, result contract, packet shapes, and routing notes.
- `tests/`: regression tests for parser, transport, MCP, chunking, and structured results.

## Check

```powershell
python -m py_compile .\scripts\deepseek_delegate.py .\scripts\deepseek_delegate_mcp.py
python -m unittest discover -s tests -v
```

The test suite uses the Python standard library only.

## License

MIT-0. See [LICENSE](LICENSE).

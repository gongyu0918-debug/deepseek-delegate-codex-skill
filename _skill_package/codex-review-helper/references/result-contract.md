# Structured Result Contract

Load this file when changing `--structured-result`, interpreting `--json-result`, or diagnosing malformed delegate output.

## Delegate Output

With `--structured-result`, the external CLI should return one fenced JSON object:

```json
{
  "answer": "Concise packet-local conclusion.",
  "findings": [
    {
      "severity": "low|medium|high",
      "claim": "Evidence-bound finding.",
      "evidence": "Packet quote, id, path, log line, or static code path.",
      "codex_check": "Exact local check Codex should perform."
    }
  ],
  "uncertainty": ["Missing context or assumptions."],
  "suggested_codex_checks": ["Commands, files, or evidence Codex should verify."]
}
```

`findings` may be empty when the packet has no issues. Empty findings are valid only if `answer`, `uncertainty`, and `suggested_codex_checks` still explain what was checked.

## Helper Semantics

- `status=ok`: delegate exited zero and the single result satisfied the active result contract.
- `status=partial`: delegate returned output, but JSON parsing, required fields, or legacy headings failed.
- `status=timeout`: the delegate transport exceeded its timeout.
- `status=setup_error`: local setup, safety guard, MCP probe, cwd, prompt size, or command-line validation failed before a trustworthy result.
- `status=error`: delegate call completed with a nonzero exit code.

For structured mode, schema success is authoritative. Markdown headings are only a compatibility fallback when `--structured-result` is not used.
In structured mode, chunks report `headings_checked=false`; use `structured_ok` and `structured_errors` instead of legacy heading fields.

The result envelope also reports transport metadata:

- `input_transport`: `cli`, `json-file`, or `json-stdin`.
- `backend_transport`: `exec-argv`, `exec-file`, `exec-stdin`, or `mcp-stdio`.
- `single_packet_attempted`: whether the helper attempted one full packet.
- `chunk_reason`: why a packet was rejected as too large for the active transport.

## Codex Acceptance

Codex may use a finding only after it verifies the cited packet evidence or reproduces the suggested check locally. Treat uncited claims, broad advice, style-only rewrites, or findings that depend on missing context as advisory noise.

Do not send helper results back to the external CLI for grading, correction, prompt tuning, or calibration. Codex accepts or rejects findings inside the Codex thread.

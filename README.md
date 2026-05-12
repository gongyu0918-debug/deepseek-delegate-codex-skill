# Codex Review Helper

Single-packet review helper for Codex.

This skill lets Codex ask a configured external CLI for one read-only second opinion on a small review packet. Codex remains the host: it chooses whether to call the helper, verifies every finding locally, and accepts or rejects the result inside the Codex thread.

The current adapter can call the local `deepseek` executable with `deepseek-v4-pro`. The project is not affiliated with DeepSeek, does not provide a model, and does not create a training or evaluation pipeline.

## Boundaries

- One explicit packet per call.
- Review only: code review, code recheck, bug-risk findings, small logs/configs, or short prose.
- No implementation, patch application, full-repo work, migrations, security-owned decisions, or final acceptance.
- No secrets, cookies, credentials, environment dumps, hidden prompts, full conversation history, or repo-wide context.
- No batch jobs, queues, map/reduce, A/B ablation, calibration, scoring, labeling, benchmarks, or corpus processing.
- No loop where helper output is sent back to the helper for grading, correction, or prompt tuning.

## Install

Copy the skill folder into Codex:

```powershell
Copy-Item -Recurse .\_skill_package\codex-review-helper "$env:USERPROFILE\.codex\skills\codex-review-helper"
```

Recommended call:

```powershell
python "$env:USERPROFILE\.codex\skills\codex-review-helper\scripts\review_helper.py" `
  --input-json .\packet.review-helper.json `
  --structured-result `
  --json-result
```

## What The External CLI Gets

Only the explicit packet:

- `task`
- optional `context_text`
- contents of explicitly listed `context_files`
- helper framing for structured findings

It does not get Codex hidden prompts, memory, environment variables, browser/session data, credential files, or files that were not attached.

## Safety Notes

This helper cannot control a remote provider's retention policy. For sensitive code or documents, do not use a remote external model. Use Codex locally, a native Codex subagent, or a local model you control.

`--cwd` is used by the helper to resolve explicit `context_files`. The downstream CLI process is launched from an isolated temporary directory so it does not start inside the repository.

The helper also passes `--telemetry false`, `--approval-policy never`, and `--sandbox-mode read-only` to the configured CLI. On Windows, CLI sandboxing may be best-effort; do not rely on it for secrets or private repositories.

## License

MIT-0.

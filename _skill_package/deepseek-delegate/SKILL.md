---
name: deepseek-delegate
description: Use when Codex can save context by delegating a bounded, low-risk task to the installed DeepSeek TUI CLI, or when Codex needs an independent lightweight audit/review perspective. Trigger for subagent-suitable helper work: simple answer extraction, small code-reading questions, second-pass review of compact diffs/snippets/configs/logs, Chinese prose proofreading or fact-risk checks on bounded drafts, low-cost batch advisory passes over independent chunks, batch Weibo digest ablation/calibration packets, and sanity checks that fit in a reviewable task packet. Do not use for broad architecture, large implementation, long-running work, sensitive full-context handoffs, tasks that would split apart context Codex must keep integrated, or tasks where Codex must preserve and reason over the complete workspace context.
---

# DeepSeek Delegate

Delegate light work to DeepSeek TUI through agent-friendly CLI commands while keeping Codex responsible for final judgment.
Use this skill only when the delegated packet is smaller than the surrounding Codex context and the task can be answered from the packet alone.
Do not delegate work that would sever a decision from the broader context Codex must hold together.

## Core Rule

Treat DeepSeek as an advisory subagent, not an authority.
Codex must decide whether to delegate, minimize the context packet, verify the returned claims, and own the final answer to the user.
Prefer the helper's `auto` driver, which probes DeepSeek MCP support and falls back to non-interactive CLI execution when no delegate tool is exposed. Do not operate the visual TUI, use headless browsers, OCR, screenshots, screen scraping, or terminal UI automation as glue.

## Use Cases

Use this skill for:

- Simple bounded questions that can be answered from a short prompt or a few excerpts.
- Independent lightweight audits of compact code snippets, diffs, configs, logs, or plans.
- Second-perspective review where a different model may notice a missed issue.
- Chinese prose proofreading or wording/factual-risk checks when the draft can be reviewed in small independent chunks.
- Low-cost batch advisory passes when every item or chunk is independently reviewable and Codex can merge and verify the findings.
- Batch Weibo digest ablation or calibration review when the packet preserves candidate ids, original URLs, `source_tail`, validator output evidence, and hot-search control fields for historical samples.
- Low-risk exploration that does not require DeepSeek to edit files or operate over the full repo.
- Long text review only when chunked into small independent sections.
- Codex-assistant work where DeepSeek is only a second set of eyes on a self-contained packet.

Avoid this skill for:

- Large implementation tasks, broad refactors, migrations, or architecture design.
- Work requiring hidden conversation history, full Codex context, secrets, or many files.
- Batch tasks whose items depend on shared hidden context that would be lost when split into packets.
- User-facing conclusions that Codex cannot verify afterward.
- Cases where native Codex subagents are required by the user or better suited to the task.
- Cases where extracting a packet would lose crucial cross-file, workflow, conversation, or product context.
- Cases that would require driving the interactive TUI visually instead of using a normal CLI prompt.
- Single-shot long prompts or whole-document reviews that cannot finish within the configured timeout.

## Delegation Workflow

1. Decide whether delegation is worthwhile.
2. Create a minimal task packet:
   - one-sentence goal
   - relevant constraints
   - smallest necessary snippets, paths, diffs, logs, or command output
   - explicit instruction not to modify files
3. Call the helper script.
4. Evaluate the result deterministically before using it.
5. Synthesize the final answer yourself.

## Helper Script

Prefer the helper script because it standardizes prompts, timeouts, output headings, structured result metadata, and raw output capture.
The helper defaults to `--driver auto`, `--provider deepseek`, `--model deepseek-v4-pro`, `--sandbox-mode read-only`, and `--approval-policy never`. The `auto` driver probes MCP and uses the CLI exec driver when no MCP delegate/review tool is exposed; avoid visual or browser-based interaction layers.

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --mode audit `
  --task "Review this small diff for correctness risks. Do not modify files." `
  --context-file .\small-diff.txt `
  --out .\deepseek-delegate-output.md
```

For machine-readable status, add `--json-result`. This prints a request/result envelope with `status`, `driver`, `model`, per-chunk status, exit code, heading checks, warnings, duration, and output path.

For longer text, chunk it instead of sending a whole document as one prompt:

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --mode audit `
  --task "Review this document section for wording, factual risk, and overclaiming. Do not modify files." `
  --context-file .\document-extract.txt `
  --chunk-chars 3000 `
  --max-findings-per-chunk 5 `
  --timeout-seconds 240 `
  --out .\deepseek-delegate-chunks.md
```

For Weibo digest ablation or calibration packets, use a profile instead of manually lifting limits:

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --packet-profile weibo-ablation `
  --task "Review prepared vs baseline digest quality. Do not modify files." `
  --context-file .\weibo-ablation-packet.md `
  --cwd F:\Workspaces\weibo `
  --out .\deepseek-weibo-ablation-review.md
```

Supported modes:

- `answer`: concise answer or extraction
- `ablation`: before/after or variant comparison for quality and gate regressions
- `audit`: independent risk scan or sanity check
- `calibration`: sample comparison and repeatable signal extraction
- `review`: code-review style findings from a compact packet

The helper accepts `--driver auto|exec|mcp`, `--provider`, `--model`, `--sandbox-mode`, and `--approval-policy` for controlled experiments, but everyday Codex delegation should keep the defaults. Desktop TUI permissions are configured separately and should not be copied into this read-only advisory path.
For Weibo batch profiles, use the explicit model required by the active task. For hotness-controlled historical packets in the 01H workflow, pass `--model deepseek-v4-pro` and include hot-search lifecycle plus same-topic reuse fields; DeepSeek should return `topic_heat_driven`, `angle_label`, and `transferable_to_01h`. Codex should merge chunk findings and audit them before any calibration rule enters the live chain.
The helper rejects sensitive-looking context, rejects any single prompt above `--prompt-char-limit`, and also checks the estimated Windows command line length. Reduce `--chunk-chars` or the packet content instead of relying on local packet-file reads. Weibo profiles use `--prompt-char-limit 24000`, `--chunk-chars 15000`, and a Candidate boundary regex that recognizes plain, bullet, or Markdown-heading `Candidate N:` lines; if one candidate block exceeds the chunk size, the helper fails closed rather than splitting source/URL evidence away from the candidate.

If the helper fails, times out, or returns a delegate warning about missing headings, do not retry blindly. Shrink the packet, lower `--chunk-chars`, limit findings per chunk, clarify the task, or handle the work in Codex.
If the helper reports a prompt length limit, use `--chunk-chars`, reduce `--max-context-chars`, or summarize locally before delegating.

## Evaluation Rubric

Before trusting any DeepSeek output, check:

- Exit status is zero and no timeout occurred.
- The response includes `Answer`, `Evidence`, `Uncertainty`, and `Suggested Codex Checks`.
- Claims are supported by packet evidence or locally verifiable facts.
- Review findings cite concrete files, line numbers, snippets, or reproducible behavior.
- Findings are hypotheses until Codex reproduces them or verifies the cited static evidence.
- Uncertainty is explicit enough to guide Codex verification.

Discard or down-rank results that speculate, depend on missing context, overreach beyond the packet, or recommend edits without evidence.

## Context Management

Do not send the whole conversation or broad workspace state.
Prefer excerpts created by Codex after local inspection.
For code review, send the smallest diff or focused file region that covers the risk.
For command output, trim noise and preserve exact error text.
For long prose, split by section, ask for section-local findings, and cap findings per chunk; Codex should merge and deduplicate the final recommendations.
Never include API keys, tokens, private credentials, or unrelated user data.

## Evaluation Boundary

For everyday work, use this skill through DeepSeek TUI CLI because it tests the real local chain and avoids key handling.
For formal model evaluation, compare three columns: Codex native subagent, DeepSeek via this TUI helper, and DeepSeek direct API. Treat direct API results as model-capability evidence, and TUI results as end-to-end skill evidence.

## References

Open only if needed:

- `references/index.md`: local assumptions, command patterns, and rubric index.
- `references/agent-cli-delegation.md`: mature MCP, handoff, subagent, and CLI-adapter patterns for stable cross-agent calls.
- `references/weibo-batch.md`: Weibo digest ablation/calibration packet shape, hotness-controlled historical fields, and boundaries.
- `references/weibo-ablation-index.md`: dedicated index for low-cost batch ablation testing, hotness-controlled calibration, and subagent-style map/reduce review.

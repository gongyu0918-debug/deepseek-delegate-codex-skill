# DeepSeek Delegate Reference Index

Load this file only when the `SKILL.md` workflow is not enough.
This is an index, not a copied manual.

## Local Assumptions

- `deepseek` is available on `PATH`.
- DeepSeek TUI 0.8.16 or newer is preferred; verify with `deepseek --version` after updates.
- User-level DeepSeek TUI config lives at `~/.deepseek/config.toml`.
- The skill must not store, print, or copy API keys.
- The helper defaults to `--driver auto --provider deepseek --model deepseek-v4-pro --sandbox-mode read-only --approval-policy never` and leaves final judgment to Codex.
- Integration must stay agent-tool friendly; prefer MCP when a usable tool is exposed, otherwise use the restricted CLI exec adapter. Do not use visual TUI automation, screenshots, OCR, or headless browser control.
- Desktop TUI may run in Agent mode with `workspace-write` and `on-request`; do not inherit those permissions for Codex delegation.

## Command Patterns

- Simple answer:
  `python scripts/deepseek_delegate.py --mode answer --task "<bounded task>"`
- Structured smoke:
  `python scripts/deepseek_delegate.py --mode answer --task "<bounded task>" --json-result`
- Audit with context:
  `python scripts/deepseek_delegate.py --mode audit --task "<audit request>" --context-file <file>`
- Review with saved output:
  `python scripts/deepseek_delegate.py --mode review --task "<review request>" --context-file <packet> --out <output.md>`
- Alternate model or provider only for explicit experiments:
  `python scripts/deepseek_delegate.py --mode audit --model deepseek-v4-pro --task "<bounded task>"`
- Weibo ablation:
  `python scripts/deepseek_delegate.py --packet-profile weibo-ablation --task "<compare baseline/prepared/gate output>" --context-file <packet.md> --cwd F:\Workspaces\weibo --out <review.md>`
- Weibo hotness-controlled calibration:
  `python scripts/deepseek_delegate.py --packet-profile weibo-calibration --task "<review same-hot-topic or hard-negative historical pairs; return topic_heat_driven, angle_label, transferable_to_01h>" --context-file <packet.md> --cwd F:\Workspaces\weibo --out <review.md>`
- `--out` saves the raw DeepSeek response for Codex to inspect; it is advisory evidence, not final user-facing output.
- `--json-result` prints the request/result envelope for automation and smoke tests; it records driver, status, warnings, chunk ids, heading checks, duration, exit code, and output path.
- Weibo batch profiles support explicit model override. For 01H hotness-controlled calibration, use `--model deepseek-v4-pro`, keep chunking under the Windows command-line safe limit, and treat the output as a map/reduce advisory surface that Codex merges and verifies.
- Local packet-file reads are not part of the supported read-only non-interactive path; use chunking and explicit `--prompt-char-limit` rejection instead.
- Long text:
  `python scripts/deepseek_delegate.py --mode audit --task "<section-local review>" --context-file <text> --chunk-chars 3000 --max-findings-per-chunk 5 --timeout-seconds 240 --out <chunks.md>`

## Context Packet Index

Use one of these packet shapes:

- `question-only`: a self-contained task with no external context.
- `snippet`: one or more small excerpts or logs.
- `diff`: compact patch or selected changed regions.
- `review-packet`: goal, constraints, affected files, focused evidence.
- `chinese-prose-chunks`: bounded Chinese draft sections for proofreading, wording consistency, tone fit, or factual-risk review. Load `references/chinese-prose.md` only for this packet type.
- `weibo-ablation-packet`: baseline digest, prepared digest, candidate ids, validator output, ablation output, and changed editorial decisions. Load `references/weibo-batch.md`.
- `weibo-calibration-packet`: high-flow and low-flow samples, learned profile excerpts, source tiers, candidate scoring evidence, and hot-search control fields when historical samples are involved. Load `references/weibo-batch.md`.
- `weibo-hotness-calibration-packet`: same-hot-topic, same-hot-cluster, or hard-negative historical pairs with hot-search lifecycle and reuse fields. Load `references/weibo-batch.md` and `references/weibo-ablation-index.md`.
- `weibo-ablation-test-index`: low-cost batch ablation plan, chunking strategy, model tiers, and Codex synthesis checks. Load `references/weibo-ablation-index.md`.
- `agent-cli-delegation`: mature MCP, handoff, native subagent, and restricted CLI-adapter patterns. Load `references/agent-cli-delegation.md` before changing driver behavior.
- `low-cost-batch-advisory`: independent chunk map/reduce review where cheap-model output is triage evidence and Codex performs synthesis and verification. Load `references/agent-cli-delegation.md`; for Weibo, also load `references/weibo-ablation-index.md`.
- `long-text-chunks`: section-local prose chunks; Codex merges and deduplicates findings afterward.

Keep packet templates in `SKILL.md`; this file only names the shapes.

## Progressive Disclosure Index

- Chinese prose review: load `references/chinese-prose.md` only when the user asks to proofread, polish, fact-check, or risk-check bounded Chinese copy, notices, reports, public posts, or leadership-facing text through DeepSeek Delegate.
- Weibo batch review: load `references/weibo-batch.md` only when reviewing 01H Weibo digest ablation, candidate selection, source binding, repeat-topic risk, quality-gate failures, or calibration against reference account samples.
- Weibo ablation testing: load `references/weibo-ablation-index.md` when the user wants repeated or batch ablation tests, low-cost model routing, or subagent-style review patterns for the Weibo workflow.
- Agent CLI stability: load `references/agent-cli-delegation.md` when discussing or changing how Codex calls DeepSeek or another agent CLI.
- Low-cost batch advisory: load `references/agent-cli-delegation.md` when the user wants cheap-model batch review over independent chunks; keep the trigger only if the chunks can be verified and merged by Codex.

## Rubric Index

- `advisory-only`: DeepSeek output is never final by itself.
- `evidence-bound`: accept only claims grounded in supplied packet or local verification.
- `context-minimal`: send less context than Codex would otherwise retain.
- `context-not-severed`: do not delegate a task if extracting the packet would detach it from context Codex must reason over as one unit.
- `deterministic-check`: verify exit code, timeout, required headings, and concrete evidence.
- `permission-separated`: keep Codex delegate calls read-only/non-interactive even when desktop TUI is configured for interactive workspace work.
- `cli-only`: prefer direct command invocation over visual glue layers.
- `chunk-long-text`: split long documents; avoid one-shot whole-document review.
- `chinese-prose-advisory`: use DeepSeek as a language and local-context-sensitive reviewer for Chinese drafts, while Codex keeps final editorial judgment and verifies named facts.
- `weibo-gate-advisory`: DeepSeek can suggest selection/style risks, but local `send_prepared_digest.py --validate-only` and `ablate_01h_changes.py` remain the acceptance gate.
- `map-reduce-batch`: split long packets into evidence-preserving chunks, collect independent findings, then have Codex merge duplicate findings and run deterministic local checks.
- `low-cost-batch-advisory`: use cheaper DeepSeek passes only for independent triage, ablation, calibration, or second-pass review chunks; Codex remains responsible for synthesis and gates.
- `eval-three-way`: for benchmarks, compare Codex subagent, DeepSeek TUI helper, and DeepSeek direct API.
- `supervisor-worker`: Codex is the supervisor; DeepSeek is a bounded advisory worker.
- `structured-envelope`: prefer `--json-result` for automation so partial output, fallback drivers, and setup errors are visible.

Required headings are `Answer`, `Evidence`, `Uncertainty`, and `Suggested Codex Checks`.
If `deepseek` is unavailable, exits nonzero, or times out, Codex should skip delegation or retry with a smaller clearer packet rather than treating partial output as authoritative.
If the helper reports `prompt is too long`, retry with `--chunk-chars` or reduce `--max-context-chars`.
If the helper reports missing required headings, treat the result as partial; retry with smaller chunks or fewer findings before relying on it.

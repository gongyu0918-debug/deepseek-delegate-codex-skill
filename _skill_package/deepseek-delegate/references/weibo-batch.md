# Weibo Batch Ablation And Calibration

Load this file only when DeepSeek Delegate is reviewing 01H Weibo digest ablation, calibration, or candidate-selection packets.

## Fit

Use DeepSeek as a second reviewer for:

- Comparing baseline digest vs prepared digest after Codex edits.
- Explaining `QUALITY_GATE=FAIL`, repeat-topic failures, body-length problems, or soft-issue clusters.
- Calibrating candidate-selection patterns against high-flow and low-flow reference examples.
- Reviewing hotness-controlled historical calibration packets built from benchmark-account history.
- Finding duplicate same-angle chains and weaker filler items before Codex reruns the local gate.

Do not use it as the final sender, validator, or editor of record.
For 01H Weibo ablation or calibration batches, use `deepseek-v4-pro`. The helper defaults to Pro; pass `--model` only for an explicit manual compatibility override.

## Packet Contents

Prefer one Markdown packet assembled by Codex from safe artifacts:

- Current run summary: output directory, hot topic count, candidate count, selected count.
- Candidate evidence: candidate id/index, hot rank, topic, source, exact `source_tail`, original URL, short link if present, `traffic_lane`, `traffic_score`, `full_text_ok`, image count, and concise body excerpt.
- Immutable evidence: exact `immutable_blocks`, title/topic shell blocks, and `原文：<url>` binding where applicable.
- Draft evidence: baseline digest, prepared digest, selected/rejected rationale, and inline-image count.
- Gate evidence: `send_prepared_digest.py --validate-only` output and `ablate_01h_changes.py` output.
- Calibration evidence: `learned_01h_profile.md`, `source_tiers.json`, `social_high_flow_reference.md`, and benchmark-account samples when directly relevant.
- Hotness calibration evidence: `hot_at_publish`, matched hot-search word, rank at publish, best rank, first/last seen, snapshot count, lifecycle stage, same-hot post counts, one-hour reuse counts, and pair type (`same_hot_topic`, `same_hot_cluster`, or `hard_negative_hot`).

Never include cookies, SMTP app passwords, API keys, credential files, or unrelated personal data.

## Review Contract

Ask DeepSeek to return:

- Strongest keep/drop decisions with candidate ids.
- Duplicate same-angle chains and the single strongest survivor in each chain.
- Source binding risks: changed `source_tail`, missing original URL, invented source name, mismatched `原文：`.
- Validator risks: `immutable_blocks` drift, bad numbered header shape, item count outside 8-14, body-length drift, topic density problems.
- Calibration signals: what high-flow examples reward, what low-flow examples penalize, and which signal is actionable in the local pipeline.
- Hotness-controlled judgments: whether the reading gap is mostly `topic_heat_driven`, what factual `angle_label` each pair reflects, and whether the remaining signal is transferable to 01H.
- Suggested Codex checks: exact local commands or files Codex should verify next.

## Hard Boundaries

- Do not accept a DeepSeek recommendation that relaxes `immutable_blocks`, exact `source_tail`, or original URL traceability.
- Do not use DeepSeek to bypass `PREPARED_VALIDATE_OK`, `PREPARED_VALIDATION=PASS`, or `QUALITY_GATE=PASS`.
- If DeepSeek says a candidate is better but cannot cite candidate id/source/original URL evidence, treat it as style opinion only.
- If DeepSeek ignores hot-search rank, lifecycle stage, or same-topic reuse evidence in a historical pair, treat the finding as incomplete.
- Entertainment, celebrity, variety, and fandom heat can be platform signal only; do not convert it into 01H news-writing rules.
- If validator output disagrees with prose notes, trust validator markers such as `PREPARED_VALIDATE_OK`, `PREPARED_VALIDATION=PASS`, `QUALITY_GATE=PASS`, and `PREPARED_MAIL_SENT`.

## Useful Commands

Relative `--context-file` and `--out` paths are resolved against `--cwd` when it is provided.

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --packet-profile weibo-ablation `
  --task "Review this Weibo prepared digest against baseline and gate output. Identify regressions and exact Codex checks. Do not modify files." `
  --context-file .\out\llm-calibration\auto-latest\deepseek_ablation_packet.md `
  --cwd F:\Workspaces\weibo `
  --structured-result `
  --json-result `
  --out .\out\llm-calibration\auto-latest\deepseek_ablation_review.md
```

```powershell
python "$env:USERPROFILE\.codex\skills\deepseek-delegate\scripts\deepseek_delegate.py" `
  --packet-profile weibo-calibration `
  --task "Review hotness-controlled historical Weibo pairs. Return one JUDGMENT per Candidate with topic_heat_driven, angle_label, transferable_to_01h, and evidence-bound signals. Do not modify files." `
  --context-file .\out\llm-calibration\auto-latest\deepseek_calibration_packet.md `
  --cwd F:\Workspaces\weibo `
  --structured-result `
  --json-result `
  --out .\out\llm-calibration\auto-latest\deepseek_calibration_review.md
```

With `--structured-result --json-result`, treat `result.status=ok` and all chunk `structured_ok=true` as evidence that the advisory call completed cleanly. The raw review file remains advisory; local validators remain authoritative.

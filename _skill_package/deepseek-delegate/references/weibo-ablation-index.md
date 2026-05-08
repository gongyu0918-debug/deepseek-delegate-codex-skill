# Weibo Ablation Test Index

Load this file when the user wants repeated 01H Weibo ablation tests, hotness-controlled historical calibration, low-cost model routing, or subagent-style review using DeepSeek Delegate.

## Model Tiers

- Broad batch pass: use `--packet-profile weibo-ablation` with the model required by the active task.
- Hotness-controlled calibration batch pass: use `--packet-profile weibo-calibration --model deepseek-v4-pro` for the 01H workflow unless the user explicitly changes the model.
- Dispute pass: rerun only narrow packets after Codex identifies a conflict with validator evidence, source traceability, or local judgment.
- Do not use the stronger model for every candidate batch unless the low-cost pass produces ambiguous or high-impact findings.

## Mature Pattern

Use a supervisor plus advisory workers pattern:

- Codex is the supervisor. It owns repo context, secrets boundaries, file edits, validator execution, and the final decision.
- DeepSeek Delegate is an advisory worker. It receives one bounded chunk and returns evidence-bound findings.
- Batch review is map/reduce. Map over candidate groups or digest sections with stable `chunk_id` records; reduce by merging duplicate findings, keeping candidate ids and source evidence intact.
- Deterministic local validators remain authoritative for pass/fail.

This mirrors common multi-agent practice: split bounded tasks, pass minimal task-local evidence, keep one orchestrator responsible for synthesis and side effects.

## Chunking Strategy

Keep each chunk below a conservative Windows command-line range. The helper profiles use `chunk_chars=15000`, `prompt_char_limit=24000`, and a Candidate boundary regex that recognizes plain, bullet, or Markdown-heading `Candidate N:` lines; if a single candidate block exceeds the chunk limit, the helper fails closed instead of splitting its source/URL evidence. Trim the block or raise `--chunk-chars` only while staying under `--prompt-char-limit`.

Use `--json-result` for batch smoke tests so Codex can verify every chunk returned `status=ok`, `headings_ok=true`, and the expected low-cost model before reading advisory findings.

Chunk by evidence boundary, not arbitrary text, when preparing packets:

- candidate group by hot-rank bands, topic cluster, or duplicate-chain suspicion
- baseline vs prepared digest section
- validator/ablation output block
- hotness-controlled high-flow vs low-flow reference group

For historical calibration, Codex should attach hot-search control fields before delegation: `hot_at_publish`, matched hot-search word, rank at publish, best rank, first/last seen, snapshot count, lifecycle stage, same-hot post totals, one-hour reuse counts, post-per-snapshot ratio, same-hot post index, and pair type (`same_hot_topic`, `same_hot_cluster`, or `hard_negative_hot`).

Each chunk should retain enough anchors to verify a finding:

- candidate id/index
- hot rank/topic
- exact source and `source_tail`
- original URL and short link if present
- `immutable_blocks`
- prepared item text
- relevant validator or ablation lines

## Batch Ablation Questions

Ask DeepSeek to answer these repeatedly:

- Which prepared items should be dropped because they are duplicate same-angle, weak public value, too promotional, too long, or source-risky?
- Which rejected candidates are stronger replacements, and what evidence makes them stronger?
- Which changes caused validator or `QUALITY_GATE` regressions?
- Which item would survive if only one in a same-angle chain can remain?
- Which candidate evidence is insufficient for Codex to trust the recommendation?
- For historical pairs, is the gap mainly `topic_heat_driven`, or does an angle/material/fact-density difference remain after hot-search controls?

For hotness-controlled historical packets, require one line per candidate:

`JUDGMENT | pair_id=... | winner=positive|negative|unclear | confidence=0.00-1.00 | topic_heat_driven=yes|no|partial | angle_label=latest_progress|official_response|expert_explanation|on_scene_material|public_service_tip|media_commentary|background_repeat|duplicate_angle|unclear | high_reading_labels=... | low_flow_labels=... | high_reading_signals=... | low_reading_risks=... | transferable_to_01h=yes|no|partial | suggested_codex_check=...`

## Reduce Step

Codex should merge chunk outputs into:

- must-fix blockers: exact validator/source/immutable/original URL failures
- candidate swaps: drop id, add id, evidence, and expected gate impact
- style calibration: repeatable rule, not one-off wording preference
- disputed items: rerun narrow packet or inspect local artifacts
- no-action findings: style opinions without candidate/source evidence

## Hard Gates

Never let DeepSeek replace these local gates:

- `python .\scripts\send_prepared_digest.py --config .\config\weibo_digest_config.json --digest .\out\llm-calibration\auto-latest\prepared_digest.txt --candidates .\out\latest_candidates.json --validate-only`
- `python .\scripts\ablate_01h_changes.py --candidates .\out\latest_candidates.json --prepared-digest .\out\llm-calibration\auto-latest\prepared_digest.txt --baseline-digest .\out\latest_digest.txt`

Continue only when the local gate reports the validator success marker (`PREPARED_VALIDATE_OK` or `PREPARED_VALIDATION=PASS`, depending on the script path) and `QUALITY_GATE=PASS`. If later send notes disagree with validation markers, trust the validator markers.

# Packet Types

Load this file when building a DeepSeek Delegate packet or choosing chunk boundaries.

## Common Packet Shapes

- `question-only`: one self-contained question, explicit constraints, and no external context.
- `snippet`: smallest relevant code/config/log excerpt plus the local question Codex wants answered.
- `diff`: compact patch or selected changed regions, affected file paths, intended behavior, and specific review focus.
- `review-packet`: goal, constraints, relevant paths, focused evidence, and exact "Do not modify files" instruction.
- `long-text-chunks`: section-local text chunks with audience, register, and preservation constraints; each chunk must stand alone.

## Domain Packet Shapes

- `chinese-prose-chunks`: use with `chinese-prose.md`; include audience, register, named-fact preservation rules, and one bounded text section.
- `weibo-ablation-packet`: use with `weibo-batch.md`; include baseline digest, prepared digest, candidate ids, validator output, ablation output, and changed editorial decisions.
- `weibo-calibration-packet`: use with `weibo-batch.md`; include high-flow/low-flow samples, learned profile excerpts, source tiers, candidate scoring evidence, and hot-search control fields when relevant.
- `weibo-hotness-calibration-packet`: use with `weibo-batch.md` and `weibo-ablation-index.md`; include same-hot-topic, same-hot-cluster, or hard-negative historical pairs with hot-search lifecycle fields.

## Chunking Rules

- Split by evidence boundary, not arbitrary length: candidate block, diff hunk, log incident, prose section, or validator output block.
- Preserve ids, paths, URLs, source names, line numbers, timestamps, and gate markers inside the same chunk as the text they support.
- If one evidence block exceeds `--chunk-chars`, trim the block or raise the chunk size without exceeding `--prompt-char-limit`; do not split source evidence away from the claim it supports.

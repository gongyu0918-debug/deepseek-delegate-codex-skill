# Packet Types

Load this file when building a single Codex Review Helper packet.

## Common Packet Shapes

- `question-only`: one self-contained question, explicit constraints, and no external context.
- `snippet`: smallest relevant code/config/log excerpt plus the local question Codex wants answered.
- `diff`: compact patch or selected changed regions, affected file paths, intended behavior, and specific review focus.
- `review-packet`: goal, constraints, relevant paths, focused evidence, and exact "Do not modify files" instruction.
- `short-prose`: one bounded prose section with audience, register, and named-fact preservation constraints.

## Domain Packet Shapes

- `chinese-prose-section`: use with `chinese-prose.md`; include audience, register, named-fact preservation rules, and one bounded text section.

## Packet Rules

- Keep one evidence boundary per packet when possible: a diff hunk, log incident, config excerpt, snippet, or prose section.
- Preserve ids, paths, URLs, source names, line numbers, and timestamps inside the packet when they support the requested review.
- If the packet is too large for the active transport, shrink it or keep the work in Codex. Do not split it into repeated external CLI calls.

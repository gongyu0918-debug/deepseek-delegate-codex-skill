# Chinese Prose Review

Load this file only when Codex Review Helper is being used for bounded Chinese prose review.

## Good Fits

- Short Chinese drafts where native wording, register, fluency, or ambiguity matters.
- Leadership-facing copy, notices, public posts, summaries, or reports that need a second pass on tone and readability.
- Localized phrasing checks where a Chinese model may catch stiff translation, awkward word order, or register mismatch.
- Fact-risk checks on named facts present in the packet, such as dates, titles, organization names, quantities, or quoted claims.

## Boundaries

- Do not send secrets, private credentials, unrelated user data, or broad conversation history.
- Do not ask the external CLI to rewrite a whole long document. Use one small section only, or keep the work in Codex.
- Do not treat the helper as the final authority on law, medicine, finance, policy, current facts, or organization-specific truth.
- Do not accept style-only smoothing that changes named facts, obligations, amounts, dates, titles, or attribution.

## Task Packet Shape

Include only:

- Goal: proofreading, tone review, factual-risk scan, or concise rewrite suggestions.
- Audience and register: public, leadership-facing, internal, formal notice, social post, or casual note.
- Constraints: preserve named facts, preserve structure, avoid adding unsourced facts, return findings before rewrites.
- Text section: the smallest self-contained section needed.

Prefer review prompts like:

```text
Review this Chinese draft section for wording, register, ambiguity, and factual-risk issues.
Do not modify files. Preserve named facts and do not add new claims.
Return findings with evidence, then optional concise rewrite suggestions.
```

## Codex Checks

After delegation, Codex should:

- Verify every suggested factual correction against the packet or a trusted source.
- Reject rewrites that silently change names, dates, numbers, titles, quoted meaning, or responsibility.
- Merge duplicate wording findings locally if Codex reviews multiple sections itself.
- Keep the final user-facing edit consistent with the user's requested style, not the helper's style by default.

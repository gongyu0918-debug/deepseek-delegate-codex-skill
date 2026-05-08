# Weibo Rewrite Format

Preserve these invariants:

- Keep every `immutable_blocks` title/topic block.
- Normalize `〖标题〗` to `【标题】`.
- Keep exact candidate `source_tail`, for example `（某某来源01H）`.
- For video, put only the candidate `t.cn` short link immediately after `source_tail`.
- Do not paste image URLs into the body; sender embeds local images below the matching `原文：` line.
- Keep `原文：<url>` with the full-width colon.
- Reject candidates with `full_text_ok=false`.

Selection policy:

- Prepared target is 12-14 items; allow 10-11 when quality is insufficient.
- Normal same hot topic max 3 items.
- Strong hotspot max 5 items only when angles differ: latest progress, official response, expert explainer, onsite material, public-service tip, media commentary.
- Do not fill quota with weak sources or same-angle retells.
- Avoid marketing/commentary terms such as `封神`, `拉满`, `治愈`, `核心矛盾`, `公众误读`, generic `网友热议`.

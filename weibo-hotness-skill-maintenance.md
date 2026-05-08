# Weibo Hotness Calibration Skill Maintenance

This note records the local skill update for the 01H Weibo historical calibration workflow.

## Installed Skills Touched

- `C:\Users\admin\.codex\skills\weibo-01h-local-delivery\references\deepseek-calibration.md`
- `C:\Users\admin\.codex\skills\deepseek-delegate\SKILL.md`
- `C:\Users\admin\.codex\skills\deepseek-delegate\references\index.md`
- `C:\Users\admin\.codex\skills\deepseek-delegate\references\weibo-batch.md`
- `C:\Users\admin\.codex\skills\deepseek-delegate\references\weibo-ablation-index.md`

## Change Summary

- Replaced the old lane/media/hour historical pairing guidance with hot-search lifecycle control.
- Added same-hot-topic, same-hot-cluster, and hard-negative historical calibration packet concepts.
- Required DeepSeek judgment fields now include `topic_heat_driven`, `angle_label`, and `transferable_to_01h`.
- For 01H hotness-controlled calibration, `weibo-calibration` now uses or documents explicit `deepseek-v4-pro`; cheaper models are not the default for this workflow.
- Clarified that DeepSeek is advisory and must not receive cookies, SMTP credentials, API keys, credential contents, or login state.

## Source Package Notes

- `_skill_package\deepseek-delegate\references\weibo-batch.md` now documents hotness-controlled Weibo packets.
- `_skill_package\deepseek-delegate\references\weibo-ablation-index.md` now documents hotness-controlled batch review.
- `_skill_package\deepseek-delegate\references\index.md` now routes `weibo-hotness-calibration-packet`.
- `_skill_package\deepseek-delegate\scripts\deepseek_delegate.py` now sets the `weibo-calibration` profile model to `deepseek-v4-pro`.

- `_skill_package\weibo-01h-local-delivery` now contains the synced installed skill snapshot for this hotness-calibration update.

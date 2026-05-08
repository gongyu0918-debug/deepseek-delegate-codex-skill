# DeepSeek Hotness-Controlled Calibration

DeepSeek is advisory for historical Weibo calibration. Codex owns collection,
hot-search matching, deterministic labels, local validation, and final judgment.

Secret boundary:

- Set `DEEPSEEK_API_KEY` outside the repo.
- Do not write API keys into command lines, files, prompts, logs, or skill resources.
- DeepSeek receives only public Weibo text and derived features.
- Do not pass cookies, SMTP credentials, credential file contents, or login state.

Workflow:

```powershell
python .\scripts\collect_jstv_history_batches.py --start-page 241 --pages 360 --batch-pages 30 --out-dir .\out\deepseek-calibration\<run> --skip-pairs
python .\scripts\merge_jstv_history_runs.py --runs .\out\deepseek-calibration\history-120-merged .\out\deepseek-calibration\history-121-240-<run> .\out\deepseek-calibration\<run> --out-dir .\out\deepseek-calibration\history-1-600-<run>
python .\scripts\fetch_lxw_hotsearch_history.py --samples .\out\deepseek-calibration\history-1-600-<run>\history_posts.jsonl --out-dir .\out\deepseek-calibration\external-hotsearch-lxw
python .\scripts\annotate_history_hotness.py --samples .\out\deepseek-calibration\history-1-600-<run>\history_posts.jsonl --out-dir .\out\deepseek-calibration\history-1-600-<run>\hotness-v2 --snapshot-root . --external-hourly-dir .\out\deepseek-calibration\external-hotsearch-lxw
python .\scripts\build_hotness_v2_pairs.py --samples .\out\deepseek-calibration\history-1-600-<run>\hotness-v2\history_posts.hotness.v2.jsonl --out-dir .\out\deepseek-calibration\history-1-600-<run>\hotness-v2 --max-pairs 1500
python .\scripts\build_deepseek_tui_packets.py --pairs .\out\deepseek-calibration\history-1-600-<run>\hotness-v2\pairs.hotness.v2.jsonl --out-dir .\out\deepseek-calibration\history-1-600-<run>\hotness-v2\tui-packets-v5 --pairs-per-packet 2
python .\scripts\run_deepseek_tui_packet_batch.py --packets-dir .\out\deepseek-calibration\history-1-600-<run>\hotness-v2\tui-packets-v5 --out-dir .\out\deepseek-calibration\history-1-600-<run>\hotness-v2\tui-reviews-v5 --limit 1 --stop-on-fail --model deepseek-v4-pro
```

Default sample definitions:

- Positive: `read_count >= 50000`.
- Negative: `read_count < 3000`.
- First target: pages 1-600. If stable and still after 2024-05-20, extend to 800.
- Pair priority: same hot-search topic, then same hot-search cluster, then hard negatives where `hot_at_publish=true` and `read_count < 3000`.
- Ordinary lane/media/hour/length similarity is only a tie-breaker after hot-search controls.

Hotness v2 outputs:

- `history_posts.hotness.v2.jsonl`: per-post timestamp, hot-search hit state, rank at publish, best rank, lifecycle stage, and same-topic reuse fields.
- `topic_lifecycle.jsonl`: first/last seen, snapshot count, best rank, and duration for each hot topic.
- `topic_reuse_stats.jsonl`: how many posts used each hot topic and how dense reuse was within one hour.
- `pairs.hotness.v2.jsonl`: DeepSeek packet source with `same_hot_topic`, `same_hot_cluster`, and `hard_negative_hot` pair types.

DeepSeek judgment contract:

- Required fields: `topic_heat_driven`, `angle_label`, `transferable_to_01h`.
- Allowed angle labels: `latest_progress`, `official_response`, `expert_explanation`, `on_scene_material`, `public_service_tip`, `media_commentary`, `background_repeat`, `duplicate_angle`, `unclear`.
- Entertainment, celebrity, variety, or fandom heat can be recorded as platform signal, but must not become a 01H rule.

Acceptance:

- TUI packet smoke must return all required judgment fields before full batch.
- GPT-5.5 should audit at least 10% or 50 reviews, whichever is larger when available.
- If audit failure rate exceeds 15%, revise the harness prompt before using findings.
- No calibration rule enters the live send chain until a separate dry-run, prepared validation, and ablation gate pass.

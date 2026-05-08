# 01H Send Gate

Use the guarded sequence literally:

1. Run `.\scripts\run_weibo_digest.ps1 -DryRun`.
2. If it prints `SKIP_OUTSIDE_TIME_WINDOW`, stop immediately.
3. Read the fresh candidates, rule digest, editor playbook, style guide, learned profile, source tiers, and social reference.
4. Write `out\llm-calibration\auto-latest\prepared_digest.txt` and `calibration_report.md`.
5. Run prepared validation.
6. Run ablation.
7. Send only after `PREPARED_VALIDATION=PASS` and `QUALITY_GATE=PASS`.

Commands:

```powershell
python .\scripts\send_prepared_digest.py --config .\config\weibo_digest_config.json --digest .\out\llm-calibration\auto-latest\prepared_digest.txt --candidates .\out\latest_candidates.json --validate-only
python .\scripts\ablate_01h_changes.py --candidates .\out\latest_candidates.json --baseline-digest .\out\latest_digest.txt --prepared-digest .\out\llm-calibration\auto-latest\prepared_digest.txt
.\scripts\run_weibo_digest.ps1 -SendPreparedPath .\out\llm-calibration\auto-latest\prepared_digest.txt -PreparedCandidatesPath .\out\latest_candidates.json
```

Report output directory, hot topic count, candidate count, selected count, prepared digest path, ablation report path, inline image count, remaining attachment count, and whether `PREPARED_MAIL_SENT` appeared.

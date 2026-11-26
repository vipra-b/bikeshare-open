# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-25 Add `cnt_roll_std_7` (sample std of cnt over the 7 days before d, `.shift(1)` then `.rolling(7)`). Availability: every input is a count from d-7..d-1, all known at prediction time for d. LAG_WARMUP unchanged (same 7-day window). Validation R^2: ridge 0.6475 -> 0.7224 (+0.0749, MAE 832.9 -> 700.4), hgb 0.2185 -> 0.0977 (-0.1208). Test not consulted. Keep or drop: TODO (Vipra).
- 2026-11-25 Add `tests/test_contract.py::test_every_raw_column_is_classified`. Every raw column must sit in FORBIDDEN or in one of three new hand-listed sets in `src/config.py` (RAW_FEATURE_COLS, ENCODED_COLS, REDUNDANT_CALENDAR_COLS) or be `dteday`. Reason: `feature_columns()` is a denylist, so a column appended to the CSV would become a feature silently. Seeded in a throwaway copy (appended `cnt_forecast = cnt`): this test went red and no other test did. Classification of season/mnth/weekday as redundant: TODO confirm (Vipra).
- 2026-11-25 Seeded faults (Exercise 2). Removing the `raise` in `encode_weather` left the starter suite green, so added `test_weather_encoder_rejects_unknown_labels`. A `cp` into `data/raw/` from Bash passed every test, so pinned the raw sha256 in `src/config.py`, checked in `make data` and `test_raw_data_is_unmodified`.
- 2026-11-25 CLAUDE.md: added the raw-column classification rule, the raw-hash rule, and the two skill commands (41 -> 47 lines). No feature-specific rule: `cnt_roll_std_7` follows the existing shift-then-roll rule.
- 2026-11-25 `.gitignore`: removed `reports/` and `audit.jsonl` so `reports/metrics.json` and `reports/audit.jsonl` are tracked.

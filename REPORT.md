## Results

We predict daily Capital Bikeshare rides (`cnt`) using the processed Molnar mirror of the UCI data: 728 observed days from 2011-01-03 to 2012-12-31. The absent 2011-03-10 is explicitly inserted before lagging. Seven warm-up days and seven days affected by that gap are removed, leaving 714 modelling rows: 348 training days in 2011, 182 validation days in H1 2012, and 184 test days in H2 2012. Calendar, weather, and past-demand features are used; `casual` and `registered` are excluded because they sum exactly to the target.

The added feature is `cnt_roll_std_7`, the sample standard deviation of rides on days d-7 through d-1. Its test was committed before implementation and checks a hand-computed value on 2011-06-15. It uses only prior counts and shares the existing seven-day history requirement. Vipra retained it based on the validation improvement for ridge: R² 0.6475 to 0.7224 (+0.0749), with MAE falling from 832.9 to 700.4 rides. HGB worsened on validation, from R² 0.2185 to 0.0977; we report that tradeoff rather than hiding it.

`make all` reproduces the following untransformed-target results in `reports/metrics.json`. The top-level fields are After; `before_feature` contains Before. Both configurations use identical retained dates, fixed hyperparameters, and seeds; Before omits only `cnt_roll_std_7`. R² is dimensionless; MAE is daily rides.

| Feature set | Model | Validation R² | Validation MAE | Test R² | Test MAE |
|---|---|---:|---:|---:|---:|
| Before | baseline_mean | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| Before | baseline_persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Before | ridge | 0.6475 | 832.9 | 0.5833 | 947.1 |
| Before | hgb | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| After | baseline_mean | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| After | baseline_persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |
| After | ridge | 0.7224 | 700.4 | 0.6356 | 840.3 |
| After | hgb | 0.0977 | 1381.6 | -0.6959 | 2108.4 |

These are rolling daily evaluations with observed past counts available for subsequent predictions, rather than a forecast of all future days issued on a single date. The inherited pipeline also uses realized same-day weather summaries. Its scores are conditional on having those weather inputs; operational forecasts require archived weather forecasts at the actual issue time or a separate evaluation without realized weather. The figures below do not establish that operational accuracy.

The final suite has 19 passing tests. An added numerical invariant checks one- to three-feature affine restatements of `cnt`, `casual`, or `registered`; source-engineered aliases of the target and of `casual` each produce a red test and hook exit 2. The previous 18 checks stayed green with the target alias. Full actual mutation output is in `docs/SEEDED_FAULTS.md`. This catches renamed arithmetic leakage, not arbitrary nonlinear transformations or unavailable weather.

The inherited test suite scored the held-out set on every run of its mean-baseline smoke test, and the inherited metrics already contained test scores. We therefore cannot claim that the test set was historically touched once. The repeated smoke test now uses validation. We froze the inherited feature choice and the human-selected ratio transformation before the final transformed test run; the later untransformed reruns verify fixed results rather than guide further tuning.

## Headline finding

The leaky demonstration reaches R² 1.000 by reconstructing `cnt` from its components and is invalid. With temporal evaluation, the mean baseline reaches test R² -2.1441, showing the cost of the demand-level shift. Before the new feature, ridge reaches 0.5833 against persistence at 0.5099, yet loses on MAE (947.1 versus 840.1). After adding past-week volatility, ridge reaches 0.6356 and MAE 840.3; persistence remains 0.5099 and 840.1. HGB reaches -0.6959 and MAE 2108.4, worse than persistence but better than the mean baseline. Trees fit demand levels observed in 2011 and struggle to extrapolate growth into 2012. Vipra kept volatility for its validation gain; the negative HGB change remains part of the finding.

## Exercise 4: target transformation

The inherited validation-only comparison tried ratio to the trailing seven-day mean, difference from yesterday, and log1p. HGB validation R² was 0.7483, 0.5642, and -0.0282 respectively, against 0.0977 without transformation. On 2026-11-25, before the final transformed test run, K-Pat selected the ratio and judged its use of known past counts defensible. It predicts `z = cnt / cnt_roll_7`; forecasts return to rides by multiplying predicted z by the trailing mean. This removes the changing demand level from the target while allowing the inverse operation to scale beyond 2011 ride levels.

The frozen ratio was evaluated using `python -m src.train --target-transform ratio --touch-test`; its saved output is `reports/target_transform_ratio.json`. Both baselines remain on the original ride scale and are unchanged. The committed main `reports/metrics.json` remains the untransformed pipeline.

| Target | Model | Validation R² | Validation MAE | Test R² | Test MAE |
|---|---|---:|---:|---:|---:|
| Ratio | baseline_mean | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| Ratio | baseline_persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |
| Ratio | ridge | 0.6128 | 857.3 | 0.1977 | 1323.3 |
| Ratio | hgb | 0.7483 | 685.5 | 0.6280 | 832.8 |

The ratio lets HGB compete: its test R² becomes 0.6280 and MAE 832.8, near untransformed ridge at 0.6356 and 840.3. Ratio ridge worsens to 0.1977 and 1323.3, so the transformation is not a universal improvement. The availability argument is sound for rolling prediction with known prior counts; it does not fix the weather-availability limitation. The validation comparison determined the transformation, and these test numbers will not be used for another search.

## Exercise 5: ridge vs persistence

The original ridge comparison is weak for deployment under an absolute-error objective: R² improves by 0.0734 over persistence, but MAE is 107.0 rides worse (947.1 versus 840.1). With the retained volatility feature, ridge improves test R² by 0.1257 while MAE is effectively tied (840.3 versus 840.1, a 0.2-ride disadvantage at printed precision). This supports ridge if avoiding large squared errors justifies its data and maintenance costs; it does not show a typical absolute-error advantage. Our recommendation is to retain persistence as the operational reference until a rolling evaluation with weather forecasts, uncertainty intervals, and stated error costs establishes a material benefit. K-Pat adopted this conclusion on 2026-11-25: keep persistence unless reducing large errors justifies ridge’s complexity. The agent drafted the numeric argument; the deployment judgement is the human decision.

## Attribution

The inherited work names Claude Opus 5.5 in Claude Code (hosted; parameter count and context were not recorded), and its SDK audit used hosted `sonnet` (exact version unspecified). The continuation uses Codex (GPT-6; parameter count undisclosed). The local reviewer uses `qwen3.5:9b-q4_K_M` through Ollama as `bikeshare-coder`, with a 65536-token context. CLI/SDK runs are configured for disabled thinking and low effort. Initial connection/configuration and native-MLX startup attempts were interrupted without a verdict; they are not counted as successful audits. The completed configured reviewer took 13 turns and reported all five checks passing on Vipra’s incoming snapshot; its exact output is in `docs/AUDIT.md` and `reports/teammate-auditor.json`.

Agent-generated work:

- The starter pipeline, tests, hook, subagent, and starter `new-feature` skill were supplied by the assignment.
- The inherited agent added `cnt_roll_std_7`, its test-first check, raw-column classification and raw-hash enforcement, the seeded-fault evidence, the `seed-fault` skill, target-transform code, and the earlier hosted SDK audit. Existing commits and `docs/SEEDED_FAULTS.md` record that provenance, including manually invoked hooks rather than automatic firing in its original harness.
- Codex added reproducible before/after metrics, both baselines to transformed output, fresh estimator instances, the validation-only smoke check, the frozen ratio evaluation artifact, the numerical alias-leakage test and its red/green/hook evidence, Parquet support and configuration for the SDK auditor, corrected weather-availability documentation, and this report draft. Codex wrote the prose and numeric comparisons; K-Pat’s methodological choices are already recorded; the shared human audit verdict remains outstanding; the final SDK result is now complete.

Human/project decisions traced to `docs/DECISIONS.md`:

- The starter specifies predicting daily rides, excluding target components and unverified lags, using chronological splits, and comparing both baselines. These are course-supplied project choices, not newly invented personal decisions.
- Vipra kept the past-week volatility feature on validation and confirmed the redundant calendar-column classification in commit `334fc3f`.
- K-Pat chose the ratio transformation and judged its use of prior counts defensible before final transformed test evaluation, recorded in the dated continuation decision.
- K-Pat chose to keep persistence unless reducing large errors justifies ridge’s complexity, recorded in the dated continuation decision. The designated human reviewer's own verdict on the peer auditor's numerical findings remains pending; the partners confirmed one joint submission, and Vipra is the proposed reviewer of the continuation diff.

The inherited hosted SDK audit remains preserved in git history. The final own-repository SDK audit completed successfully against source commit `62898c5` using local `qwen3.5:9b-q4_K_M` (`bikeshare-coder`, 65536 context), in 17 turns and 34.4 minutes including SDK structured-output enforcement. The actual schema-valid result reports no leakage, valid temporal evaluation, both baselines, reproducibility, no findings, and high confidence. Its trace confirms `make all test` executed ingestion, feature generation, training and all 19 tests; the numerical identity tool checked exactly the 15 active features and found no identities. The SDK returned final JSON through its documented text fallback (structured_output was null); the saved row was independently validated against REPORT_SCHEMA. Regenerated metrics are unchanged. No transformed test evaluation was repeated.

The configured local reviewer’s incoming-snapshot output is verbatim in `docs/AUDIT.md`. Its actual trace ran 18 tests and the features/train stages; its prose additionally claimed ingest execution, which the trace does not show. The audit record explicitly corrects that provenance claim. Separate fixed-pipeline validation did run ingest through `make all`.

For the confirmed joint submission, our plan is one shared human audit paragraph; the assignment page does not explicitly define joint versus per-person allocation. Vipra is the proposed reviewer of the continuation. K-Pat’s feature-transform and deployment choices are already recorded; no extra blanket approval is requested. The actual human audit verdict remains pending.

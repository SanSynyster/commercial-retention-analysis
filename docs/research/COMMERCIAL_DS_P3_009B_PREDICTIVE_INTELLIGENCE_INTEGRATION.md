# COMMERCIAL_DS_P3_009B — Predictive Intelligence Streamlit Integration

**Status:** closed after independent review acceptance (PASS WITH CONDITIONS; conditions corrected); no model training performed.
**Evidence type:** Historical prediction. Development results were used for model selection; the July–November 2011 results are a previously examined exploratory holdout.

## Implemented functionality

Added a **Predictive Intelligence** page to the existing local Streamlit application. It presents three interactive views:

- **Model comparison:** switch between pooled March–June development folds and the previously examined July–November replay; select ROC-AUC or average precision for the chart; inspect Logistic C, frequency, Random Forest, HistGradientBoosting, XGBoost and LightGBM, selection status, top-decile precision, and available paired ranking intervals.
- **Global SHAP:** explore global mean absolute and signed attributions, development-fold summaries, and optionally compare selected-feature mean absolute attributions across the exploratory holdout months. Attribution is expressed in positive-class purchase-probability units. Correlated-feature caveats and the fold rank-stability range are shown.
- **Calibration:** compare uncalibrated RF with the intercept-only research candidate; select development or exploratory holdout; inspect pooled scores, development month-level Brier/log-loss, and paired customer-cluster intervals.

The page uses the neutral **Historical prediction** heading; development and previously examined exploratory holdout labels remain beside their evaluation controls and results. It is explicitly predictive, not causal. No confirmatory randomised label is applied to these results.

Model comparison pools March–June development results (17,221 snapshots), while calibration uses the matched April–June evaluation population (12,961 snapshots); the page now states this population difference to contextualize small metric differences. The signed difference and confidence-bound columns in paired ranking intervals use explicit `+0.0000` formatting. The independent Claude review returned **PASS WITH CONDITIONS**; the formatting condition was corrected and covered by a focused rendered-table regression test.

## Bundle provenance and privacy

`app_data/p3_predictive_v1.json` is a stable, canonical JSON projection with schema validation and a content SHA-256. The builder reads four exact, fixed source paths and copies only allowlisted aggregate values. It rejects missing inputs, raw-file checksum mismatches, manifest disagreement, invalid numeric values, prohibited customer-level keys, and absolute/private paths. The checked-in bundle contains only report references, relative source artifact names, digests and aggregate metrics; no absolute local path, row-level data, customer identifier, model binary or prediction record.

| Source report | Explicit source artifact | Raw-file SHA-256 | Verification |
|---|---|---|---|
| P3-002 | `source_data/uci_online_retail_ii/p3_002_outputs/p3_002_aggregate_results.json` | `f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb` | Report-recorded raw-file digest; checked against sibling manifest |
| P3-003 | `source_data/uci_online_retail_ii/p3_003_outputs/p3_003_aggregate_results.json` | `0d9280d4926b3819df02b33cb2c67d7decc560db57517ba8add65964e811d0d5` | Exact report-cited aggregate filename; pinned digest checked against raw bytes and sibling manifest |
| P3-004 | `source_data/uci_online_retail_ii/p3_004_outputs/p3_004_aggregate_results.json` | `a04d7cd1919af7ae9304c4d2b3817597558680f7a3d82971de23fb2711919d47` | Exact runner aggregate filename; raw digest checked against sibling manifest |
| P3-005 | `source_data/uci_online_retail_ii/p3_005_outputs/p3_005_aggregate_results.json` | `d4fa81bbb8bae9c484917981fa15fc94591668f96d427926030fe25d29b72484` | Exact runner aggregate filename; raw digest checked against sibling manifest |

The P3-002 report documents its exact raw aggregate digest. P3-003 identifies its aggregate and SHA-256 manifest; P3-004/005 runners and reports identify their aggregate/manifest convention. Their aggregate raw-file digests were pinned here after matching the explicit artifact to its sibling manifest. Paths are constants in `src/p3_predictive_bundle.py`; no directory discovery, timestamp ranking, or filename fallback occurs. If private sources are unavailable, rebuild-dependent tests skip and the builder exits with a clear missing-source error. Committed bundle schema, checksum and integrity tests always run.

Rebuild command (requires those private sources):

```sh
.venv/bin/python -m src.p3_predictive_bundle --build
```

The process reads aggregate JSON/manifest files only; it does not retrain models or access raw transactions, private prediction rows, individual SHAP rows, or the P3-008 test artifacts.

## Predictive benchmark displayed

The task is the established-customer next-month qualifying-purchase prediction using 11 point-in-time features and the fixed prior 365-day window. Development comprises 17,221 pooled out-of-fold snapshots from 4,670 customers; the July–November exploratory period contains 21,672 snapshots from 4,999 customers. Frequency is an uncalibrated ranking baseline; probability-only metrics are not fabricated for it.

| Model | Development ROC-AUC | Development AP | Development top-decile precision | Explored holdout ROC-AUC | Explored holdout AP | Holdout top-decile precision |
|---|---:|---:|---:|---:|---:|---:|
| Logistic C | 0.7752 | 0.5291 | 62.68% | 0.7660 | 0.5659 | 69.35% |
| Frequency | 0.7623 | 0.4949 | 61.81% | 0.7454 | 0.5252 | 68.80% |
| Random Forest | 0.7824 | 0.5395 | 64.02% | 0.7732 | 0.5758 | 70.28% |
| HistGradientBoosting | 0.7806 | 0.5367 | 63.55% | 0.7742 | 0.5759 | 70.00% |
| XGBoost | 0.7814 | 0.5380 | 64.13% | 0.7745 | 0.5772 | 70.65% |
| LightGBM | 0.7806 | 0.5372 | 64.07% | 0.7743 | 0.5778 | 70.28% |

Random Forest remains the development reference because it had the highest four-fold mean AP (0.53942) among the compared models; XGBoost and LightGBM did not meet the predeclared adoption criteria. Their development paired AP differences versus RF are small and their intervals include zero. The P3-002 customer-cluster intervals for RF versus Logistic C and HGB versus Logistic C are available in the app; P3-003 adds booster-versus-RF intervals. They condition on fitted predictions/configurations, do not include selection uncertainty, and are not future-period uncertainty. The previous holdout is shown separately as exploratory evidence and did not select the models.

## SHAP and calibration summaries

The highest development mean absolute SHAP contributions are purchase dates over 365 days (0.0369 probability units), purchase occasions over 365 days (0.0288), qualifying gross merchandise over 365 days (0.0196), and days since last qualifying purchase (0.0183). This is attribution magnitude in the fitted RF probability output, not causal importance. The top five features were stable across the development folds; 11-feature pairwise rank correlations ranged from 0.945 to 1.000. April and May used the same fitted RF; SHAP attribution can be split among correlated substitute features, so individual ranks are not uniquely assigned.

For P3-005’s matched April–June evaluation rows (12,961 snapshots), uncalibrated RF Brier/log loss were 0.12377/0.40185; intercept-only were 0.12189/0.39584. Paired customer-cluster intervals for intercept-only minus uncalibrated were −0.00188 (Brier 95% CI [−0.00262, −0.00111]) and −0.00601 (log loss [−0.00835, −0.00384]). Monthly Brier differences were +0.00065 for April (worse), −0.00481 for May and −0.00149 for June. The pooled gain is chiefly May and then June, not a uniform time-specific improvement.

Intercept-only recalibration is a **provisional research candidate**, not selected for deployment. Uncalibrated RF remains the reference. A monotone intercept shift normally preserves within-period ranking, and so does not inherently improve fixed-capacity targeting. July–November calibration metrics are only an exploratory replay; calibration-pool transfer to the full-training model is an additional assumption. No calibration method is presented as a validated operational probability correction.

## Verification and limits

- Added bundle schema, checksum, explicit source mapping/hash, missing-source, deterministic rebuild, frequency-metric applicability, and private-field tests.
- Added Streamlit page AppTest coverage for rendering, visible evidence labels and holdout interaction.
- The committed bundle rebuilt byte-for-byte from the current pinned private aggregates; content SHA-256: `40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd`.
- Predictive model results are historical and use folds involved in selection. The July–November period was previously examined, not independent confirmation. The app does not score new customers. Purchase propensity and SHAP do not estimate incremental response to contact; no customer-level explanations are created.
- Calibration results cover few development periods and show mixed month-level changes. P3-006 value/timing results are not included in this page and remain unvalidated historical forecasts.

No source transactions, private prediction rows, private SHAP rows or model binaries were changed or added to the application. P3-009B does not modify frozen M1/M2 experiments or prior research outputs.

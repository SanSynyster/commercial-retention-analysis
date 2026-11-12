# M5-003 — Purchase Propensity Dashboard

## Result

The Purchase Propensity placeholder is now a functional aggregate-only page. It presents the new-customer M1 Day-21 result separately from the established-customer M2 monthly prediction, shows the M2 model comparison and monthly test variation, and describes M2's exploratory sequential intercept adjustment. No model was fit and no customer-level prediction artifact was loaded or created.

## Verified research results

### M1 — New-customer second-purchase prediction

The unit is a customer in the approved 12-month qualifying-history acquisition proxy. The decision is Day 21 after the first qualifying purchase; the outcome is a second qualifying purchase in `(Day 21, Day 111]`. Training had 304 customers (90 positive); chronological test had 208 (97 positive).

The predeclared three-feature Model C ROC-AUC was **0.5189**, with a customer-bootstrap 95% interval **[0.4410, 0.5963]**. Its predeclared lower-bound criterion was **not met**. Gross-only Model B ROC-AUC was 0.5439. Brier scores were 0.2779 (constant), 0.2761 (gross-only), and 0.2743 (three-feature). The M1-010 corrected Model C calibration diagnostic is intercept 0.172 and slope 0.376 (approximate SE 0.45 and 0.53).

The page explicitly describes the weak/inconclusive discrimination evidence, small samples, training/test prevalence shift (29.61% to 46.63%), and M1-008's prior descriptive examination of test prevalence. The M1 task is not directly compared with M2 as if the AUCs came from a shared evaluation.

### M2 — Established-customer monthly purchase prediction

The unit is an eligible customer-month snapshot with a preceding fixed 365-day feature window and a mature 30-day purchase outcome. Training comprised 25,647 snapshots from 4,808 customers (4,573 positives); July–November test comprised 21,672 snapshots from 4,999 customers (5,092 positives). Positive prevalence was 17.83% in training and 23.50% in test; 4,265 customers appeared in both periods.

| Model | ROC-AUC | Average precision | Brier | 10% precision | 10% lift |
| --- | ---: | ---: | ---: | ---: | ---: |
| A — constant / random expectation | 0.50000 | 0.23496 | 0.18296 | 23.50% | 1.00× |
| B — RFM logistic | 0.75995 | 0.54830 | 0.14968 | 67.34% | 2.87× |
| C — full 11-feature logistic | 0.76599 | 0.56595 | 0.14744 | 69.28% | 2.95× |

Model C's customer-clustered percentile interval is **[0.75646, 0.77490]** (2,000 resamples). The constant model has no ranking; its capacity precision/lift is the analytical random-selection expectation. The monthly chart shows verified July–November ROC-AUC for Models B and C alongside a separate monthly prevalence chart.

### Exploratory sequential calibration

The fixed Model C received an intercept-only adjustment based on labels whose 30-day outcomes were mature strictly before each target decision. Calibration pools were 8,640 snapshots for September, 8,640 for October, and 17,328 for November. July/August were unadjusted warm-up months. This is an exploratory re-analysis of the previously examined holdout.

For pooled September–November (13,032 snapshots, 4,796 customers), Brier score changed from **0.16815 raw** to **0.16369 adjusted**; adjusted-minus-raw difference was −0.00446, with a customer-clustered 95% interval **[−0.00553, −0.00340]**. Mean predicted probability moved from 17.76% to 19.68% while observed prevalence was 26.76%; the risk-scale underprediction gap narrowed from 9.01 to 7.08 percentage points. Underprediction remained. Original full-test Model C calibration intercept/slope were 0.411/0.973; the adjusted pooled Sep–Nov diagnostic was 0.435/0.949. Month-specific intercepts preserve within-month ranking, but can reorder observations across months.

## Bundle and provenance

`app_data/propensity_summary_v1.json` is a 14.2 KB versioned aggregate bundle. It includes only compact task definitions, model and partition metrics, five monthly aggregate rows, calibration pool/month summaries, limitations, and provenance hashes. It contains no customer IDs, prediction rows, feature matrices or model coefficients.

The builder `src/propensity_summary_bundle.py` requires configurable paths to the M2-008 run manifest and M2-012 aggregate summary, verifies their exact expected hashes and the tracked M1/M2 report and protocol hashes, then extracts an allowlisted set of fields. The bundle records these source hashes plus the upstream M2 dataset, dataset-manifest, builder, model, prediction and protocol hashes. Runtime uses only the checked-in JSON bundle.

Canonical data-section SHA-256 (also independently pinned in the validator):

`a4fcc6d60cac7ddc2de3a5c62c457c9f706237792b42b1bdffa1715d09535562`

The pin detects a content difference from this approved application bundle; it does not authenticate application source code changed together with the bundle.

## Implementation and verification

- `app/views/purchase_propensity.py` implements the separate M1/M2 sections, aggregate comparison table, monthly AUC/prevalence displays, and calibration summary with expandable methodology and limitations.
- `app/streamlit_app.py` routes Purchase Propensity to the new page; `app/views/placeholders.py` retains only the two unimplemented pages.
- `src/propensity_summary_bundle.py` provides the source-hash-checked builder, runtime schema validator, independent content pin, and aggregate loader.
- `tests/test_propensity_summary_bundle.py` and `tests/test_purchase_propensity_page.py` cover approved values, source integrity, task separation, row-level data exclusion, rehashed tampering, error handling and page rendering.
- **Verification:** focused M5/app tests: 29 passed; full repository suite: 156 passed, 1 existing Java-dependent Spark test skipped. A fresh Python 3.11 checkout with no local research data passed all 29 focused app/bundle tests with 2 expected private-input rebuild skips; the Purchase Propensity page rendered in AppTest and the headless app returned HTTP 200.

Rebuild using the commands in `app/README.md` after setting `LOCAL_DATA_DIR` to the local directory holding the verified M2 aggregate artifacts. Normal app runtime does not require that directory.

## Limitations and next milestone

M1 and M2 answer different questions and use different evaluation units, horizons, eligibility rules and sample sizes. M2 has repeated customers, a previously examined July–November holdout, and seasonal prevalence drift; its fixed-model calibration adjustment was evaluated on the same holdout and did not remove underprediction. Neither propensity nor retrospective targeting establishes causal CRM effectiveness.

The next milestone is **M5-004 — Targeting Explorer**, using only the already reviewed aggregate M3 policy comparison and its tie-breaking disclosure. Keep customer selections and predictions outside the app bundle.

# COMMERCIAL_DS_P3_002 — Temporal ML Benchmark and First Experiments

**Corrected closeout:** 2026-11-13. The seven-month-later July–November comparison below is the previously examined M2 holdout and is explicitly exploratory, not independent confirmation.

## Task and source data

The task is to rank established customers at month-start decision time `T` by whether they make at least one corrected-contract qualifying merchandise purchase in `[T, T + 30 days)`. M2-004 snapshots use only qualifying purchase information from `[T − 365 days, T)`, the existing 11 M2 features, and the existing mature-label/coverage rules. Feature generation and the M2 population/label definitions were not changed. Customer ID is used only for snapshot uniqueness, deterministic score-tie handling and clustered uncertainty; it is not a predictor.

Frozen M2-004, its manifest, and M2-008 model/prediction/run-manifest artifacts were hash-checked by the runner. The published M2 Model C holdout AUC, average precision and Brier score reproduced within `1e-9`. Frozen M1/M2 source, results and protocols remain unchanged.

## Time-ordered validation and maturity

Training decisions are available from January–June 2011; July–November 2011 is the previously examined holdout. Folds were formed only after comparing each stored `outcome_window_end_exclusive` timestamp with the validation decision boundary. Training labels had to be mature, complete and binary, with `label_end < validation T`. Validation outcomes also had to be complete, mature and binary. Features remain point-in-time and all imputers are fit only on each training fold.

| Validation month | Training decision months | Training snapshots / customers | Latest training decision / label end | Validation snapshots / customers / positives |
|---|---|---:|---|---:|
| March | January | 4,205 / 4,205 | Jan 1 / Jan 31 | 4,260 / 4,260 / 755 |
| April | January–March | 12,686 / 4,407 | Mar 1 / Mar 31 | 4,318 / 4,318 / 739 |
| May | January–March | 12,686 / 4,407 | Mar 1 / Mar 31 | 4,319 / 4,319 / 901 |
| June | January–May | 21,323 / 4,695 | May 1 / May 31 | 4,324 / 4,324 / 868 |

The strict maturity rule excludes February labels at the March 1 training boundary (their outcome window ends March 3), and excludes April labels at the May 1 boundary (their outcome window ends exactly May 1). The M2-008 frozen training cutoff uses `label_end <= 2011-07-01`, whereas these development folds use strict `<`. This is conservative and does not create leakage. At the final July cutoff, the frozen M2 training can include June 1 snapshots whose 30-day label ends exactly July 1; a strict rule would exclude that boundary cohort. Fold definitions were not changed to improve results.

The four validation periods contain 17,221 snapshots from 4,670 distinct customers and 3,263 positives (18.95%). Repeated customer observations and overlapping outcome windows remain; months are not independent replications. The UCI data has no untouched later decision period: all available July–November outcomes were already examined. Independent future generalisation cannot be evaluated with this dataset.

## Models, preprocessing and experiment counts

- **Frozen Logistic C:** exact M2-007 settings and all 11 features. For development folds it is fitted anew with the frozen `log1p`, training-median imputation and standardisation procedure. For holdout comparison, the original frozen M2-008 predictions are reused, not refit.
- **Frequency:** `qualifying_purchase_dates_365d`, used only as an uncalibrated ranking score. In each month, ties are resolved by customer key ascending, as in the approved M3-002 policy. Brier, log loss and probability calibration are not applicable to this raw ranking.
- **Random Forest:** fold-local `log1p` and median imputation; no scaling. The selected configuration is 200 trees, depth 8, minimum leaf size 20, `max_features="sqrt"`, no class weighting, `n_jobs=1`, seed 20261113.
- **HistGradientBoostingClassifier:** fold-local `log1p` and median imputation; no scaling. The selected configuration is learning rate 0.05, 7 leaf nodes, 100 iterations, minimum leaf size 50, L2 regularisation 1.0, **`early_stopping=False`**, seed 20261113. Automatic early stopping is disabled for every candidate so fold size cannot change stopping behaviour.

Three bounded configurations per tree family were evaluated on each of four origins: 12 RF candidate fits and 12 HGB candidate fits. Configuration selection used only mean validation-month average precision. The selected HGB configuration's mean fold AP was 0.53741; RF's was 0.53942. The implementation performed **30 estimator fits per benchmark execution**: 24 tree candidate-fold fits, 4 fold-specific logistic reference fits, and 2 selected-tree fits on January–June for exploratory holdout scoring. Two clean benchmark executions were run for reproducibility (60 fit calls total).

The experiment uses random seed 20261113, 1,000 customer-cluster CRM bootstrap replicates and 1,000 paired ranking bootstrap replicates (PCG64, same seed). Environment: Python 3.11.14, scikit-learn 1.8.0, NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1. RF used one worker. Final first execution took **57.28 seconds wall**, 76.11 seconds user CPU and 17.34 seconds system CPU. macOS `/usr/bin/time -l` reported **330,104,832 bytes maximum resident set size** and **261,424,064 bytes peak memory footprint**; these are the tool's separately named measurements, not interchangeable RSS labels.

## Development validation results

The selected configurations are evaluated on the same four folds used for selection. These pooled out-of-fold metrics are therefore tuning estimates, potentially optimistic; they are not a nested-CV final estimate.

| Model | ROC-AUC | Average precision | Brier | Log loss |
|---|---:|---:|---:|---:|
| Logistic C, refit per fold | 0.7752 | 0.5291 | 0.1237 | 0.4027 |
| Frequency ranking | 0.7623 | 0.4949 | N/A | N/A |
| Random Forest | **0.7824** | **0.5395** | **0.1223** | **0.3989** |
| HistGradientBoosting | 0.7806 | 0.5367 | 0.1227 | 0.3998 |

Month-level AUC/AP by validation fold (Logistic C / Frequency / Random Forest / HistGradientBoosting):

| Month | Logistic C | Frequency | Random Forest | HistGradientBoosting |
|---|---:|---:|---:|---:|
| March | .777 / .511 | .766 / .480 | .781 / .512 | .778 / .512 |
| April | .756 / .488 | .747 / .465 | .764 / .500 | .763 / .497 |
| May | .789 / .575 | .773 / .534 | .796 / .589 | .793 / .584 |
| June | .780 / .546 | .764 / .507 | .788 / .557 | .789 / .557 |

### Paired ranking uncertainty

The bootstrap samples customer trajectories with replacement and applies customer multiplicity weights to all of each customer's rows. It preserves pairing across model scores. Intervals are conditional on the fitted scores and selected configurations; they do **not** include hyperparameter-selection uncertainty or independent future-period uncertainty.

| Development comparison | ΔAUC, 95% interval | ΔAP, 95% interval |
|---|---:|---:|
| Random Forest − Logistic C | +0.0071 [0.0042, 0.0102] | +0.0104 [0.0059, 0.0151] |
| HistGradientBoosting − Logistic C | +0.0054 [0.0027, 0.0081] | +0.0076 [0.0034, 0.0122] |

These intervals describe customer resampling variation within the same four periods. Because those periods selected the configurations, they are conditional and not confirmatory evidence.

## Previously examined holdout: exploratory comparison

Holdout population: 21,672 mature customer-month snapshots, 4,999 customers, 5,092 purchases (23.50% prevalence). The predictions/outcomes have already informed M2-008, M2-012, and M3-002. No holdout outcome was used to select a P3-002 setting, but this retrospective replay is not an untouched test.

| Model | ROC-AUC | Average precision | Brier | Log loss | Mean predicted probability | Observed prevalence |
|---|---:|---:|---:|---:|---:|---:|
| Frozen Logistic C | 0.7660 | 0.5659 | 0.1474 | 0.4649 | 0.1769 | 0.2350 |
| Frequency ranking | 0.7454 | 0.5252 | N/A | N/A | N/A | 0.2350 |
| Random Forest | 0.7732 | 0.5758 | 0.1460 | 0.4601 | 0.1755 | 0.2350 |
| HistGradientBoosting | 0.7742 | 0.5759 | 0.1462 | 0.4603 | 0.1746 | 0.2350 |

Monthly AUC/AP (July to November):

| Month | Prevalence | Logistic C | Frequency | Random Forest | HistGradientBoosting |
|---|---:|---:|---:|---:|---:|
| July | 18.75% | .777 / .544 | .756 / .500 | .785 / .554 | .787 / .554 |
| August | 18.38% | .812 / .570 | .788 / .523 | .819 / .574 | .820 / .576 |
| September | 24.12% | .773 / .578 | .754 / .540 | .782 / .590 | .782 / .588 |
| October | 24.04% | .742 / .529 | .725 / .497 | .750 / .539 | .752 / .542 |
| November | 32.14% | .751 / .638 | .734 / .600 | .750 / .646 | .752 / .645 |

The ranking differences against Logistic C are positive on this holdout, but the customer bootstrap is conditional on the fitted models and this historical period:

| Exploratory holdout comparison | ΔAUC, 95% interval | ΔAP, 95% interval |
|---|---:|---:|
| Random Forest − Logistic C | +0.0072 [0.0051, 0.0095] | +0.0099 [0.0066, 0.0132] |
| HistGradientBoosting − Logistic C | +0.0082 [0.0062, 0.0104] | +0.0100 [0.0075, 0.0126] |

These intervals quantify resampling of customers in already inspected months; they do not establish independent prospective generalisation.

## Calibration findings

The frozen M2 implementation and reports were not changed. P3 uses a separate diagnostic: joint logistic regression of outcome on the logit of the raw prediction, BFGS with `gtol=1e-6`, maximum 5,000 iterations, and a post-fit stationarity tolerance of `1e-5` on the infinity norm of the score gradient. An estimate is reported only if it is finite, stationary within that tolerance, and the information matrix is positive and adequately conditioned (minimum eigenvalue above `1e-10`; condition number below `1e10`). Constant scores are explicitly non-identifiable. Nonstationary or ill-conditioned fits are failures, not estimates. This avoids treating a strict optimizer flag alone as a failed calibration estimate while leaving M1/M2 frozen diagnostics untouched.

All three probability models produced estimable calibration fits in this final run; optimizer success was true. Intercept and slope are separate diagnostics and do not alter predictions. Frequency has no probability interpretation and no calibration fit.

| Evaluation set | Logistic C intercept / slope | Random Forest intercept / slope | HistGradientBoosting intercept / slope |
|---|---:|---:|---:|
| Four development folds pooled | 0.293 / 0.977 | 0.330 / 0.995 | 0.352 / 1.008 |
| Exploratory July–November holdout | 0.411 / 0.973 | 0.461 / 0.997 | 0.507 / 1.024 |

Overall mean predicted probability minus observed prevalence is negative for every model. On holdout, observed-minus-predicted gaps are 5.80 pp for Logistic C, 5.94 pp for RF and 6.04 pp for HGB. Training prevalence was 17.83%, versus 23.50% on holdout; the gap is consistent with prevalence drift and underprediction. The calibration intercept is a conditional score-based diagnostic; it does not prove that prevalence drift alone caused the underprediction. Holdout prevalence rose from 18.75% in July to 32.14% in November, so a single pooled calibration summary masks temporal drift. No recalibration was fitted or applied.

## CRM capacity results and interpretation

At each month and capacity, the policy selects `ceil(capacity × eligible snapshots)` with deterministic customer-key tie breaking. Pooled precision, purchase capture and lift are snapshot-weighted over the five months.

| Capacity | Policy | Precision | Purchase capture | Lift |
|---:|---|---:|---:|---:|
| 5% | Logistic C | 82.24% | 17.56% | 3.50× |
| | Frequency | 80.77% | 17.24% | 3.44× |
| | Random Forest | 82.34% | 17.58% | 3.50× |
| | HistGradientBoosting | **82.89%** | **17.69%** | **3.53×** |
| 10% | Logistic C | 69.35% | 29.56% | 2.95× |
| | Frequency | 68.80% | 29.32% | 2.93× |
| | Random Forest | **70.28%** | **29.95%** | **2.99×** |
| | HistGradientBoosting | 70.00% | 29.83% | 2.98× |
| 20% | Logistic C | 54.89% | 46.74% | 2.34× |
| | Frequency | 54.20% | 46.15% | 2.31× |
| | Random Forest | **55.63%** | **47.37%** | **2.37×** |
| | HistGradientBoosting | 55.42% | 47.19% | 2.36× |

Customer-cluster intervals show why ranking improvements should not be equated with large or certain CRM gains. For tree minus Logistic C precision at 5/10/20% capacity, RF differences were +0.09 pp [−1.39, +1.66], +0.92 [−0.09, +2.26], and +0.74 [+0.16, +1.58]; HGB differences were +0.64 [−0.55, +1.94], +0.65 [−0.23, +1.93], and +0.53 [+0.02, +1.36]. These are paired 1,000-resample percentile intervals conditional on the five fixed months, predictions, selected settings and deterministic tie rule. They exclude model-selection and future-time uncertainty. The advantage over frequency is also small in point terms, although conditional intervals at several capacities are positive. None of these retrospective propensity metrics estimate incremental campaign impact.

## Reproducibility, artifacts and limitations

Two clean runs used separate external output directories. After removing only `created_utc` and runtime/timing fields, their saved aggregate JSON objects matched **exactly**; this supports deterministic scientific results in this pinned environment, but the full files are not bitwise identical because timestamp and runtime metadata differ. Both runs used Python 3.11.14, sklearn 1.8.0, NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, seed 20261113 and RF `n_jobs=1`. Frozen Logistic C remains hash-verified and unchanged. The frozen sklearn `penalty="l2"` setting emits its known deprecation warning and was retained for exact M2 consistency.

The final aggregate JSON and manifest are outside Git under `source_data/uci_online_retail_ii/p3_002_outputs/`; aggregate SHA-256 is `f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb`. They contain aggregate metrics/configuration/provenance only. No customer predictions, raw transactions, identifiers or fitted model binaries were saved.

Scientific limitations are material: only four short development origins were available; those same folds selected configurations; there is no untouched future period in UCI Online Retail II; the published holdout was already examined; customers repeat across snapshots and outcome windows overlap. Cluster bootstraps condition on the fitted scores and do not include hyperparameter-selection uncertainty, period-to-period variation or external generalisation. The ranking gains are consistent in these historical evaluations, but CRM precision/capture advantages are small and uncertain, and no causal campaign benefit is established.

## Recommendation

XGBoost and LightGBM are approved as a **bounded exploratory extension**, not as required deployment improvements. Do not begin that extension before independent review of this corrected milestone. If pursued, keep a small search, the same mature-label temporal discipline, and an explicit exploratory label; additional packages cannot compensate for the lack of an untouched future evaluation period.

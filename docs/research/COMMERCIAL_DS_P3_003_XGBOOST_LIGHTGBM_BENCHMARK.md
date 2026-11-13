# P3-003 XGBoost and LightGBM Benchmark Extension

## Objective and decision

This bounded exploratory experiment tests whether XGBoost or LightGBM improve next-month qualifying-purchase ranking over the existing Random Forest (RF) and HistGradientBoosting (HGB) development references. The predeclared rule was to advance a new model only when development AP exceeds RF, its paired customer-cluster 95% interval is wholly above zero, CRM targeting and calibration do not materially worsen, and gains are reasonably consistent by fold. Neither new model meets that rule; retain RF as the development reference. July–November results did not influence configuration selection or this decision.

## Prediction task and data

We used the frozen M2 established-customer monthly snapshot dataset: month-start decisions, next 30-day qualifying-purchase label, the fixed 365-day history definition, existing 11 point-in-time features, and the existing complete/mature label rules. Unknown labels were not treated as negatives. Model preprocessing used the existing log1p transform and median imputation fitted inside each training fold. Identifiers, labels, timestamps and split columns were excluded from the feature allowlist. Snapshot keys were unique and frozen prediction keys were checked for one-to-one alignment.

The supplied artifact has 25,647 training snapshots and a 21,672-snapshot July–November 2011 holdout. The holdout had already been examined in prior M2/P3 work and is replayed here only as exploratory evidence. No untouched future period exists within this dataset. Repeated customers appear across monthly snapshots; the temporal folds are not independent customer samples, and 30-day outcome windows overlap in calendar time.

## Development folds and maturity

We preserved the four existing March–June origins. For each fold, the validation month begins at its earliest decision time; training rows must have a decision before that boundary, complete mature labels, and `outcome_window_end_exclusive < boundary`. This strict inequality is unchanged from P3-002. The frozen M2 train/test protocol separately uses `<= 2011-07-01`; the more conservative development rule excludes any label ending exactly at the cutoff. Actual timestamps were checked. Training histories and labels were available before the corresponding validation point.

| Validation month | Train snapshots | Train customers | Validation snapshots | Positives | Prevalence | Latest training label end (exclusive) |
|---|---:|---:|---:|---:|---:|---|
| 2011-03 | 4,205 | 4,205 | 4,260 | 755 | 0.177 | 2011-01-31 00:00:00 |
| 2011-04 | 12,686 | 4,407 | 4,318 | 739 | 0.171 | 2011-03-31 00:00:00 |
| 2011-05 | 12,686 | 4,407 | 4,319 | 901 | 0.209 | 2011-03-31 00:00:00 |
| 2011-06 | 21,323 | 4,695 | 4,324 | 868 | 0.201 | 2011-05-31 00:00:00 |

The folds reuse earlier eligible snapshots in expanding training windows. Their validation snapshots are calendar-separated, but customer independence is not assumed. Hyperparameter selection on these four fold outcomes means the resulting uncertainty intervals are conditional and optimistic with respect to selection. No holdout value enters the selector.

## Candidate configurations and selection

Each family had three explicitly predeclared candidates; every candidate was fit on all four development folds. Selection was the highest unweighted mean fold AP, with ties resolved by lower configuration index. There was no early stopping or hidden validation split. XGBoost used CPU `hist`, one thread and fixed seed 20261113. LightGBM used deterministic CPU/column-wise execution, one thread, `subsample_freq=1` so row subsampling is active, and the same seed. Both were wrapped in the same fold-local tree preprocessing pipeline. The full benchmark made 40 estimator fit calls: 24 new-family candidate-fold fits, 8 fixed RF/HGB fold reference fits, 4 logistic fold fits, and 4 final full-training fits for holdout replay.

**XGBoost grid (learning rate, depth, estimators, minimum child weight, row fraction, column fraction, L1, L2):**

| Config | Parameters | Mean fold AP |
|---:|---|---:|
| 0 | `{"learning_rate":0.05,"max_depth":3,"n_estimators":150,"min_child_weight":5,"subsample":0.8,"colsample_bytree":0.8,"reg_alpha":0.0,"reg_lambda":2.0}` | 0.5378 |
| 1 | `{"learning_rate":0.03,"max_depth":4,"n_estimators":250,"min_child_weight":10,"subsample":0.85,"colsample_bytree":0.8,"reg_alpha":0.1,"reg_lambda":5.0}` | 0.5386 |
| 2 | `{"learning_rate":0.1,"max_depth":2,"n_estimators":100,"min_child_weight":1,"subsample":0.8,"colsample_bytree":0.9,"reg_alpha":0.0,"reg_lambda":1.0}` | 0.5367 |

**LightGBM grid (learning rate, leaves, estimators, minimum child samples, column fraction, row fraction, bagging frequency, L1, L2):**

| Config | Parameters | Mean fold AP |
|---:|---|---:|
| 0 | `{"learning_rate":0.05,"num_leaves":7,"n_estimators":100,"min_child_samples":50,"colsample_bytree":0.8,"subsample":0.8,"subsample_freq":1,"reg_alpha":0.0,"reg_lambda":2.0}` | 0.5373 |
| 1 | `{"learning_rate":0.03,"num_leaves":15,"n_estimators":200,"min_child_samples":50,"colsample_bytree":0.9,"subsample":0.9,"subsample_freq":1,"reg_alpha":0.1,"reg_lambda":5.0}` | 0.5373 |
| 2 | `{"learning_rate":0.1,"num_leaves":7,"n_estimators":100,"min_child_samples":100,"colsample_bytree":0.8,"subsample":0.8,"subsample_freq":1,"reg_alpha":0.0,"reg_lambda":1.0}` | 0.5340 |

Selected XGBoost configuration 1 (mean-fold AP 0.5386); selected LightGBM configuration 1 (mean-fold AP 0.5373). LightGBM configurations 0 and 1 were effectively tied, differing by approximately 0.00005 in mean development-fold AP. RF and HGB were reproduced using the frozen P3-002 configuration 0; Logistic C predictions were reused for the published holdout and refit with frozen settings on each development fold. Frequency uses the existing deterministic ranking/tie policy. No P3-002 configuration or reported metric was changed.

## Pooled predictive performance

### Development out-of-fold

| Model | ROC-AUC | AP | Brier | Log loss | Calibration intercept / slope | Mean predicted / observed prevalence |
|---|---:|---:|---:|---:|---:|---:|
| Logistic C | 0.7752 | 0.5291 | 0.1237 | 0.4027 | 0.293 / 0.977 | 0.153 / 0.189 |
| Frequency | 0.7623 | 0.4949 | NA | NA | not applicable | not applicable |
| Random Forest | 0.7824 | 0.5395 | 0.1223 | 0.3989 | 0.330 / 0.995 | 0.152 / 0.189 |
| HistGradientBoosting | 0.7806 | 0.5367 | 0.1227 | 0.3998 | 0.352 / 1.008 | 0.151 / 0.189 |
| XGBoost | 0.7814 | 0.5380 | 0.1225 | 0.3999 | 0.301 / 0.968 | 0.151 / 0.189 |
| LightGBM | 0.7806 | 0.5372 | 0.1225 | 0.4004 | 0.292 / 0.960 | 0.150 / 0.189 |

### Exploratory replay of the previously examined holdout

| Model | ROC-AUC | AP | Brier | Log loss | Calibration intercept / slope | Mean predicted / observed prevalence |
|---|---:|---:|---:|---:|---:|---:|
| Logistic C | 0.7660 | 0.5659 | 0.1474 | 0.4649 | 0.411 / 0.973 | 0.177 / 0.235 |
| Frequency | 0.7454 | 0.5252 | NA | NA | not applicable | not applicable |
| Random Forest | 0.7732 | 0.5758 | 0.1460 | 0.4601 | 0.461 / 0.997 | 0.176 / 0.235 |
| HistGradientBoosting | 0.7742 | 0.5759 | 0.1462 | 0.4603 | 0.507 / 1.024 | 0.175 / 0.235 |
| XGBoost | 0.7745 | 0.5772 | 0.1459 | 0.4603 | 0.452 / 0.980 | 0.174 / 0.235 |
| LightGBM | 0.7743 | 0.5778 | 0.1458 | 0.4602 | 0.458 / 0.984 | 0.174 / 0.235 |

Frequency is a raw ranking score, so Brier score, log loss, calibration and mean probability are not applicable. Probability metrics are reported for classifiers without post-hoc calibration.

## Fold stability

| Development month | RF AP | HGB AP | XGBoost AP | LightGBM AP |
|---|---:|---:|---:|---:|
| 2011-03 | 0.5122 | 0.5117 | 0.5097 | 0.5069 |
| 2011-04 | 0.5003 | 0.4967 | 0.4973 | 0.4964 |
| 2011-05 | 0.5887 | 0.5838 | 0.5864 | 0.5835 |
| 2011-06 | 0.5566 | 0.5574 | 0.5610 | 0.5623 |

XGBoost exceeded RF AP only in June; LightGBM did so only in June. Neither improved in March–May, so fold consistency is weak. The exploratory holdout monthly AP replay is shown for transparency only:

| Holdout month | RF AP | HGB AP | XGBoost AP | LightGBM AP |
|---|---:|---:|---:|---:|
| 2011-07 | 0.5536 | 0.5538 | 0.5555 | 0.5562 |
| 2011-08 | 0.5736 | 0.5764 | 0.5761 | 0.5760 |
| 2011-09 | 0.5898 | 0.5880 | 0.5894 | 0.5903 |
| 2011-10 | 0.5393 | 0.5421 | 0.5427 | 0.5440 |
| 2011-11 | 0.6460 | 0.6453 | 0.6465 | 0.6468 |

## Paired customer-cluster ranking uncertainty

Intervals use 1,000 paired customer-trajectory bootstrap resamples with customer multiplicity weights, seed 20261113. Point deltas and percentile 95% intervals use the same saved score aggregates and preserve model pairing across snapshots. These intervals condition on fitted models and selected configurations; they do not include configuration-selection uncertainty, temporal process uncertainty or independent future generalisation.

| Development comparison | ΔROC-AUC (95% CI) | ΔAP (95% CI) |
|---|---:|---:|
| XGBoost - Random Forest | -0.0010 [-0.0025, +0.0007] | -0.0014 [-0.0038, +0.0011] |
| XGBoost - HistGradientBoosting | +0.0008 [-0.0008, +0.0024] | +0.0014 [-0.0011, +0.0044] |
| LightGBM - Random Forest | -0.0017 [-0.0034, -0.0000] | -0.0023 [-0.0051, +0.0006] |
| LightGBM - HistGradientBoosting | +0.0000 [-0.0018, +0.0018] | +0.0005 [-0.0021, +0.0033] |

Both new models fall short of RF in development AP: XGBoost ΔAP is −0.0014 (95% CI −0.0038 to +0.0011), and LightGBM ΔAP is −0.0023 (−0.0051 to +0.0006). Neither has a positive point improvement, much less a lower confidence bound above zero. Comparisons with HGB are included in the artifact; their development AP intervals also include zero.

Exploratory holdout paired results are shown only as a descriptive replay; the period was previously examined and these intervals are not independent confirmation.

| Exploratory comparison | ΔROC-AUC (95% CI) | ΔAP (95% CI) |
|---|---:|---:|
| XGBoost - Random Forest | +0.0013 [+0.0002, +0.0025] | +0.0014 [-0.0004, +0.0031] |
| XGBoost - HistGradientBoosting | +0.0003 [-0.0007, +0.0013] | +0.0013 [-0.0003, +0.0030] |
| LightGBM - Random Forest | +0.0011 [-0.0001, +0.0022] | +0.0020 [+0.0002, +0.0037] |
| LightGBM - HistGradientBoosting | +0.0000 [-0.0010, +0.0012] | +0.0019 [+0.0001, +0.0037] |

The small positive holdout point estimates (and two positive conditional AP intervals) are post hoc replay results. They cannot establish success, correct for selection, or override development-based model selection.

## CRM capacity targeting

Each month is ranked independently at the listed contact capacity, with deterministic customer-ID tie handling inherited from the existing targeting policy. Values are precision / capture recall / lift. Lift is calculated relative to the pooled observed purchase prevalence across the evaluated months.

### Development folds

| Model | 5% precision / capture / lift | 10% precision / capture / lift | 20% precision / capture / lift |
|---|---:|---:|---:|
| Logistic C | 0.760 / 0.201 / 4.01 | 0.627 / 0.331 / 3.31 | 0.484 / 0.511 / 2.56 |
| Frequency | 0.751 / 0.198 / 3.96 | 0.618 / 0.326 / 3.26 | 0.473 / 0.499 / 2.49 |
| Random Forest | 0.762 / 0.201 / 4.02 | 0.640 / 0.338 / 3.38 | 0.488 / 0.515 / 2.58 |
| HistGradientBoosting | 0.761 / 0.201 / 4.02 | 0.636 / 0.336 / 3.35 | 0.490 / 0.518 / 2.59 |
| XGBoost | 0.759 / 0.200 / 4.00 | 0.641 / 0.339 / 3.38 | 0.488 / 0.515 / 2.58 |
| LightGBM | 0.774 / 0.204 / 4.08 | 0.641 / 0.338 / 3.38 | 0.487 / 0.514 / 2.57 |

### Exploratory published holdout

| Model | 5% precision / capture / lift | 10% precision / capture / lift | 20% precision / capture / lift |
|---|---:|---:|---:|
| Logistic C | 0.822 / 0.176 / 3.50 | 0.694 / 0.296 / 2.95 | 0.549 / 0.467 / 2.34 |
| Frequency | 0.808 / 0.172 / 3.44 | 0.688 / 0.293 / 2.93 | 0.542 / 0.462 / 2.31 |
| Random Forest | 0.823 / 0.176 / 3.50 | 0.703 / 0.299 / 2.99 | 0.556 / 0.474 / 2.37 |
| HistGradientBoosting | 0.829 / 0.177 / 3.53 | 0.700 / 0.298 / 2.98 | 0.554 / 0.472 / 2.36 |
| XGBoost | 0.835 / 0.178 / 3.56 | 0.706 / 0.301 / 3.01 | 0.559 / 0.476 / 2.38 |
| LightGBM | 0.836 / 0.179 / 3.56 | 0.703 / 0.299 / 2.99 | 0.558 / 0.475 / 2.37 |

Paired CRM bootstrap intervals versus both RF and HGB are in the aggregate (`crm_bootstrap_vs_rf_and_hgb`). For example, development XGBoost minus RF precision differences at 5%, 10%, and 20% are −0.0035, +0.0012 and +0.0003; the respective 95% intervals all include zero. LightGBM’s 5% precision point difference is +0.0116 but its interval is −0.0046 to +0.0244. These are small, uncertain ranking/targeting differences and do not estimate incremental campaign effect or causal uplift.

## Calibration

Joint logistic calibration intercept and slope are estimated from each model’s pooled probabilities; intercepts above zero reflect systematic underprediction at the observed prevalence, while slopes near one indicate approximate spread calibration. Calibration is diagnostic only; no calibration map was fitted or selected. The raw frequency score has no probability calibration diagnostic. The holdout observed purchase prevalence is 0.235, while the new model mean predictions are about 0.174; all classifiers underpredict under this prevalence drift. The development observed prevalence is 0.189, while new model means are about 0.150. Brier/log loss and calibration results therefore reflect both ranking and prevalence shift. There is no calibration procedure selected using this already examined holdout.

## Computational cost, complexity and reproducibility

Experiment computation took 21.7s, including bootstrap calculations and excluding aggregate file writing, on the recorded local environment. Across 12 candidate fold fits, XGBoost fit/predict time was 0.831s/0.044s and LightGBM was 1.077s/0.139s; selected full-training fits took 0.182s and 0.262s respectively. Holdout inference took 0.024s for XGBoost and 0.096s for LightGBM. Their fitted complexity was 250 depth-4 trees for XGBoost and 200 trees of up to 15 leaves for LightGBM. These timings are environment-specific; they do not justify added package/build/maintenance burden given the performance results.

Recorded versions: Python 3.11.14, scikit-learn 1.8.0, XGBoost 3.2.0, LightGBM 4.7.0, NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1. Research dependencies are pinned in `requirements.txt`. In the reviewed macOS environment, both the XGBoost and LightGBM wheels depend on Homebrew's OpenMP runtime; install it with `brew install libomp`. Two successive executions with the final configuration produced exact equality in selected settings, all reported predictive metrics, development/holdout bootstrap outputs, monthly results, training settings and provenance; elapsed wall time differed (22.2s and 21.9s). The run uses seed 20261113, one CPU thread per estimator, XGBoost CPU histogram trees and deterministic LightGBM execution. This demonstrates repeatability in the present environment, not a guarantee of bitwise reproducibility across platforms or dependency builds. No model binary or customer-level prediction output was saved. Aggregate artifacts and provenance are outside Git under `source_data/uci_online_retail_ii/p3_003_outputs/`.

## Scientific limitations and recommendation

- Development folds were used to select one of three configurations per family; the bootstrap conditions on the selected scores and understates total model-selection uncertainty.
- The July–November 2011 holdout was examined before this experiment. It is exploratory replay only, not an untouched test or independent confirmation.
- UCI Online Retail II contains no untouched future period for prospective confirmation. A new split from already examined data would not restore independence.
- Repeated customers, overlapping label windows, seasonal and prevalence drift limit interpretation of pooled month-level evidence.
- Predictive targeting metrics do not establish incremental campaign impact; uplift requires randomized treatment/control data.
- The LightGBM row subsampling was explicitly activated with `subsample_freq=1`; both new libraries used explicit no-early-stopping settings and fixed CPU thread counts.

**Recommendation:** retain Random Forest as the development reference. Neither XGBoost nor LightGBM meets the predeclared adoption criteria on development evidence. No algorithm is selected on holdout outcomes. Any later validation should be prospective or externally sourced; calibration should be evaluated under future prevalence conditions before operational probability use.

## Reproducibility artifact

Compact aggregate metrics, per-fold candidate results, selected settings, bootstrap summaries, timing and provenance are stored in `p3_003_aggregate_results.json` with a SHA-256 manifest outside the repository. These aggregate files contain no customer identifiers or predictions. The report’s displayed values are generated from that saved aggregate.

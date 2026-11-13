# COMMERCIAL_DS_P3_001 — Existing ML Recovery and Benchmark Readiness

**Scope:** Read-only inventory of modelling assets and evidence. No model was trained, tuned, or scored for this investigation.

## 1. Repository and Git state

- Development repository: `commercial-retention-analysis-dev`; branch `main`; HEAD `8d89a6b6050cfc44f186f6dbf0a3c19ee66a3d7e`.
- Working tree was clean at inspection. Local `main` is 25 commits ahead of `origin/main`; no history or remote state was changed.
- Public curated repository was not inspected or modified.
- Main M2 assets are `src/monthly_customer_snapshots.py`, `src/monthly_purchase_baselines.py`, `src/monthly_purchase_calibration.py`, `src/targeting_metrics.py`, `src/targeting_bundle.py`; focused tests include `tests/test_monthly_customer_snapshots.py`, `tests/test_monthly_purchase_baselines.py`, and `tests/test_monthly_purchase_calibration.py`.
- Frozen M1 code/protocol/results are in `src/day21_cohort.py`, `src/day21_baseline.py`, and the M1 P2 research reports. M1 was not modified.

## 2. Algorithm inventory and historical evidence

| Algorithm | Existing code | Previously evaluated | Reusable | Recommended action |
|---|---|---|---|---|
| Logistic Regression | Yes: frozen M2 A/B/C in `src/monthly_purchase_baselines.py`; historical lapse and M1 code too | Yes: frozen M2 C AUC 0.76599; M1 C AUC 0.5189; historical lapse comparisons | High as frozen reference and preprocessing/evaluation reference; preserve M2 baseline unchanged | Keep M2 C fixed as comparator; implement P3 candidate fits separately |
| Random Forest | Yes: `src/churn_prediction.py`; notebooks 05 and 06 | Yes, historical non-M2 lapse/second-purchase results; not on corrected M2 snapshots | Partial: sklearn pipeline patterns exist, but target/features/protocol and preprocessing differ | Include one modest, bounded candidate in first M2 development comparison |
| HistGradientBoosting | Yes: `src/churn_prediction.py`; notebooks 05 and 06 | Yes, historical non-M2 results; no corrected-M2 benchmark | Partial: estimator is present; categorical preprocessing in old pipeline is unsuitable for M2's numeric features without adaptation | Include as first boosted-tree candidate |
| XGBoost | No source implementation or notebook result found | No | No | Defer until sklearn candidates establish a reason to add a dependency |
| LightGBM | No source implementation or notebook result found | No | No | Defer; avoid expanding dependency set for initial comparison |
| CatBoost | No source implementation or notebook result found | No | No | Defer; no categorical M2 features justify it initially |
| SHAP | No implementation or result found | No | No | Defer until candidate model and explanation question are fixed |

Repository-wide code, notebooks, and Git history search found no M2 boosted-tree experiment, hyperparameter search, or cross-validation implementation. Git history for `src/churn_prediction.py` shows only the legacy implementation commit; the advanced models in the lapse notebook and module are existing exploratory work, not recovered corrected-M2 experiments.

### Recovered lapse and earlier propensity results

`src/churn_prediction.py` builds rolling customer-month rows and compares class-weighted logistic regression, a 120-tree Random Forest, and HistGradientBoosting. It predicts `lapsed_next_90_days` (no qualifying historical-V1 order in a future 90-day window), using 15 features: recency, age/activity, order frequency/value/quantity/lines, second-purchase timing, repeat/high-value flags, country group, and snapshot month. The module uses pre-snapshot history; labels inspect future orders. It performs a chronological snapshot split (last 30% of dates by default), trains candidates, then selects the “best” using test/top-20% precision with AUC secondary. This is **test-set model selection**, so its reported test metrics are optimistically selected and are not unbiased comparison evidence. The old inclusive end-date label and legacy order/value taxonomy also differ from corrected V2.

The historical report `reports/ml_lapse_risk_summary.md` gives 9,425 test rows and AUCs 0.753 (HistGradientBoosting), 0.757 (Random Forest), and 0.750 (logistic), with reported top-10% precision 75.8%, 74.8%, and 74.3%. It explicitly flags older V1 status and conflicting lapse figures elsewhere (0.759/0.692 versus 0.753/0.690). Therefore these numbers establish that the algorithms once ran; they are not dependable evidence for choosing an M2 estimator. Notebook 06 contains another HistGradientBoosting/Random Forest specification with different settings, further confirming implementation divergence.

Notebook 05 is an earlier 60-day second-purchase task based on first-order baskets, product-description keyword features and a first-purchase-date 80/20 split. It is not M1 Day-21 or established-customer M2. Its global-median-derived feature (`first_order_above_median_revenue`) and eligibility/split rules merit review before reuse; there is no evidence in that notebook of nested time-aware tuning or corrected-M2 comparability.

## 3. M2 modelling foundation

- **Snapshot builder:** `src/monthly_customer_snapshots.py` builds month-start customer snapshots from canonical merchandise purchase occasions. Customers must have a full 365-day history and be active in that lookback. Features use occasions strictly before decision time `T`; the target is any qualifying purchase in `[T, T+30 days)`. Coverage and complete label maturity are explicit. The frozen corrected-V2 Parquet and manifest are at `source_data/uci_online_retail_ii/monthly_customer_snapshots_m2_004.parquet` and its manifest, outside the repository.
- **Feature contract:** ordered `FEATURE_COLUMNS` has 11 numeric columns: recency; 365-day occasion and date counts; 365-day gross merchandise, average basket value/quantity, average basket diversity, unique products and median interpurchase interval; and 90-day occasion count and gross merchandise. No identifiers, timestamps, label, partition, or coverage columns may enter the model matrix.
- **M2 partition:** protocol `docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md` fixes train to Jan–Jun 2011 (25,647 snapshots, 4,808 customers; 4,573 positives), and test to Jul–Nov 2011 (21,672 snapshots, 4,999 customers; 5,092 positives). Training label availability cutoff is 2011-07-01. 4,265 customers overlap partitions. Test outcomes have already been inspected.
- **Models/preprocessing:** A is training-prevalence constant; B is logistic RFM on three predictors; C is L2 logistic regression on all eleven. The frozen M2 preprocessor applies `log1p`, training-only median imputation after transformation, then training-only centering/scaling. C is the frozen reference (AUC ≈0.766, AP ≈0.566, Brier ≈0.1474). Do not alter or refit it as part of the original M2 experiment.
- **Artifacts:** M2-008 models/preprocessing JSON, run manifest, and row-level test predictions Parquet exist under `source_data/uci_online_retail_ii/m2_008_baseline_outputs/`, outside Git. Their pinned hashes are recorded in M2-008 and M2-012 reports. M2-012 verifies them and demonstrates sequential intercept calibration using previously examined July–November predictions.
- **Evaluation utilities:** `monthly_purchase_baselines.py` provides ROC-AUC, average precision, Brier, calibration diagnostic/bands, top 5/10/20% capacity precision/lift with boundary ties included, month-level summaries, feature/probability drift, and a customer-cluster bootstrap AUC. The bootstrap weights every repeated row of a sampled test customer by cluster multiplicity (2,000 draws, seed 20261112). `monthly_purchase_calibration.py` has strict historical-label availability filtering and sequential intercept calibration. `src/targeting_bundle.py` and frozen M3 targeting work supply paired, customer-cluster bootstrap comparisons against simple frequency ranking with capacity and overlap analysis.
- **Limits of reuse:** M2 fitting is purpose-built, not a general estimator registry or sklearn `Pipeline`. `FittedPreprocessor` is specialized to the frozen logistic protocol. New estimators can reuse snapshot construction, feature contract, partition/maturity logic, and most metric/bootstrap/ranking functions, but need a separate train-fitted transformer and evaluation path that accepts arbitrary candidate prediction vectors. Preserve M2 files and hashes.

## 4. Data and dependencies

The M2-004 Parquet and manifest and frozen M2-008 artifacts are available outside Git. Only file presence and aggregate reports were checked; transaction contents and customer-level artifact rows were not read. Available corrected-M2 rows span decision months Jan–Nov 2011, but the fixed M2 experiment only trains through June and the inspected holdout is July–November. M2-012 used mature July/August labels for September calibration, then expanding historical pools for October and November, confirming the narrow chronology and maturity constraints.

The repository `.venv` has Python 3.11.14 and scikit-learn 1.8.0. `requirements.txt` pins NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, scikit-learn 1.8.0, and PyArrow 24.0.0 among its environment. XGBoost, LightGBM, CatBoost, and SHAP are absent from the environment and not declared. The fallback system Python 3.14 has no scikit-learn. First experiments can use the pinned venv and sklearn without new libraries.

## 5. Scientific comparability and risks

Any new candidate evaluated on the M2-008 July–November test predictions/labels is exploratory because those outcomes and the Model C result have already influenced project decisions. Do not call it independent confirmation, and do not use that test for hyperparameter selection, model selection, or claims of improved generalisation. A retrospective comparison there can be retained as a clearly labelled diagnostic only.

The available January–June training set has six monthly decision anchors. A leakage-respecting expanding-origin development scheme must respect label maturity, not just snapshot order. For example: fit on January snapshots and validate March; fit on January–February and validate April; fit on January–March and validate May; fit on January–April and validate June. For a validation decision at `T`, include training labels only if their full outcome window has matured by `T` (use the documented strict `end < T` rule consistently); evaluate the validation month only after its own 30-day outcomes mature. This leaves at most four short origins. This creates at most a few short origins, not robust seasonal replication. The earliest folds are small; avoid broad searches and report fold-specific counts and uncertainty. Since feature snapshots repeat customers, estimate uncertainty with paired customer-cluster resampling within each origin and summarize origin variation separately; do not treat month rows as independent replicates.

For the July onward period, a truly forward simulation would require fitting/tuning only on earlier matured labels and predicting each later decision before its outcomes mature. But those outcomes have already been examined, and M2-012 has used some as calibration history. It can support exploratory replay or diagnostics, not fresh confirmation. Genuinely independent predictive confirmation requires later future observations with mature 30-day labels and a predeclared protocol before accessing those outcomes; external confirmation would require a separate comparable population and harmonized contracts.

Other risks: overlapping 30-day outcome windows; strong customer overlap across train/test; seasonality/prevalence shift (training 17.83%, test 23.50%); correlated recency, frequency, purchase-date, 90-day and lifetime-window proxies; tuning many algorithms on six origins; and giving trees untransformed differently while failing to refit imputation within each fold. No random split is appropriate. The fixed July–November holdout must remain labelled “previously examined”.

## 6. Initial fair benchmark recommendation

Start with a compact comparison on the same eleven M2 predictors and the same mature monthly rows:

1. Frozen Model C logistic regression as a reference (do not change its M2 artifact).
2. A simple frequency ranking using `qualifying_purchase_occasions_365d` (and, if the existing frozen CRM comparator specifies it, the exact established frequency policy); preserve deterministic tie rules.
3. One shallow/modest Random Forest.
4. One HistGradientBoostingClassifier.

Use fold-local median imputation for missing interpurchase interval and a shared feature allowlist. Logistic should retain the frozen `log1p`/standardized reference implementation; tree inputs may use raw nonnegative numeric features or a predeclared shared `log1p` representation, but compare these choices only within training folds and keep the reference’s frozen preprocessing untouched. Tune a very small predeclared grid over tree depth/leaf size, number of trees/iterations, and learning rate using expanding-origin folds. Do not introduce XGBoost/LightGBM/CatBoost until this baseline comparison demonstrates a concrete gap or limitation.

For each origin, report ROC-AUC and average precision for ranking; Brier and calibration-in-the-large/slope for probabilities; precision, lift, and purchase capture at CRM capacities 5/10/20%; and model-versus-frequency paired customer-cluster intervals. Fit any calibration mapping using only matured out-of-fold predictions available before the corresponding validation/test decision. Choose a candidate using development folds only; then freeze model/settings/calibration before any later replay. Do not assert that the old M2 holdout has become confirmatory.

## 7. SHAP readiness

The eleven engineered features are named, numeric and meaningful as purchasing behaviour summaries. Saved M2 model JSON also preserves names, but the current M2 fitting path mostly carries NumPy arrays and does not offer a generic named transformed-feature interface. A P3 path should retain the original feature names through fold-local preprocessing and associate transformed columns to their source names. Logistic coefficients and grouped permutation reliance provide immediate, simpler explanations.

Tree SHAP would be efficient for fitted Random Forest/HistGradientBoosting variants subject to library/model-version compatibility; linear SHAP is available conceptually for logistic. SHAP is not installed. Do not calculate SHAP until a model is selected and explanation scope is fixed. Summarize global attribution distributions and a small set of aggregate archetypes; local explanations should be generated only for approved internal review and never include customer IDs, raw rows, or exported customer-level records. Correlated recency/frequency/monetary features can split or redistribute attribution; SHAP values explain a fitted model’s allocation under a background distribution, not causal effects. Prefer grouped interpretation/sensitivity checks and avoid causal language.

## 8. Immediate next implementation milestone

**P3-002 — M2 expanding-origin estimator benchmark.** First write a short, predeclared protocol specifying folds and label-maturity rule, compact candidate grid, frequency baseline/tie policy, fold-local preprocessing, metrics, calibration-only-on-prior-OOF rule, paired customer bootstrap, and explicit exploratory status of every reused period. Then add an isolated runner that reads the already verified external M2 cohort, fits logistic reference-compatible plus Random Forest and HistGradientBoosting candidates on the expanding origins, and writes aggregate reports and any row-level predictions only outside Git. Do not alter M1/M2 code or frozen artifacts. Do not spend this milestone on SHAP or optional boosting packages.

**P3-003 — frozen candidate replay and readiness decision.** After development-fold selection is frozen, replay the selected candidate on the already examined July–November period only as an explicitly exploratory historical comparison, including temporal, calibration, uncertainty and CRM capacity metrics against frozen Model C and the exact frequency policy. Document limitations and identify the need/date for a genuinely future confirmation. Keep all test-driven tuning out of this step. If a live stream of data becomes available, predeclare a later confirmatory protocol before its labels mature.

This sequencing starts model work immediately while keeping the baseline, evaluation chronology and claims auditable. No MLflow, cloud runtime, or orchestration layer is warranted for this local dataset and small candidate set.

# COMMERCIAL-DS-001 — Evaluation Protocol

Part of the [recovery index](README.md). This protocol is binding for all studies in the [research programme](COMMERCIAL_DS_001_RESEARCH_PROGRAMME.md). Temporal terms (`T`, `h`, maturity, `D_end`) are defined in the [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md).

---

## 1. Evidence classes (every claim must carry one)

| Class | Definition | Allowed language |
| --- | --- | --- |
| **Observed** | A direct computation on the data (counts, sums, shares) | "X was", "X accounted for" |
| **Inferred** | A statistical estimate with uncertainty about a population or process | "estimated X (95% CI a–b)"; associational wording only |
| **Model-based** | Output of a fitted predictive/probabilistic model | "the model predicts / ranks"; never "causes" |
| **Simulated** | Produced by simulation, synthetic effects or synthetic scale-ups | "in simulation", "under synthetic effect δ" |
| **Assumed** | A parameter not estimable from data (margin, campaign cost, effect size) | "assuming X" |
| **Recommendation** | A business suggestion | Must cite which evidence classes support it; **cannot rest on Simulated or Assumed evidence alone** |

Causal language ("drives", "increases", "impact of") is prohibited unless the evidence comes from a real randomised experiment. There is none in this dataset.

---

## 2. Study lifecycle

1. **Pre-registration** (`research/<study>/PREREGISTRATION.md`, written before any outcome is examined):
   - questions and hypotheses;
   - population and eligibility;
   - unit;
   - windows;
   - primary and secondary metrics;
   - baselines;
   - the model family and tuning budget;
   - holdout definition;
   - decision thresholds for "better than baseline";
   - known limitations.
2. **Development:** EDA and tuning on development data only.
3. **Freeze:** commit the final model specification and the pre-registration hash.
4. **Holdout evaluation:** run once and record it in the run manifest.
5. **Report:** generated tables, interpretation, negative findings, limitations, and the evidence class of every claim.
6. **Independent review:** a different session or person checks the report against the manifest (see the [roadmap](COMMERCIAL_DS_001_ROADMAP.md) gates).

Deviations from the pre-registration are allowed but must be listed in a **"Deviations"** section with reasons.

---

## 3. Dataset versioning

- Every result names its dataset (`v1`, `v2`, `v2c`), its contract version and the source file hash. All of these come from the run manifest.
- V1 results are **legacy** unless a study explicitly compares versions.
- Changing a contract version invalidates downstream results. They must be regenerated, not edited.

---

## 4. Temporal design and leakage prevention

| Rule | Requirement |
| --- | --- |
| L1 Point-in-time features | Features at anchor T use only data with timestamp < T. Enforced by a **truncation test**: recompute features on data truncated at T and require equality |
| L2 Point-in-time population statistics | Thresholds (high-value cut-off, scalers, encoders, quantiles) are fitted on training data or at T, never on the full period |
| L3 Label maturity | Only labels with `T + h ≤ D_end` |
| L4 Purging | For a training anchor `T_tr` and the earliest evaluation anchor `T_ev`, require `T_tr + h ≤ T_ev` (the gap equals the label horizon) |
| L5 Embargo for repeated customers | Customers appear in train and holdout at different anchors (allowed); CIs use a **customer-clustered bootstrap** |
| L6 Rolling-origin validation | Hyperparameters and model choice are selected by rolling-origin CV within the development period (≥3 origins where data permits) |
| L7 No test-set selection | Model choice uses validation folds only (fixes audit D-3) |
| L8 Scoring vs evaluation | Current-anchor scores (unlabelled) are produced separately from evaluation anchors (fixes audit D-4) |
| L9 Calendar features | Encode cyclically or omit if the holdout contains categories unseen in training (fixes audit D-17) |

### Proposed reference split for R3 (V2 canonical, h = 90)
| Segment | Anchors (month starts) | Notes |
| --- | --- | --- |
| Burn-in | before 2010-06-01 | ≥6 months of history |
| Development | 2010-06-01 … 2011-04-01 (11 anchors) | Rolling-origin CV inside; train anchors in each fold purged by 90 days. 2011-04-01 + 90d = 2011-06-30, so its label ends before the holdout |
| Purge gap | 2011-05-01, 2011-06-01 excluded from training for the holdout model | Their labels would overlap the holdout period |
| **Protected holdout** | 2011-07-01, 2011-08-01, 2011-09-01 | Evaluated once; includes the Q4 onset (documented as a distribution shift) |
| Scoring anchor | 2011-12-09 (`D_end`, normalised) | Unlabelled; CRM-facing only |

These split dates are a **proposal**. Final values are fixed in the R3 pre-registration.

---

## 5. Holdout protection

1. The holdout definition is committed in the pre-registration before development begins.
2. Code accesses holdout rows only through a single function (`models/evaluation.py::final_holdout()`, proposed). That function writes an access record (timestamp, git SHA, model ID) to the run manifest.
3. More than one holdout access per frozen model ID fails the results-consistency test, unless it is declared as a deviation.
4. Holdout results are never used to change the model. If a change is needed afterwards, the new model is reported as **post-hoc** and the original result is kept.

---

## 6. Baselines (mandatory)

| Study | Required baselines |
| --- | --- |
| R1 | Prior-year same calendar window; V1 legacy figures (reconciled) |
| R2 | RFM quintiles; legacy lifecycle rules |
| R3 | Recency rank; RFM score; logistic regression on recency + frequency; B0 legacy model |
| R4 customer-level | Zero; last-period repeat; historical mean rate |
| R4 aggregate | Naive; seasonal-naive (lag 52 weeks); moving average |
| R5 | Analytic power vs simulated power; nominal α vs A/A false-positive rate |
| R6 | pandas ×1 runtime; pandas outputs as the parity oracle |

**A model that does not beat its strongest simple baseline by the pre-registered margin, with a CI on the paired difference excluding zero, is reported as "not better than baseline".** It is not reframed as "directionally useful".

---

## 7. Metrics

| Task | Primary | Secondary |
| --- | --- | --- |
| Binary ranking (lapse, propensity) | PR-AUC (prevalence stated) and top-decile precision/lift | ROC-AUC, Brier, calibration slope/intercept, reliability curve |
| Regression (future revenue) | MAE on revenue; Spearman rank | RMSE on log1p; top-decile revenue capture; total calibration (Σpred / Σactual) |
| Forecasting | MASE vs seasonal-naive | MAE, sMAPE (not MAPE near zero), 80/95% interval coverage |
| Clustering | Pre-declared usefulness test (R2) | Silhouette, Davies–Bouldin, BIC, bootstrap ARI |
| Experiments | Effect estimate with CI; A/A false-positive rate; synthetic CI coverage, bias and power | Guardrails |
| Engineering | Parity pass/fail; median runtime (IQR); peak memory | Plan statistics |

---

## 8. Uncertainty, significance and practical significance

- **CIs are required** for every headline metric. Use the percentile or BCa bootstrap with ≥1,000 resamples, clustered by customer where rows repeat. Use the Wilson/Newcombe interval for proportions.
- **Paired comparisons:** model vs baseline uses a bootstrap on the paired metric difference over the same holdout rows.
- **Significance:** α = 0.05 two-sided unless pre-registered otherwise. p-values are reported alongside effect sizes, never alone.
- **Practical significance:** each study pre-declares a minimum meaningful difference. Examples: +0.02 PR-AUC; +5% relative top-decile precision; −5% MASE. A difference can be statistically significant but practically irrelevant, and the report must say so.
- **Multiple testing:** use Holm for a small family of confirmatory tests and Benjamini–Hochberg for exploratory screens. The family is defined in the pre-registration.

---

## 9. Calibration and explainability

- Calibrate on validation folds only, using isotonic or Platt scaling. Report reliability curves before and after.
- Explainability: permutation importance on holdout (with the same customer clustering) is the default. SHAP is optional, subject to the dependency decision. Importance is described as **model reliance**, not causal influence.
- Error analysis is mandatory. Slice performance by tenure band, value band, country group, recency band and anchor month, with CIs.

---

## 10. Experimentation-specific standards (R5)

- **Pre-registration fields:** unit, eligibility, allocation, salt, primary metric, guardrails, windows, MDE, α, power, analysis method, stopping rule, multiplicity plan.
- **Eligibility** requires `fully_observed = true` for every analysed window.
- **One assignment function.** The allocation check (binomial test on arm sizes) must pass before any readout.
- **A/A:** ≥1,000 re-salted splits. The false-positive rate at α must lie within its binomial 95% interval.
- **Synthetic effects:** inject known δ (absolute pp on conversion; multiplicative on revenue) into the treatment arm. Report bias, CI coverage and empirical power vs analytic power.
- **Economics:** incremental revenue = Δ revenue per eligible × treated count. Margin and cost are **Assumed** parameters, shown with sensitivity ranges. No "scale" decision is emitted for non-causal evidence classes.

---

## 11. Reproducibility and provenance

- Every run writes `artifacts/runs/<run_id>/manifest.json` (proposed) containing:
  - git SHA and dirty flag;
  - Python and package versions (`pip freeze` hash);
  - dataset ID and source SHA-256;
  - contract version, parameters and random seeds;
  - command and start/end time;
  - output file hashes.
- Seeds are fixed and recorded, and stochastic results report variation across ≥3 seeds where relevant.
- Reports and the README pull numbers only from the results registry. A CI check fails if a documented number differs from the registry by more than its display rounding.
- Dependencies are pinned for CI (decision P-12).

---

## 12. Negative findings and limitations

Each report contains:
- **"What did not work"**: models that failed to beat baselines, unstable clusters, unrecoverable synthetic effects.
- **"What this data cannot tell us"**: written from the data-reality list in the research programme.
- **"What would change with real data"**: for example, exposure logs, margin, acquisition channel.

---

## 13. Business recommendations

A recommendation must:
1. state the decision it informs;
2. cite the supporting evidence classes and their uncertainty;
3. state the assumptions;
4. state what evidence (usually a real experiment) is required before acting at scale.

Recommendations based only on Simulated or Assumed evidence are labelled **"hypothesis for testing"**, not **"recommendation"**.

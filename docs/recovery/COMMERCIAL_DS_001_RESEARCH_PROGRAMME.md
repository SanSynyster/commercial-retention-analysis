# COMMERCIAL-DS-001 — Research Programme

Part of the [recovery index](README.md). Definitions referenced here are fixed in the [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md). Evaluation rules are fixed in the [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md). Sequencing is in the [roadmap](COMMERCIAL_DS_001_ROADMAP.md).

**No result in this document is a finding.** Numbers marked [VERIFIED] are descriptive facts about the data that were used to assess feasibility. Everything else is design.

---

## 0. Data reality check (shared by all workstreams)

| Fact | Value | Source |
| --- | --- | --- |
| V1 coverage | 2010-12-01 → 2011-12-09 (13 calendar months, the last one partial) | [VERIFIED] `data/processed/v1_online_retail/clean_transactions.parquet` |
| V2 coverage | 2009-12-01 → 2011-12-09 (25 calendar months, the last one partial) | [VERIFIED] V2 parquet |
| V2 overlap defect | 1–9 Dec 2010 appears twice in V2. In that window V1 has 22,523 rows and GBP 311,878 valid revenue; V2 has 45,046 rows and GBP 623,756 | [VERIFIED] |
| Customers / orders | V1 4,338 / 18,532. V2 5,878 / 36,969 (V2 order count unaffected by line duplication; revenue is affected) | [VERIFIED] |
| One-order customers | V1 34.4%, V2 27.6% | [VERIFIED] |
| Inter-purchase interval (days) | V1 median 21, p75 51, p90 ≈103. V2 median 24, p75 61, p90 134, p95 206 | [VERIFIED] |
| Left-censoring of V1 | 62.8% of V1 customers bought before 2010-12-01 (per V2) | [VERIFIED] |
| Seasonality | Revenue peaks in Sep–Nov in both years (V2 monthly valid revenue: Nov-2010 GBP 1.17M, Nov-2011 GBP 1.16M) | [VERIFIED] |
| Geography | 43 countries in V2; UK ≈ 83% of valid revenue | [VERIFIED] |
| Refund lines | V2 22,951 (18,744 with CustomerID) | [VERIFIED] |
| Missing fields | No marketing exposure, cost/margin, channel, demographics, product hierarchy, or stated customer type (B2B/B2C) | [VERIFIED] by schema |
| Customer type | Many customers are likely trade buyers (wholesaler) | [ASSUMPTION] from public dataset description |

**Consequences that apply everywhere**

1. V1 cannot identify acquisitions. Any "new customer", cohort-acquisition or first-to-second-purchase study must use V2 with a look-back burn-in (contract `C-ACQ`).
2. With 25 months there are at most about two seasonal cycles. Any seasonal claim rests on n≈2 per calendar month.
3. Labels that look forward *h* days are mature only for anchor dates ≤ 2011-12-09 − *h*.
4. Every monetary figure is revenue. Margin-based economics are **assumption-driven scenarios**.

---

## Feasibility classification key

| Class | Meaning |
| --- | --- |
| **READY FOR DESIGN** | Data supports it; the method can be specified now |
| **FEASIBLE WITH CONDITIONS** | Supported only if the named conditions hold (dedupe, burn-in, purging, etc.) |
| **REQUIRES EXPLORATORY EVIDENCE** | Worth doing only if a pre-declared exploratory check passes |
| **NOT SUPPORTED BY CURRENT DATA** | Cannot be answered credibly; may be simulated or deferred |

---

## R1 — Commercial Performance and Revenue Analytics

### Research questions
- R1-Q1. How much of gross revenue is attributable, returned, cancelled or non-product, and is the revenue bridge internally consistent?
- R1-Q2. What are the monthly/weekly revenue, order and active-customer trends? How large is Q4 seasonality relative to the rest of the year?
- R1-Q3. How concentrated is revenue across customers (deciles, Lorenz/Gini), and is concentration stable between the two trading years?
- R1-Q4. What are the return/cancellation rates by customer, country and month? Are returns concentrated?
- R1-Q5. What are the distributions of purchase frequency and inter-purchase intervals? How are they affected by right-censoring?
- R1-Q6. What does cohort retention look like for **acquisition-eligible** cohorts (contract `C-ACQ`)?
- R1-Q7. How do V1-based legacy results differ from the canonical V2 results, and why?

### Feasibility
| Item | Assessment |
| --- | --- |
| Supports | Revenue bridge, trends, concentration, returns, frequency, interval distributions, retention for V2 cohorts first observed after burn-in |
| Does not support | Causes of trends; acquisition channel effects; margin; true B2C/B2B split |
| Population | All lines (bridge); identified customers (customer metrics); acquisition-eligible customers (cohorts) |
| Unit of analysis | Line, order, customer, customer-month, calendar week/month |
| Features | n/a (descriptive), plus country group, tenure, order counts |
| Outcomes | Revenue, orders, active customers, retention indicator, return rate |
| Windows | Calendar periods. Cohort observation capped by dataset end, so the retention matrix is triangular |
| Leakage | Not applicable to descriptive work. Avoid future-informed segment labels in trend splits |
| Censoring / bias | Left-censoring (use `C-ACQ`); right-censoring of recent cohorts; partial Dec-2011; V2 overlap duplication |
| Methods | Descriptive statistics; bootstrap CIs for shares/medians; Gini with bootstrap CI; Kaplan–Meier for time-to-second-purchase (handles right-censoring); year-over-year comparisons at matching calendar windows with CIs; permutation or Mann–Whitney tests for distribution differences (labelled associational) |
| Baselines | n/a. Comparisons are against the prior year or the V1 legacy result |
| Evaluation | Reconciliation identities pass; numbers regenerate; CIs reported |
| Risks | Over-interpreting n≈2 seasonal cycles; non-product codes distorting customer revenue |
| Minimum evidence to implement | Phase 2 contracts approved (dedupe, `C-ACQ`, non-product policy) |

**Classification:** R1-Q1–Q5, Q7 **READY FOR DESIGN**. R1-Q6 **FEASIBLE WITH CONDITIONS** (V2 + burn-in).

### Deliverables
`research/r1_commercial/` report with a revenue bridge, trend and seasonality panel, concentration with CIs, returns analysis, a Kaplan–Meier second-purchase curve, a V1-vs-canonical reconciliation table, and a "what this does not show" section.

---

## R2 — Customer Segmentation and Behavioural Discovery

### Research questions
- R2-Q1. What do customer behavioural distributions look like (skew, heavy tails, zero inflation)?
- R2-Q2. Does a rule-based RFM segmentation provide stable, interpretable and *useful* segments?
- R2-Q3. Do K-Means or Gaussian Mixture Models on transformed features find structure that is **more useful than RFM** under a pre-declared test?
- R2-Q4. Are discovered segments stable across bootstrap resamples and across time?

### Feasibility
| Item | Assessment |
| --- | --- |
| Supports | RFM; clustering on behavioural features; PCA for visualisation; stability analysis |
| Does not support | Demographic or attitudinal segments; product-taxonomy segments beyond keyword heuristics |
| Population | Identified customers with ≥1 valid order before the segmentation anchor date *T* |
| Unit | Customer at anchor date *T* (point-in-time snapshot) |
| Features | log-recency, log-frequency, log-monetary, observed tenure (with censoring flag), median inter-purchase interval, AOV, basket lines, product diversity, return rate, Q4 revenue share, country group |
| Outcomes (for usefulness only) | Future 90/180-day revenue and lapse after *T* (label-matured) |
| Windows | Features ≤ *T*. Usefulness outcomes in (*T*, *T*+h], with *T*+h ≤ 2011-12-09 |
| Leakage | Segments must be fitted on data ≤ *T*. The current notebook segments use full-period data and are not point-in-time |
| Censoring / bias | Tenure truncated at data start; one-order customers dominate the low-frequency mass |
| Methods | Log/Yeo-Johnson transforms plus robust scaling; K-Means (k=2…10); GMM (full/diagonal covariance, BIC); optional HDBSCAN/agglomerative only if K-Means/GMM diagnostics are poor; PCA for 2-D views only |
| Diagnostics | Silhouette, Davies–Bouldin, Calinski–Harabasz, GMM BIC, bootstrap ARI stability, temporal stability (refit at *T*−3 months) |
| Baselines | (a) RFM quintile-score segments; (b) the existing rule-based lifecycle segmentation (historical) |
| **Usefulness test (pre-declared)** | With an equal number of segments, compare RFM vs clustering on the share of variance in future-180d log revenue explained by segment membership, and on the log-loss of future lapse given segment only. Clustering is preferred only if it improves both by a pre-registered margin with a bootstrap CI excluding 0, **and** passes stability (median ARI ≥ 0.75, [PROPOSED] threshold) and an interpretability review (every segment describable in one sentence of business language) |
| Risks | Clusters that mirror monetary scale only; unstable k; "personas" invented from noise |
| Minimum evidence | An R1 distribution analysis exists; a point-in-time customer snapshot is implemented (Phase 3) |

**Classification:** RFM and distributions **READY FOR DESIGN**. Clustering superiority **REQUIRES EXPLORATORY EVIDENCE**. Product-affinity segments **NOT SUPPORTED** beyond keyword heuristics.

### Deliverables
A segmentation study report; the canonical segment contract `C-SEG`, a single scheme whichever method wins; a stability appendix; and explicit reporting if clustering does not beat RFM.

---

## R3 — Customer Retention and Lapse Prediction

### Research questions
- R3-Q1. What lapse definition is meaningful given the inter-purchase distribution? The 90-day window sits near V2's p75–p90.
- R3-Q2. Does an ML model rank customers' 90-day lapse risk better than a recency-only baseline and an RFM-score baseline, on a protected, purged temporal holdout?
- R3-Q3. Are predicted probabilities calibrated?
- R3-Q4. Is performance stable across backtest origins?
- R3-Q5. Under stated cost/benefit assumptions, does model-based targeting beat baseline targeting? (Simulated economics only.)

### Feasibility
| Item | Assessment |
| --- | --- |
| Supports | Monthly point-in-time snapshots from V2. With ≥6 months of history and label maturity, anchors run 2010-06-01 … 2011-09-01 = **16 monthly anchors** [VERIFIED arithmetic from date range] |
| Does not support | The causal effect of interventions on lapse; "uplift" targeting |
| Population | Customers with ≥1 valid order before anchor *T* and recency ≤ a max look-back (e.g., 365 days; [PROPOSED], so long-dead customers do not inflate easy negatives) |
| Unit | Customer × anchor month |
| Features | As in `src/churn_prediction.py`, plus a return rate, interval-trend features and a censoring flag for history truncated at data start. Remove `snapshot_month` or encode it cyclically (current defect: unseen categories) |
| Outcome | `lapsed_h` = no valid order in [*T*, *T*+h). Primary h=90. Sensitivity h=60, 120 |
| Windows | Features < *T*. Label [*T*, *T*+h). Label mature iff *T*+h ≤ 2011-12-09 |
| Leakage | Train labels must end before the first test anchor (**purge gap = h**). No full-period statistics in features (e.g., the high-value threshold must be computed at *T*) |
| Censoring / bias | Left-truncated tenure; customers entering late have short histories; repeated anchors per customer (cluster bootstrap by customer for CIs) |
| Methods | Logistic regression (regularised), random forest, HistGradientBoosting; hyperparameters via rolling-origin CV inside the development period; calibration (reliability curves, Brier, isotonic/Platt fitted on validation only); permutation importance plus SHAP if available (dependency decision) |
| Baselines | B0 = existing lapse model as historical reference (`src/churn_prediction.py` at `1b293c2`); B1 = recency rank; B2 = RFM score; B3 = logistic regression on recency + frequency |
| Evaluation | Holdout anchors 2011-07-01 … 2011-09-01, evaluated **once**. ROC-AUC, PR-AUC, top-decile precision and lift, Brier, calibration slope; customer-clustered bootstrap CIs; paired difference vs B1 with CI |
| Risks | Small number of independent periods; the seasonal (Q4) holdout differs from training; high-value customers are few |
| Minimum evidence | Phase 2 contracts (`C-SNAP`, `C-LAPSE`); a baseline B1 computed before any model tuning |

**Scoring rule (fixes audit D-4):** CRM-facing scores are produced at the **current** anchor (dataset end), which has no label. Evaluation uses only matured anchors. These two outputs are separate datasets.

**Classification:** **FEASIBLE WITH CONDITIONS** (purging, protected holdout, baselines). Targeting economics: **FEASIBLE WITH CONDITIONS** as a simulation.

### Deliverables
A lapse-definition analysis, a model comparison vs baselines with CIs, calibration plots, a backtest table, error analysis by segment and tenure, a simulated targeting-economics scenario (clearly labelled), and a model card.

---

## R4 — Customer Lifetime Value and Revenue Forecasting

### Concepts kept separate
| Concept | Definition | Feasible? |
| --- | --- | --- |
| Historical customer value | Observed valid revenue to date (left-truncated) | **READY FOR DESIGN** (descriptive) |
| Fixed-horizon future revenue | Revenue in (*T*, *T*+h] for each customer, h = 90/180 days | **FEASIBLE WITH CONDITIONS** |
| Expected customer lifetime value | Model-based expected future value over a horizon | **FEASIBLE WITH CONDITIONS** only as *capped-horizon* (≤ 12 months) expected **revenue**; unbounded lifetime CLV and margin-based CLV **NOT SUPPORTED** |
| Aggregate revenue forecast | Company-level weekly/monthly revenue | **FEASIBLE WITH CONDITIONS** (about 2 seasonal cycles) |

### Research questions
- R4-Q1. Can customer-level 180-day revenue be predicted better than naive baselines?
- R4-Q2. Do probabilistic repeat-purchase models (BG/NBD + Gamma-Gamma) give calibrated expected transactions/value compared with ML regression?
- R4-Q3. Can weekly aggregate revenue for the final quarter be forecast better than seasonal-naive, with honest intervals?

### Feasibility
| Item | Customer-level (Q1–Q2) | Aggregate (Q3) |
| --- | --- | --- |
| Population | Customers active ≤ 365 days before *T* | All valid revenue (and optionally all positive revenue) |
| Unit | Customer at anchor *T* | Calendar week (ISO) |
| Features | RFM, tenure, intervals, AOV, returns, country group | Lags, seasonal lag 52, holiday/Q4 indicators |
| Outcome | Revenue in (*T*, *T*+180d]. Zero-inflated, heavy-tailed | Weekly revenue |
| Windows | Latest mature anchor for h=180: 2011-06-12 (use 2011-06-01) | 105 weeks. Holdout: final 13 full weeks before the partial last week |
| Leakage | Features < *T*; no full-period normalisation | No future exogenous information; partial final week excluded or flagged |
| Censoring | Left-truncated history; BG/NBD calibration period must start at a common origin | Only about 2 Q4 peaks; 2010-12 overlap duplication must be removed |
| Methods | Two-part (hurdle) model: P(buy) × E(revenue \| buy); gradient-boosted regression on log1p revenue; BG/NBD + Gamma-Gamma (dependency decision: `lifetimes` is unmaintained, so PyMC-Marketing or a scipy implementation would be needed) | Naive, seasonal-naive (lag 52), moving average, ETS (statsmodels — dependency decision), optional SARIMA |
| Baselines | Zero prediction; last-period revenue repeated; customer historical mean per 180 days | Seasonal-naive; naive |
| Evaluation | MAE, RMSE on log1p, top-decile revenue capture, calibration of totals (sum predicted vs sum actual), Spearman rank correlation; customer bootstrap CIs | MAE, MAPE/sMAPE (with caveats), MASE vs seasonal-naive, interval coverage; rolling-origin backtest |
| Risks | Heavy tails dominated by a few wholesale customers; only one usable 180-day anchor window if a holdout is reserved | Seasonal-naive is hard to beat with 2 cycles; models may over-fit Q4 |
| Minimum evidence | `C-SNAP` implemented; R1 seasonality analysis | R1 weekly series after dedupe |

### Deliverables
A value-concept glossary, a customer-level forecast comparison vs baselines, BG/NBD diagnostics (if adopted), an aggregate forecast backtest with intervals, and an explicit statement of what CLV is *not* estimated.

---

## R5 — Experimentation and Marketing Effectiveness

### Non-negotiable framing
The UCI data contains **no marketing exposure or randomised treatment**. Accordingly:
- No historical split is an A/B test.
- No observed difference is a treatment effect.
- No campaign recommendation is derived from invented uplift.
- Every output carries an evidence class: **Observational**, **A/A**, **Synthetic**, or **Causal (real experiment)**. Only the last supports effect claims, and it is currently empty.

### Research questions
- R5-Q1. For a specified hypothetical campaign (e.g., a day-21 second-purchase nudge), what are the unit, eligibility, assignment, primary and guardrail metrics, and analysis plan?
- R5-Q2. Given observed baseline rates and variances (from eligible, fully observed customers), what sample size and duration are needed for a given MDE, and is that achievable with this customer base?
- R5-Q3. Does the assignment and readout pipeline produce no detectable effect and nominal false-positive rates in repeated A/A simulations?
- R5-Q4. When a known synthetic effect is injected, does the readout recover it with correct CI coverage and power?
- R5-Q5. How should multiple metrics and windows be corrected for multiple testing?
- R5-Q6. How would incremental revenue and profit be computed from a *real* readout, given margin and cost assumptions?

### Feasibility
| Item | Assessment |
| --- | --- |
| Supports | Design, power/MDE from observed baselines, A/A false-positive studies, synthetic effect recovery, readout-pipeline validation, economics *templates* |
| Does not support | Any real treatment effect; uplift modelling; campaign ROI |
| Population | Hypothetical eligible customers, e.g., first purchase observed after the `C-ACQ` burn-in, no second purchase by day 21, and **full observation window available** (fixes audit D-8) |
| Unit | Customer (randomisation and analysis) |
| Assignment | One deterministic salted hash rule in one place (fixes audit D-9), with a documented salt and allocation |
| Primary metric | Second-purchase conversion within *w* days of eligibility |
| Guardrails | Revenue per eligible customer; return rate; (real data only) unsubscribe/complaint rates |
| Methods | Two-proportion z-test or Newcombe CI; Welch / bootstrap for revenue; CUPED-style variance reduction using pre-period behaviour (simulation-validated); Holm or Benjamini–Hochberg for multiplicity; sequential-testing caveats documented |
| Baselines | Not applicable. Validation is against known truth in simulation |
| Evaluation | A/A: false-positive rate ≈ α over ≥1,000 simulated splits. Synthetic: bias ≈ 0, CI coverage ≈ nominal, empirical power vs analytic power |
| Risks | Readers mistaking simulation output for evidence; under-powered design (indicative: the existing power mart reports 3,677 needed per arm vs 720 control customers, a figure computed with the censoring defect, so it must be recomputed) |
| Minimum evidence | `C-ACQ`, `C-EXP` contracts; censoring filter implemented |

**Classification:** Q1, Q2, Q5, Q6 **READY FOR DESIGN**. Q3, Q4 **READY FOR DESIGN** ([SIMULATED]). Real effect estimation **NOT SUPPORTED BY CURRENT DATA**.

### Deliverables
A pre-registration template, a power/MDE study, an A/A simulation report, a synthetic-recovery report, a readout module that accepts a real exposure table (schema in `C-EXP`), and an economics template with explicit assumptions. Existing dbt experiment marts are reclassified, not deleted (see [decision log](COMMERCIAL_DS_001_DECISION_LOG.md) P-04).

---

## R6 — Scalable Analytics and Data Engineering

### Research questions
- R6-Q1. Do the pandas, dbt/DuckDB and PySpark implementations of the canonical datasets agree with the contract (exact for counts and keys, ≤ 1e-6 relative for sums)?
- R6-Q2. How do runtime and memory scale for pandas vs DuckDB vs local Spark across data sizes, and where do the crossovers occur?
- R6-Q3. What do execution plans show about shuffles, partitioning and skew, and which choices change performance?
- R6-Q4. What is required to make the Databricks bundle genuinely deployable, and can it be verified?
- R6-Q5. Is every published artifact traceable to code version, data hash, parameters and command?

### Feasibility
| Item | Assessment |
| --- | --- |
| Supports | Parity testing; local benchmarks; plan inspection; provenance |
| Does not support | The claim that Spark is *needed* at 1M rows; real cluster performance (no cluster); Databricks verification (no workspace/CLI) |
| Unit | Pipeline run × engine × data scale |
| Data | Canonical V2, plus **synthetic scale-ups** (×10, ×50; customer and invoice IDs offset per replica, dates preserved) labelled [SIMULATED] |
| Methods | ≥5 timed repetitions after one warm-up; median and IQR; cold vs warm cache noted; peak RSS; Spark `explain("formatted")`; partition counts; skew metrics; fixed hardware spec recorded |
| Baselines | pandas at ×1 |
| Evaluation | Parity tests pass; benchmark reproducibility (coefficient of variation reported); provenance manifest present for 100% of published artifacts |
| Blockers | **No Java runtime locally** [VERIFIED]: Spark cannot run until the owner installs a JDK 17 (out of scope for this phase). Databricks CLI absent |
| Risks | Benchmarks dominated by I/O or JVM start-up; misleading "Spark is slow" or "Spark scales" conclusions; CI runtime |

**Classification:** parity (pandas↔dbt) **READY FOR DESIGN**. Spark parity and benchmarks **FEASIBLE WITH CONDITIONS** (JDK available). Databricks **NOT SUPPORTED** until a workspace exists (remains optional, labelled unverified). Provenance **READY FOR DESIGN**.

### Deliverables
A contract parity test suite, a benchmark report with methodology and limitations, a plan-analysis appendix, a Databricks readiness checklist (unverified items flagged), and a run-manifest specification.

---

## Cross-workstream dependencies

| Consumer | Requires |
| --- | --- |
| R1 | Foundation (dedupe, `C-ACQ`, non-product policy) |
| R2 | R1 distributions; `C-SNAP` |
| R3 | `C-SNAP`, `C-LAPSE`; R1 interval analysis informs h |
| R4 | `C-SNAP`; R1 weekly series |
| R5 | `C-ACQ`, `C-EXP`; R1 second-purchase KM curve for baselines |
| R6 | Foundation and contracts (parity targets); can run alongside R1–R5 once foundation is stable |
| CRM priority (successor to notebook 07) | `C-SEG` (R2) + R3 current-anchor scores + R4 value; only after R2–R4 gates pass |

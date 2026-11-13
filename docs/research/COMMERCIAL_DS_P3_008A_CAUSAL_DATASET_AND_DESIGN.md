# P3-008A — Randomised Marketing Dataset and Causal Research Design

## Scope and decision

This milestone verifies a three-arm randomised email experiment and freezes an audit/split protocol for P3-008B. It performs no uplift-model fitting and reports no test-set treatment effects. The row-level split and audit JSON remain outside Git.

## Dataset provenance, permission and design facts

The primary file is the original CSV linked from [Kevin Hillstrom's MineThatData challenge page](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html): [original CSV](http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv). It was retrieved on 13 November 2026 to `../source_data/hillstrom/` and is not tracked by Git. SHA-256: `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece` (3,964,977 bytes). As a provenance cross-check, the scikit-uplift mirror's decompressed dataframe was exactly equal to the original CSV; its compressed-file MD5 matched the checksum embedded in [scikit-uplift's loader](https://www.uplift-modeling.com/en/latest/_modules/sklift/datasets/datasets.html).

The original page documents 64,000 customers, random assignment in approximately equal thirds, pre-campaign customer history and results tracked for two weeks after email. [TensorFlow Datasets](https://www.tensorflow.org/datasets/catalog/hillstrom) and [scikit-uplift's dataset documentation](https://www.uplift-modeling.com/en/latest/api/datasets/fetch_hillstrom.html) independently describe the same two-week window and outcomes. A secondary [Hillstrom data dictionary](https://book.tdda.info/datadictionaries/hillstrom-dd.html) describes a six-week outcome period; this conflicts with the primary source and both dataset-loader references. P3-008 uses two weeks, the consistently documented original definition. No evidence was found that the challenge page provides an explicit dataset license or redistribution grant; [CausalML's dataset notes](https://causalml.readthedocs.io/en/latest/datasets.html) likewise list Hillstrom as having no license file. A research-data loader's software license does not license its downloaded data. We retain the raw file privately, attribute MineThatData, and do not redistribute it pending explicit permission.

The randomized unit is one customer row in the released file. There is no customer identifier or index. Thus we cannot verify identity uniqueness beyond the dataset's documented unit, and do not fabricate identifiers or deduplicate identical rows. There are 6,562 rows that exactly repeat an earlier full row (`DataFrame.duplicated()` count), 56,209 distinct pre-treatment feature rows, and 935 groups of identical rows that span multiple splits. These facts do not establish duplicate customers or identify cross-split customer overlap. Row-level splitting keeps each source row in exactly one split.

## Schema and audit

The original CSV has 64,000 rows and 12 columns, with no missing cells:

| Column | Type | Role / meaning |
|---|---|---|
| `recency` | integer | Months since last purchase, pre-treatment |
| `history_segment` | categorical | Historical-spend band, pre-treatment |
| `history` | float | Prior-year historical spend, USD, pre-treatment |
| `mens`, `womens` | binary integer | Prior-year department purchase indicators, pre-treatment |
| `zip_code` | categorical | Urban, Rural, or source spelling `Surburban`, pre-treatment |
| `newbie` | binary integer | New customer indicator, pre-treatment |
| `channel` | categorical | Phone, Web, or Multichannel, pre-treatment |
| `segment` | categorical | Randomized assignment arm |
| `visit` | binary | Visited website during outcome window |
| `conversion` | binary | Purchased during outcome window |
| `spend` | float | Observed spend during outcome window, USD |

The first eight columns are historical attributes and precede assignment. The final three are post-assignment outcomes and must never be model covariates. `segment` is assignment, not observed email opening, clicking, or reading. The original challenge defines `visit` as a website visit; the secondary [TDDA dictionary](https://book.tdda.info/datadictionaries/hillstrom-dd.html) describes it as “visited or called.” The original website-visit definition governs this study.

| Audit item | Result |
|---|---:|
| Men's email | 21,307 (33.292%) |
| Women's email | 21,387 (33.417%) |
| No email | 21,306 (33.291%) |
| Equal-allocation chi-square | 0.203; p = 0.904 |
| Missing cells | 0 |
| Exact duplicate row occurrences | 6,562; not interpreted as duplicate people |
| Spend without conversion / conversion without visit | 0 / 0 |
| Visit without conversion | 8,816 |
| Spend range | $0–$499 |

Pooled full-file outcomes (reported without arm contrasts) are 9,394 visits (14.678%), 578 conversions (0.903%), and 578 positive-spend rows (0.903%). Thus conversion and spend are sparse, spend is 99.097% zero and right-tailed, and spend-positive status agrees exactly with conversion. The arm allocation is close to equal. Across pairwise treatment arms, the largest absolute SMD over numeric pre-treatment variables and categorical level indicators is 0.0169; the other two maxima are 0.0164 and 0.0143. This is consistent with good observed covariate balance. Neither these balance diagnostics nor the allocation-count test prove randomisation; random assignment is documented by the original challenge source.

## Treatment and estimands

The three original arms remain distinct. Let `a` denote assignment to Men's email, `b` Women's email, and `0` no email. The primary outcome is `visit`: the original challenge and both loader references define it as website visitation in the two weeks after assignment. This is an intention-to-treat (ITT) endpoint for assignment to an email, not for opening or reading it.

For each outcome `Y`, the average treatment effect for a contrast is the difference in mean potential outcomes:

- Primary: `ATE_M0 = E[Y(M) − Y(0)]`, for visit.
- Secondary: `ATE_W0 = E[Y(W) − Y(0)]`.
- Secondary: `ATE_MW = E[Y(M) − Y(W)]`.
- Secondary outcomes for each contrast: conversion (risk difference) and spend (USD per assigned customer).

For pre-treatment characteristics `X`, the conditional effect is `CATE_ab(X) = E[Y(a) − Y(b) | X]`. No observed row reveals both potential outcomes; individual effects are latent and can only be evaluated indirectly through policy value and randomized-group evidence.

Causal interpretation requires the documented random assignment to be implemented as stated, consistency of each assigned campaign, positivity, complete outcome observation, and no material interference between customers. The estimand is the effect of assignment/offer. Email delivery, opening, and engagement are unobserved, so this is not a treatment-on-the-treated or effect-of-reading estimate. The dataset describes one historical retailer and cannot establish transportability to the UCI Online Retail II population or current campaigns.

## Frozen stratified split and effective sample sizes

The audit runner `src/hillstrom_causal_audit.py` creates a deterministic row-level 60/20/20 split, stratified by all three original assignment arms, seed `20261114`. A 20% test set is selected first; the remaining 80% is split into 75% training / 25% development. Exact row indices and split membership are saved privately at `../source_data/hillstrom/p3_008a_outputs/hillstrom_row_split_private.csv`; the aggregate audit and file hashes are saved beside it. Frozen split CSV SHA-256: `0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce`. No UCI monthly or time-ordered split is appropriate: this is one cross-sectional experiment. The full-file pooled outcome audit was performed as required, but test-arm outcome contrasts, test model scores, and test policy values were not calculated or used.

| Split | Total n | Men's | Women's | No email |
|---|---:|---:|---:|---:|
| Training | 38,400 | 12,784 | 12,832 | 12,784 |
| Development | 12,800 | 4,261 | 4,278 | 4,261 |
| Test, locked | 12,800 | 4,262 | 4,277 | 4,261 |

Training and development support counts are:

| Pairwise contrast | Train n | Train visits / conversions | Development n | Development visits / conversions |
|---|---:|---:|---:|---:|
| Men's vs no email | 25,568 | 3,648 / 238 | 8,522 | 1,252 / 78 |
| Women's vs no email | 25,616 | 3,269 / 184 | 8,539 | 1,114 / 54 |
| Men's vs women's | 25,616 | 4,221 / 282 | 8,539 | 1,446 / 86 |

The primary visit endpoint has ample event counts for a bounded comparison. Conversion and spend have only 352 events in training and 109 in development across all arms; arm-specific CATE discovery on those outcomes will be low-power and exploratory. The locked test's allocation counts are recorded; no test-arm outcome contrasts, test model scores, or policy effects were examined in this milestone.

## P3-008B: predeclared ATE analysis

1. The **primary confirmatory ATE** is Men's-email assignment versus no-email assignment on two-week website visits, estimated on the locked test split only after all modelling and analysis choices are frozen. Use the randomized difference in means (risk difference) as the primary estimator, with a predeclared two-sided randomization test and a suitable 95% confidence interval (Newcombe/Wilson risk-difference interval; randomization-based interval if implemented by inversion).
2. Report training/development arm-level outcome summaries and development-only difference-in-means estimates as model-development diagnostics, not confirmatory evidence. Covariate-adjusted ATE estimates are secondary robustness analyses. Full-sample ATE estimates may be reported separately as descriptive summaries only, never as independent confirmation.
3. Use confidence intervals appropriate to secondary mean contrasts: randomization-based/permutation inference for binary outcomes; robust HC2 standard errors for covariate-adjusted linear probability/mean models. For spend, also report customer-row bootstrap intervals and randomization inference because the distribution is zero-inflated and skewed.
4. A predeclared adjusted analysis uses only baseline `X`, treatment indicators and treatment-by-centered-covariate interactions (Lin-style adjustment); it is a precision/robustness analysis, not a replacement estimand. Fit preprocessing on training folds only.
5. Women's-vs-no-email visit and Men's-vs-Women's are secondary. Conversion and spend remain secondary because rare/skewed; use Holm adjustment across the secondary contrast/outcome family, and disclose all tested comparisons. Widely available published Hillstrom results mean the locked test split limits direct model-selection reuse but does not provide genuine analyst blinding.

No test-set treatment-effect estimate or test-outcome summary was computed in P3-008A. Training and development arm-level outcome summaries were recorded to assess event support; no test results were consulted.

## P3-008B: bounded CATE/uplift comparison

The primary model task is Men's email versus no email for visit, using the original baseline features only. Fit Women's-vs-no-email and Men's-vs-Women's as separate, secondary pairwise analyses. Do not merge the two email arms into a single treatment. Keep the third arm out of each pairwise learner's training and policy evaluation, while preserving its separate contrast analysis.

Compare a constant ATE/rank-tie baseline, S-learner, T-learner, X-learner, and a cross-fitted doubly robust learner. Use a bounded pair of base learners: regularized logistic regression and HistGradientBoosting. Defer XGBoost and causal-forest packages from the initial P3-008B comparison; add neither solely to increase algorithm count. Do not add `econml` or `causalml` infrastructure solely to expose a named estimator; implement the DR pseudo-outcome with existing numerical tools. No extensive grid search. Use one fixed configuration per base learner (logistic L2, `C=1`; HGB learning rate 0.05, 7 leaves, 100 iterations, minimum leaf size 50, L2=1, early stopping disabled). Do not expand these settings after seeing development results.

Candidate policies are considered in this fixed complexity order: (1) constant-ATE/rank-tie; (2) regularized-logistic T-learner; (3) regularized-logistic S-learner; (4) regularized-logistic X-learner; (5) cross-fitted DR learner with logistic nuisances; (6) HGB T-learner; (7) HGB S-learner; (8) HGB X-learner; (9) cross-fitted DR learner with HGB nuisances. For the primary Men's-versus-control contrast, compare each candidate with the current simpler incumbent using paired customer-row bootstrap differences in development policy value at the fixed 20% treatment budget (1,000 resamples, fixed seed). Promote a more complex candidate only if the 95% paired interval for its improvement excludes zero in the positive direction; otherwise retain the simpler incumbent. This is a practical uncertainty-aware selection rule, not a proof of no heterogeneity: failure to establish superiority does not establish homogeneous treatment effects.

Use known randomized assignment probabilities from the experiment design, with the realised treated-arm proportion within the relevant evaluation split as the documented propensity convention. For the primary pairwise population, retain only Men's-email and no-email rows; within each train, development, or test split, set `e = n_M/(n_M+n_0)`. Do not estimate propensity from outcomes. For DR estimation, cross-fit response nuisance models within training using five stratified folds; each training row's nuisance prediction must come from a fold that excluded that row. For development evaluation, nuisance predictions for development rows come from models fit on training only. For final test evaluation, fit nuisances on train+development only and apply them once to test. Never fit a nuisance model on the same evaluation outcomes being scored. Fit the treatment-effect learner to cross-fitted pseudo-outcomes. Assignment is an allowed treatment input for learners; post-treatment outcomes and derived engagement features are prohibited covariates. All preprocessing is fold-local. Select model and configuration by development-set policy value at a predeclared 20% budget as the primary policy metric; use AUUC and the 10%/30% policy values as supporting diagnostics. Do not inspect test outcomes. Refit the selected approach on train+development after selection and evaluate once on the locked test set.

## P3-008B: ranking and policy evaluation

For the primary evaluation population, rank only the Men's-email and no-email observations jointly by predicted CATE. For secondary contrasts, use the corresponding pair of arms only. Compare policies against (i) random targeting at the same budget, (ii) treat-none, (iii) treat-all, (iv) a constant-effect score, and (v) simple historical-behaviour targeting ranked by greater `history`, then lower `recency` for ties. The historical rule is a benchmark, not an uplift estimate.

At each selected fraction `q`, use the known-propensity, inverse-probability-weighted treatment-control difference among the top `q` ranked observations, multiplied by the number selected to estimate cumulative incremental events. The fraction axis is `q` from 0 to 1; the gain axis is incremental events per 1,000 pairwise-eligible rows. The random-targeting reference at each `q` is `q` times the full-population randomized ATE. Qini/AUUC is the trapezoidal area between the ranked gain curve and that random reference over `q ∈ [0,1]`, reported in incremental events per 1,000 eligible rows; do not divide by the estimated full-sample ATE, which is unstable if the average effect is near zero.

Define a policy `π(X) ∈ {email, no email}` that assigns email to the top `q` CATE-ranked pairwise-eligible rows and no email to the remainder; enforce the same budget in every comparison. Estimate policy value with IPW and a doubly robust estimator, `V_DR(π) = mean[μ̂_{π(X)}(X) + I(A=π(X))/p(A|split) × (Y−μ̂_A(X))]`, and report incremental value versus treat-none. Compare top 10%, 20%, and 30% policies with same-budget random targeting; treat-all is an unconstrained reference. Use paired customer-row bootstrap intervals for policy differences. Apply the one-shot test evaluation only after model selection and all policies are frozen. Report uplift ranking, incremental policy value, and ordinary outcome prediction as distinct results. A response rate among assigned email recipients is not causal uplift. Report each pairwise experiment separately; a three-action policy is out of scope for the first comparison.

Email delivery cost, margin, and attribution economics are unavailable. Do not claim profit, ROI, or revenue net of contact cost. Spend is reported as randomized gross customer spend in USD.

## Limitations and exact handoff

This is one historical experiment, not repeated campaigns or longitudinal intervention data. Conversion/spend are sparse. The dataset has no observed email receipt/open/click, no customer identifier, and no way to validate uniqueness beyond its customer-row documentation. CATE estimates are not directly observable and require held-out policy evaluation. Historical experiment effects may not transport to this project’s retail population, present-day channels, or current campaign execution. No causal transportability claim is made.

P3-008B starts from the exact original file SHA above, fixed seed and private 60/20/20 row split. It first reports the predeclared ATE contrasts, then fits bounded pairwise CATE learners on training, selects by development policy value, and evaluates once on test. The primary result is Men's-email assignment versus no-email on two-week website visit; women’s email and other outcomes are separately labelled secondary. Test outcomes remain unopened until configuration and analysis choices are frozen.

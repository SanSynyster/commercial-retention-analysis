# P3-008D — Causal Research Synthesis

## Purpose and evidence hierarchy

This report closes the Hillstrom causal research workstream by integrating the accepted dataset design (P3-008A), development-only causal ML experiment (P3-008B), and locked test evaluation (P3-008C). It does not add analyses or reopen test outcomes.

Evidence is separated as follows:

- **Confirmatory:** the predeclared randomized Men's-email versus no-email effect on two-week website visits in the locked test split.
- **Secondary randomized evidence:** the other predeclared contrast/outcome ATEs, with Holm correction across the eight secondary tests.
- **Exploratory model evidence:** development-fold learner comparisons, uplift rankings, and development policy-value intervals. These data were used for model selection and are not an independent test of personalized targeting.

The source reports are [P3-008A](COMMERCIAL_DS_P3_008A_CAUSAL_DATASET_AND_DESIGN.md), [P3-008B](COMMERCIAL_DS_P3_008B_CAUSAL_ML_AND_UPLIFT.md), and [P3-008C](COMMERCIAL_DS_P3_008C_LOCKED_TEST_CAUSAL_EVALUATION.md).

## Dataset and randomized design

The experiment is Kevin Hillstrom's MineThatData E-Mail Analytics and Data Mining Challenge (2008): 64,000 customer rows randomly assigned in approximately equal thirds to Men's email, Women's email, or no email. The original definition is website visit, conversion, and spend measured during the **two weeks** after assignment. No email opening, delivery, or engagement variable is observed.

The first eight recorded attributes are pre-treatment features: `recency`, `history_segment`, `history`, `mens`, `womens`, `zip_code`, `newbie`, and `channel`. Assignment is represented by `segment`; `visit`, `conversion`, and `spend` are post-assignment outcomes. The primary estimand is intention-to-treat (ITT): the effect of assignment to an email, not the effect of reading it. Causal interpretation relies on the documented random assignment, consistency, positivity, complete outcome observation, and no material interference between customers.

The frozen row-level split is stratified by the three assignment arms: 38,400 training, 12,800 development, and 12,800 test rows. The primary Men's-email/no-email populations were 25,568 training, 8,522 development, and 8,523 test rows. Source SHA-256 is `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`; frozen split SHA-256 is `0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce`.

The MineThatData experiment is distinct from the project's UCI Online Retail II data. Hillstrom supplies a randomized intervention and post-assignment outcomes; UCI Online Retail II is observational transaction history without randomized email assignments. Hillstrom effects or uplift predictions do **not** directly apply to UCI customers.

## Methods implemented

P3-008B used the Men's-email versus no-email contrast for `visit` and the eight pre-treatment features. Women’s-email rows were excluded from that primary learner comparison and retained for separate randomized contrasts in P3-008C.

The development benchmark included:

- A **constant-ATE** baseline: the training randomized visit-rate difference, producing no individualized effect ranking and a seeded random tie-break for exact-budget evaluation.
- A **historical-behavior targeting** baseline ranked by prior-year history, then recency. It is a benchmark, not a causal effect estimator.
- Logistic-regression and HistGradientBoosting (HGB) **S-learners**, which fit outcome models with assignment as a treatment input and form CATE scores from predicted counterfactual probabilities.
- Logistic-regression and HGB **T-learners**, which fit separate treatment/control outcome models.
- Logistic-regression and HGB **X-learners**, which impute treatment effects from the initial arm outcome models and combine the effect models using the randomized propensity.
- Logistic-regression and HGB **doubly robust (DR) learners**, using five-fold out-of-fold training nuisance predictions to form DR pseudo-outcomes and a final CATE regression.
- One bounded **XGBoost T-learner** as a supplementary benchmark. It was fitted in the initial P3-008B run despite P3-008A deferring XGBoost; the P3-008B correction removed it from formal promotion while retaining its descriptive output. It is not approved for deployment.

Each learner family used a fixed, bounded configuration rather than a broad search: regularized logistic regression with L2 penalty and `C=1`; HGB with learning rate 0.05, 7 leaves, 100 iterations, minimum leaf size 50, L2=1, and early stopping disabled. XGBoost used one already-available CPU histogram configuration and remained supplementary. No causal forest or new causal-ML package was added.

Preprocessing was fit on training data (and within each DR cross-fit fold). The propensity convention was the realized treated share within each pairwise split; it was 0.5 in training/development and approximately 0.50006 in the primary test pair. The nuisance models used for development DR policy evaluation were trained on training observations only. Cross-fitting prevents a training row from receiving an in-sample nuisance prediction when its DR pseudo-outcome is formed.

For ranking diagnostics, P3-008B used known-propensity Horvitz–Thompson Qini gains and AUUC. Policy value was estimated with inverse-propensity weighting and a doubly robust estimator. Policies assigned treatment to exactly the top 10%, 20%, or 30% by score; treat-none was a separate baseline. Paired customer-row bootstraps compared policy values. CATE outputs are predictions of conditional average effects, not observed individual causal effects; Qini/AUUC assesses ranking, and policy value assesses a decision rule. These quantities are not interchangeable.

## RQ1 — Does email assignment increase two-week website visits?

### Confirmatory primary result

On the locked test split, Men's email produced 802 visits among 4,262 assigned customers (18.817%); no email produced 454 among 4,261 (10.655%). The randomized ITT risk difference was **+8.163 percentage points**, with a predeclared Newcombe 95% interval of **[+6.667, +9.658] pp** and exact two-sided conditional randomization p-value **1.53 × 10⁻²⁶**. This is **81.63 additional visits per 1,000 assigned customers**.

This supports a positive average assignment effect for this historical Men's-email campaign on the two-week visit outcome, subject to the experiment's randomization and outcome-observation assumptions. It does not estimate the effect of opening or reading the message.

### Secondary randomized results

After Holm adjustment across the eight secondary contrast/outcome tests, Women's email versus no email had a **+4.847 pp** visit difference (adjusted p **2.73 × 10⁻¹⁰**), and Men's versus Women's email had a **+3.316 pp** visit difference (adjusted p **0.000359**). These are secondary contrasts, not replacements for the primary question.

Conversion and spend contrasts were inconclusive after multiplicity adjustment. Conversion was rare (0.903% pooled in the original data), and spend was 99.097% zero in the original audit and right-tailed. For example, the primary Men's/no-email conversion difference was +0.352 pp (Holm p 0.5288), and gross spend difference was +$0.447 per assigned customer (95% bootstrap interval [−$0.134, +$1.070], Holm p 0.5288). These results do not prove zero effect. Spend is gross observed USD, not incremental revenue net of contact cost; no margin, email cost, or profit uplift was established.

## RQ2 — Did causal ML improve targeting over random allocation?

### Development-only policy comparisons

The frozen 20% comparison used expected random targeting: 20% times the full-population DR ATE, with that reference recomputed within each paired bootstrap sample. Candidate-minus-expected-random development policy-value differences were:

| Development policy | Δ visits per 1,000 | Paired 95% interval |
|---|---:|---:|
| HGB DR | +4.93 | [−2.34, +11.27] |
| Logistic X-learner | +2.05 | [−4.61, +8.74] |
| Logistic T-learner | +0.94 | [−5.37, +7.85] |
| Historical behavior | +2.49 | [−3.45, +9.00] |

Selected rows shown; the full table is in P3-008B, and all learner intervals include zero.

These are development-sample policy-value estimates. The development folds informed model comparison and selection; the intervals are conditional on fitted scores and nuisance predictions, and comparisons were not multiplicity-adjusted. No learner passed the frozen rule requiring a paired 95% interval lower bound above zero. **Constant ATE remained selected.** This non-promotion result does not show that treatment effects are homogeneous; it shows that the development experiment did not establish a more reliable personalized policy under the prespecified rule.

The first reported constant-ATE comparison used one seeded random tie-break draw, which yielded 11.81 incremental visits per 1,000 at 20%, below the expected random value of 15.42 in development. The correction retained that draw for protocol transparency and added the more representative expected-random reference. Both comparison conventions retained constant ATE, and all advanced learner intervals versus expected random included zero.

Development CATE rankings were not fully consistent across methods, and estimated negative-CATE shares were small (0–0.55%). Those diagnostics do not identify individual treatment effects. The supplementary XGBoost model was not eligible for promotion.

### Locked test policy value

The selected constant-ATE policy corresponds to random treatment allocation within the 20% budget. Its expected test incremental value versus treat-none is **+16.33 visits per 1,000 eligible customers**, with a scaled 95% interval of **[+13.33, +19.32]**. This is the expected value of random targeting derived from the test ATE; it is not evidence that personalization works. No candidate uplift model was evaluated on test outcomes, and there is no confirmatory personalized-targeting benefit in this workstream.

## RQ3 — Do the results establish conversion or revenue improvement?

No. The primary causal evidence concerns visits. Secondary conversion contrasts were uncertain and did not survive Holm adjustment; spend contrasts were also uncertain. Because spend is zero-heavy, the mean is affected by a small number of purchasing customers. The experiment supplies no defensible contact-cost, margin, or net-revenue calculation. It therefore does not establish conversion lift or revenue/profit uplift.

## Limitations, deviations, and provenance

- This is one historical retailer campaign, not repeated intervention data. No opens, delivery, or engagement were observed.
- Conversion and spend are sparse; spend is highly zero-inflated and skewed. Secondary results are inconclusive, not proof of no effect.
- Development bootstrap intervals are conditional on fitted models, do not include model-selection uncertainty, and were not multiplicity-adjusted across the learner comparisons.
- No test candidate-model diagnostics were performed. The locked test results are consumed and cannot serve as an untouched confirmation sample for later choices.
- The predeclared secondary Lin-style covariate-adjusted analysis with HC2 robust standard errors was omitted in P3-008C. It was not preplanned as an omission; no adjusted estimate or p-value is available. The primary unadjusted randomized difference-in-means result is unchanged.
- P3-008C's execution provenance records that a metadata-only preflight join failed because of incompatible pandas join axes; that command explicitly requested only the `segment` column. After test outcomes were opened, the runner was changed to add realized treatment shares derived from arm counts, and the aggregate JSON was later supplemented with those count-derived fields. These changes did not alter outcomes, estimators, intervals, hypotheses, or multiplicity. The aggregate was not produced by the same uninterrupted invocation as the initial private test-row Parquet. Exact execution-history details remain partly unresolved; the P3-008C report records the evidence and limits of reconstruction. The independent review reproduced all reported primary, secondary, and expected-random policy fields from the saved test rows using the final code.
- The source file has no unique customer ID, and row-split records should not be treated as verified identities. The test split is from a widely published dataset and does not create genuine analyst blinding.
- Neither average effects nor development CATE rankings are established to transport to UCI Online Retail II customers or present-day campaigns.

## Implications for the customer intelligence system

The wider project should keep five outputs distinct:

| Output | Question answered | Evidence here |
|---|---|---|
| Purchase propensity | How likely is a customer to purchase? | Predictive M2 work on observational UCI customer history. |
| Future value | How much might a customer spend? | Predictive P3-006 estimates on UCI history. |
| Segmentation | Which customers share historical behavior profiles? | Descriptive P3-007 clusters and RFM groups. |
| Uplift | How might assignment to an intervention change outcomes by customer characteristics? | Hillstrom development CATE predictions; no validated individual scores. |
| Policy value | What outcome is expected under a particular targeting rule? | Randomized Hillstrom estimates for the fixed random-allocation policy; no proven personalized gain. |

A high purchase propensity does not imply high treatment uplift: customers likely to buy may do so without an email. The Hillstrom results support a reusable causal workflow and report-level evidence, not deployable uplift scores for UCI customers.

## Integration-ready summary for P3-009

An application may present a clearly labeled **historical randomized-study evidence panel** containing:

- The confirmatory Men's-email ITT visit ATE, sample counts, Newcombe interval, and exact p-value.
- The expected 20% random-targeting value and scaled interval, identified as expected random allocation rather than personalization.
- Holm-adjusted secondary visit contrasts, identified as secondary.
- A separate research-only development table of learner policy comparisons, showing the intervals, expected-random reference, model-selection result, and exploratory status.

The application must not present customer-level Hillstrom CATEs as validated predictions for UCI customers, recommend a personalized campaign, call gross spend “incremental revenue,” or imply that the test split can be reused. State that exposure is assignment rather than observed engagement, model comparisons are exploratory, conversion/spend evidence is inconclusive, and the results do not establish transportability or profit uplift. No causal model in this workstream is approved for targeting deployment.

## Recommended next research step

Validate personalized targeting in a new, prospective randomized campaign in the intended customer population. Predeclare treatment arms, exposure logging, visit/conversion/spend outcomes, follow-up window, contact cost and margin, a fixed treatment budget, policy-value estimator, and a genuinely untouched evaluation sample. This is a recommendation only; no campaign or application work is initiated here.

# P3-008C — Locked Test Causal Evaluation

## Frozen protocol and provenance

This is the one-time evaluation on the previously unopened P3-008A test split. The original 64,000-row Hillstrom experiment, two-week outcome definitions, 60/20/20 stratified split, and P3-008B selection were preserved. Source SHA-256: `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`; split SHA-256: `0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce`.

Before reading outcomes, the repository was verified at commit `24a6ab38c4e9fa77eca763b46dbe5ca23d897abb` with a clean working tree. The frozen private P3-008B aggregate selected `constant_ate`; its prediction artifact hash matched. The split contained 38,400 training, 12,800 development, and 12,800 test rows. Test assignment counts from the assignment column were 4,262 Men's email, 4,261 no email, and 4,277 Women's email. The primary Men/control contrast therefore has 8,523 eligible rows. No split was regenerated.

The primary interval and test followed P3-008A: Newcombe's hybrid score interval using uncorrected Wilson limits, and a two-sided exact conditional randomization test using the absolute risk difference and the observed pairwise arm counts. Secondary binary contrasts use the same interval and exact randomization test; secondary p-values are Holm-adjusted over the eight prespecified contrast/outcome tests. Spend uncertainty uses a stratified customer-row percentile bootstrap (20,000 resamples) and a two-sided fixed-count Monte Carlo randomization test (50,000 assignments, plus-one correction). No candidate-model test diagnostics were run, and the test results did not select or alter a model.

### Execution provenance

**Verified from the session transcript and local files:** The failed preflight command read the dataset with `usecols=["segment"]` to obtain assignment labels, then failed while joining metadata because the pandas join axes were incompatible. It did not request `visit`, `conversion`, or `spend` in that command. The test-row Parquet has a filesystem creation/modification time of 23:18:31; the aggregate JSON was created at 23:18:40 and later modified at 23:21:13. The runner source has a modification time of 23:20:29, the report 23:21:08, and the focused tests 23:21:40.

**Evidence-supported reconstruction:** The session transcript records one full runner invocation after the metadata preflight. The runner's `load_locked_test` reads only the rows marked `test` and requests `segment`, `visit`, `conversion`, and `spend`; its next output is the private test-row Parquet. This is the first confirmed test-outcome load in the available transcript, and the Parquet timestamp is consistent with that invocation, although file timestamps do not record the exact moment `read_csv` parsed outcomes. After the outcome file had been opened, the runner source was edited to add the realized treatment share derived from arm counts to result summaries. That change did not alter the estimators, interval formulas, hypotheses, outcome definitions, or multiplicity procedure. The aggregate was then postprocessed from its saved JSON to add secondary-contrast propensities using recorded treated/control counts; that step did not reload row-level outcomes. The test file was subsequently edited to make a synthetic sample-size assertion clearer. The final code did not produce the aggregate in one uninterrupted invocation: the stored aggregate contains the original statistical results plus the later count-derived propensity fields.

Claude independently reproduced every reported primary, secondary, and expected-random policy-value field from the saved test rows using the final code. No full locked evaluation was rerun for this correction.

**Unresolved:** The local shell-history files checked did not provide a command log. File timestamps alone cannot establish exact parser start time, whether an unrecorded process invocation occurred, or the uninterrupted sequence of every write. Accordingly, this report does not claim the analysis was executed only once; it records the one full invocation visible in the session transcript and the subsequent source/aggregate edits evidenced above.

## Primary confirmatory ATE

The estimand is the intention-to-treat effect of assignment to Men's email versus no email on website visit during the original two-week outcome window.

| Assignment | Test customers | Visit events | Visit rate |
|---|---:|---:|---:|
| Men's email | 4,262 | 802 | 18.817% |
| No email | 4,261 | 454 | 10.655% |

The realized pairwise treatment propensity is 4,262 / 8,523 = **0.50006**; each secondary contrast uses its own realized treated share by the same convention. The randomized difference in visit rates is **+8.163 percentage points**, or **81.63 additional visits per 1,000 assigned customers**. The unpooled standard error is **0.763 percentage points**. The predeclared Newcombe 95% interval is **+6.667 to +9.658 percentage points** (66.67 to 96.58 additional visits per 1,000). The exact two-sided conditional randomization p-value is **1.53 × 10⁻²⁶**.

This is the single primary confirmatory test. It is evidence that assignment to this historical Men's email campaign increased two-week visit probability in this test sample. It is an assignment effect; email delivery, opening, and reading are not observed.

## Secondary ATEs

Binary outcomes are reported as risk differences in percentage points with Newcombe/Wilson intervals and exact two-sided randomization p-values. Spend is gross USD per assigned customer; its interval is a stratified customer-row percentile bootstrap interval, and its p-value is a fixed-count Monte Carlo randomization test. Holm adjustment covers all eight secondary p-values jointly.

| Contrast | Outcome | Treated / control n | Treated / control mean | Difference (95% CI) | Raw p | Holm p |
|---|---|---:|---:|---:|---:|---:|
| Men's vs no email | Conversion | 4,262 / 4,261 | 1.032% / 0.681% | +0.352 pp [−0.043, +0.759] | 0.0992 | 0.5288 |
| Men's vs no email | Spend (USD/customer) | 4,262 / 4,261 | 1.131 / 0.683 | +0.447 [−0.134, +1.070] | 0.1416 | 0.5288 |
| Women's vs no email | Visit | 4,277 / 4,261 | 15.502% / 10.655% | +4.847 pp [+3.420, +6.275] | 3.41e−11 | 2.73e−10 |
| Women's vs no email | Conversion | 4,277 / 4,261 | 1.029% / 0.681% | +0.348 pp [−0.046, +0.754] | 0.0992 | 0.5288 |
| Women's vs no email | Spend (USD/customer) | 4,277 / 4,261 | 1.159 / 0.683 | +0.476 [−0.076, +1.025] | 0.0881 | 0.5288 |
| Men's vs Women's | Visit | 4,262 / 4,277 | 18.817% / 15.502% | +3.316 pp [+1.717, +4.914] | 5.13e−05 | 0.000359 |
| Men's vs Women's | Conversion | 4,262 / 4,277 | 1.032% / 1.029% | +0.004 pp [−0.433, +0.441] | 1.0000 | 1.0000 |
| Men's vs Women's | Spend (USD/customer) | 4,262 / 4,277 | 1.131 / 1.159 | −0.028 [−0.663, +0.634] | 0.9323 | 1.0000 |

After Holm adjustment, the two secondary visit contrasts remain statistically distinguishable from zero. The conversion and spend contrasts do not. Conversion is rare, and spend is highly zero-inflated and skewed; their estimates have substantial uncertainty and should not be interpreted as proof of no effect. The Monte Carlo spend p-values have estimated Monte Carlo standard errors between 0.0011 and 0.0016.

**Predeclared adjusted analysis omitted:** P3-008A also specified a secondary Lin-style covariate-adjusted analysis with treatment-by-centered-covariate terms and HC2 robust standard errors. It was not executed in P3-008C, and this omission was not preplanned. No adjusted estimate or p-value is available. This omission does not change the primary unadjusted randomized difference-in-means estimate above.

## Frozen 20% policy value

The P3-008B selected policy is constant ATE, which corresponds to random assignment within the treatment budget rather than personalization. Its primary test policy value is expected random targeting, not one realized random draw:

**Expected incremental visits per 1,000 eligible customers = 0.20 × test ATE per 1,000 = 16.33.**

Scaling the primary Newcombe interval by 0.20 gives a 95% interval of **13.33 to 19.32 incremental visits per 1,000**. Treat-none is the zero-increment reference. This expected value describes the average value of random targeting at a 20% budget under the estimated test ATE; it is not a realized campaign result and contains no contact cost or profit calculation. The earlier seeded-draw result is not used as the primary test policy estimate.

## Candidate diagnostics and interpretation

No frozen learner candidate test diagnostics were run. P3-008B retained row-level development predictions, but did not retain fitted model objects or candidate test predictions. Candidate diagnostics were optional; this milestone did not refit models or expand the experiment. XGBoost remains supplementary and was not promoted into formal selection.

The primary ATE is an average randomized assignment effect. P3-008B's CATE scores are conditional-effect predictions; this test evaluation does not validate individual effects. Ranking quality concerns ordering customers by predicted effect, while policy value concerns the outcome under a specified assignment rule. No test-set CATE ranking, candidate Qini/AUUC, or personalized-policy value was estimated. A positive average email effect therefore does not establish that personalized targeting improves on random targeting. Likewise, the P3-008B null promotion result does not establish homogeneous treatment effects.

## Reproducibility and limitations

The runner accessed only test rows after checksum validation and saved test row assignments/outcomes and aggregate results under `../source_data/hillstrom/p3_008c_outputs/`, outside Git. It performed zero model fits and no model selection. Randomization/bootstrap seeds, replicate counts, test population counts, and all aggregate statistics are recorded in the private JSON artifact. The public report contains only aggregate-safe results.

This remains one historical experiment with no repeated campaigns or observed email engagement. The test split is a held-out subset of a widely published dataset, so it protects against direct reuse in this analysis but does not provide genuine analyst blinding. Secondary results are subject to multiplicity and low event counts; spend is especially uncertain. These findings do not establish causal transportability to Commercial Retention Analytics customers or current campaigns.

## P3-008D closure

P3-008D should archive the protocol, private reproducibility artifacts, and aggregate report; confirm that the locked test was evaluated once and remains excluded from later tuning; and summarize the causal conclusion without adding a new model search. Any future uplift study should use a newly randomized campaign with predeclared outcomes, contact costs, and a genuinely prospective evaluation sample.

# M1-010 — Independent Review of M1-009 Baseline Results

**Reviewer:** Claude Code (independent scientific reviewer)
**Review date:** 2026-11-12
**Verdict:** **PASS WITH CONDITIONS**

## Summary

The M1-009 experiment was predeclared, executed once, and implemented as specified. Every reported partition count, coefficient, AUC, bootstrap interval, Brier score and monthly descriptive was reproduced exactly using independent code: a separate Newton–Raphson logistic fit, a rank-based AUC and a re-implemented bootstrap. No leakage, test-set tuning or unreported modelling decision was found. The negative primary finding is reported accurately and without exaggeration.

There is one material reporting error. Model C's calibration diagnostic is reported as "not stably estimable". It is estimable. The optimizer reached the optimum, but the code treated a numerical precision warning as a failure. This affects a diagnostic-only secondary output, not the primary result or the success criterion.

There is also one disclosure gap. Before the protocol was frozen, the M1-008 independent review (this reviewer) inspected test-set outcome rates. That examination is recorded below.

## Evidence reviewed

| Artifact | SHA-256 |
| --- | --- |
| `docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md` | `d5be6bfefbbbddf8e5f7dfe8a81202cc04c1d18e7480c698aec5211b3c92c3ac` (matches the frozen hash in code and results) |
| `src/day21_baseline.py` | `f7b3cb2a65a4e99af797bc22df403a353bc4bc5aaeafed49c37ee3d67c979daa` |
| `tests/test_day21_baseline.py` | `ca64c23bdf7efd9fd24fa043e02552ff1ec7a8458fd92adc46c5a1ceb05faa70` |
| External M1-007 cohort Parquet | `0f2217598c5e58c83946edcb4f6a5eeb652b987d9e46f8b7779616c26342810e` (matches the M1-007 split manifest) |

Tests: 23 of 23 pass (5 baseline, 18 cohort).

## 1. Was the protocol fixed before model execution?

**Yes.** The implementing agent's local session log (`~/.codex/sessions/2026/11/11/rollout-2026-11-11T22-55-19-…jsonl`) gives this command timeline (UTC; the machine's timezone is GMT):

| Time | Action |
| --- | --- |
| 00:42:00 | Protocol written (file modification time agrees) |
| 00:43:37–00:43:47 | `src/day21_baseline.py` created, with the frozen hash embedded |
| 00:44:17–00:44:36 | Tests written and run; the protocol hash is verified |
| **00:44:47** | **The single experiment run** (results report `2026-11-12T00:44:49Z`) |
| 00:46:20 | Results report written |

A search of every agent session from 10–12 November found no `LogisticRegression`, `roc_auc`, Brier or baseline execution before 00:43:37, and exactly one invocation of the experiment runner. The protocol file still hashes to the frozen value, so it was not edited after the run.

**Disclosure: the holdout was not entirely unseen before the protocol was frozen.** The M1-008 review, written before the M1-009 protocol, computed descriptive test-partition statistics:

- the test prevalence (46.6%)
- prevalence by decision month
- prevalence by tercile of first-day gross spend (38.2% / 54.2% / 45.7%)

That review also recommended the feature set later adopted. The tercile pattern did not increase steadily with spend in test. If anything, that argues against first-day spend as a predictor, yet spend was retained, so the observation did not steer the protocol towards success.

The look did happen, however, and future pre-registrations should use a reviewer workflow that does not inspect holdout outcomes. This does not invalidate the result. The criterion was not met, and none of the pre-freeze information could have inflated it.

## 2. Do the models and transformations match the specification?

**Yes.**

- Allowlists are exact.
- Features are transformed with `log1p` and standardised with the training mean and population SD (`ddof=0`). The test set is transformed with frozen training statistics.
- Model A predicts the constant training prevalence of 0.2961.
- Models B and C are unpenalised logistic regressions with an intercept, fitted with lbfgs (`tol=1e-10`, `max_iter=5000`).

An independent Newton–Raphson fit reproduces every coefficient to four decimal places:

| Model | Coefficients (intercept, then features in protocol order) |
| --- | --- |
| B | −0.8721, 0.1719 |
| C | −0.8812, −0.0883, 0.2253, 0.1427 |

The three log features are correlated in training (r = 0.79 gross–quantity, 0.60 gross–diversity and 0.62 quantity–diversity). The report correctly treats the sign reversal for gross spend as uninterpretable.

## 3. Were the partitions used correctly?

**Yes.**

- I re-derived the partitions from the raw cohort columns: acquisition boundary 2010-12-01 07:45, Day-21 eligibility, decision before 2011-07-01 with deadline at or before the cutoff for training, and decision at or after the cutoff with deadline at or before 2011-12-09 12:50 for test.
- This gives 304 (90 / 214) training and 208 (97 / 111) test rows, with customer sets identical to the stored `evaluation_partition` values.
- The models are fitted only on training rows. The test set is used only for scoring.
- The 326 labels that matured after the cutoff, the 486 immature rows and the 4,528 non-primary customers are excluded from both.

## 4. Are the reported metrics mathematically correct?

The values below were recomputed independently from refitted predictions. The run kept no per-customer predictions, so a deterministic refit was required, and it reproduces the run exactly.

| Quantity | Reported | Recomputed |
| --- | --- | --- |
| AUC B / C | 0.5439 / 0.5189 | 0.5439 / 0.5189 |
| C bootstrap 95% (seed 20261112, 2,000 resamples, 0 omitted) | [0.4410, 0.5963] | [0.4410, 0.5963]; 0 omitted |
| C DeLong 95% (reviewer cross-check, not predeclared) | — | [0.440, 0.598] |
| Brier A / B / C | 0.2779 / 0.2761 / 0.2743 | 0.2779 / 0.2761 / 0.2743 |
| Mean predicted rate A / B / C | 0.2961 / 0.3033 / 0.3091 | identical |
| B calibration intercept / slope | 0.112 / 0.295 | 0.112 / 0.295 (SE 0.64 / 0.74) |
| **C calibration intercept / slope** | **"Not stably estimable"** | **0.172 / 0.376 (SE 0.45 / 0.53)** |
| Monthly n, AUC and Brier (July, August, September) | as reported | identical |

### Finding 1 (material, reporting): Model C's calibration diagnostic was misreported as not estimable

`calibration_diagnostic()` uses BFGS with `gtol=1e-8` and treats `fit.success == False` as failure. For Model C, BFGS stops with "Desired error not necessarily achieved due to precision loss". It does so at (0.1722, 0.3758), where the gradient is about 2e-8, so it has converged. Newton–Raphson gives the same estimate with a finite, well-conditioned information matrix.

The protocol allows "unavailable" only for numerical instability or non-identifiability. Neither applies here, so the results report's statement that the calibration regression "did not yield a stable estimate" is factually incorrect.

The substantive conclusion is unchanged. Both slopes are far below 1, with very wide standard errors, which is consistent with near-chance ranking. All three models under-predict aggregate test prevalence by about 16–17 percentage points.

### Reviewer context (descriptive, not predeclared)

- **Calibration-in-the-large:** with the slope fixed at 1 (a logit offset), the intercept is about +0.70 for B and +0.68 for C. The training-derived probabilities are shifted by roughly 0.7 logits.
- **Brier against the test-prevalence constant:** a constant equal to the *test* prevalence would score Brier 0.2489, better than all three models. The 0.0036 Brier advantage of C over A therefore says nothing about useful probability accuracy. The report says so correctly.
- **Difference between C and B:** a paired bootstrap 95% interval for AUC(C) − AUC(B) is [−0.085, 0.036]. There is no evidence that the models differ, and the report correctly declines to prefer B.

## 5. Leakage, test-set tuning and unreported decisions

- **Leakage:** none found. Features are first-day merchandise measures selected by allowlist. Dates, weekday, status and maturity fields are excluded. Training labels were all observable by the cutoff.
- **Test-set tuning:** none. There was one run, no refits, no threshold selection and no recalibration, and the monthly results were not used for any selection.
- **Unreported decisions:**
  - `random_state` is set on lbfgs but has no effect.
  - The bootstrap omission rule never applied, since 0 resamples were omitted.

  Neither is material. The pre-freeze holdout inspection under §1 is the only undisclosed item.

## 6. Do the conclusions reflect the sample size and the seasonal shift?

**Yes, with one recommended clarification.**

- The report states that the criterion was not met.
- It describes discrimination as only slightly above chance, with an interval spanning 0.5.
- It refuses to select Model B after seeing the results and separates ranking from calibration.
- It attributes the prevalence gap (29.6% → 46.6%) to calendar shift and disclaims deployment readiness.

None of these claims is exaggerated.

Recommended clarification: the result is **inconclusive, not evidence that no signal exists**. The upper bound (0.596) cannot rule out modest discrimination around AUC 0.6. The phrase "limited predictive signal … with substantial uncertainty" is acceptable. The statement should not be strengthened to "first-day characteristics do not predict repeat purchase".

## Conditions for closure

1. **Erratum for Model C's calibration.** Add a dated addendum to the M1-009 results report, without altering the frozen run record. It should state that the predeclared joint calibration regression for Model C is estimable at intercept 0.172 and slope 0.376 (SE 0.45 / 0.53). The "not estimable" status came from a BFGS precision-loss flag at a converged optimum, and the conclusion is unchanged. In the code, judge convergence on the gradient norm, or use Newton or IRLS, before any reuse, and add a unit test for `calibration_diagnostic`.
2. **Holdout-inspection disclosure.** Add one sentence to the results report recording that the M1-008 review inspected descriptive test-outcome rates (overall, by month and by gross tercile) before the protocol was frozen. The look was not used to tune the model and could not have favoured success.

Optional:

- Add the "inconclusive, not evidence of absence" wording from §6.
- Keep an aggregate results JSON, with no customer-level rows, alongside the report.
- Pin the scikit-learn version, given the `penalty=None` deprecation warning.

## Milestone readiness

The primary result is valid and reproducible. **Once the two conditions are added as documentation, M1-009 is ready for milestone closure and a local commit**, covering `src/day21_cohort.py`, `src/day21_baseline.py`, both test files and `docs/research/`. No rerun of the experiment is required or appropriate.

No code, data, protocol or results were modified by this review. Reviewer scripts are outside the repository, in the session scratchpad (`rev010.py`).

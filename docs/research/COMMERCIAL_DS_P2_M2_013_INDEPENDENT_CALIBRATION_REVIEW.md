# M2-013 — Independent Review of M2-012 Sequential Calibration

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS WITH CONDITIONS**

Every reported pool, offset, Brier score, calibration gap, ranking metric and the paired bootstrap interval reproduces independently. The historical simulation uses no future outcomes.

One wording correction is required. M2-012 describes its strict label-availability rule as a "correction" of M2-011. The inclusive rule in M2-011 is also leakage-free, and it is the rule the verified M2-007 baseline split used. As written, the M2-012 text implies an error that does not exist.

## A. Historical information validity

**Labels and coverage.** Every test row has `outcome_window_end_exclusive = T + 30 days` and complete coverage. Label maturity by month:

| Month | Labels mature at |
| --- | --- |
| July | 2011-07-31 |
| August | 2011-08-31 |
| September | **2011-10-01 00:00** |
| October | 2011-10-31 |
| November | 2011-12-01 |

**Calibration pools.** I rebuilt them independently, requiring the decision before the target decision `T*`, `end < T*` and complete follow-up:

| Target month | Pool | Customers | Positive / negative | Pool prevalence | Latest maturity | Offset δ |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| September | 8,640 (July–August) | 4,432 | 1,604 / 7,036 | 18.56% | 08-31 | +0.08328 |
| October | 8,640 (July–August) | 4,432 | 1,604 / 7,036 | 18.56% | 08-31 | +0.08328 |
| November | 17,328 (July–October) | 4,756 | 3,696 / 13,632 | 21.33% | 10-31 | +0.30286 |

All values match the report. No target month's own labels, and no label maturing after its decision, enter its pool. The simulation reflects what was available at each decision, not what is available in hindsight.

**Run order.** The session log shows the strict rule came from the owner's M2-012 instruction and was coded at 16:20, before any results.

- The first full run was interrupted before it produced an interval.
- The bootstrap was then rewritten for speed (cluster draws changed from `rng.choice` to `rng.integers`). The agent had seen the pooled point estimates at that stage, but no interval.
- The final run took place at 16:25.

The rewrite changes which replicates a given seed draws, but not the method, and no interval was observed beforehand. This is not material.

### Finding 1 (Medium; required wording correction): the boundary rule is a convention, not a correction

The September outcome window `[09-01, 10-01)` is fully observed at 2011-10-01 00:00, so an inclusive rule (`end <= T*`) uses no future information. That is M2-011's predeclared rule, and it is the rule M2-007 used to admit June training labels ending exactly at the 1 July cutoff.

The strict rule is a valid, more conservative choice, for example to allow for operational data latency. However, the M2-012 sentence "This corrects the M2-011 planning table, which had applied an inclusive maturity boundary" wrongly implies that the inclusive rule leaks future information. It also implicitly questions the verified M2-007 training split.

**Consequence.** The headline conclusions do not change, but the strict rule understates the benefit. Reviewer sensitivity analysis (descriptive only, not a replacement result) using the inclusive rule:

- October's pool becomes 12,964 rows, with δ = +0.238.
- October's adjusted gap is 3.37 pp instead of 5.29 pp.
- The pooled Brier difference is −0.00500 instead of −0.00447.
- September and November are unchanged.

**Correction.** Reword M2-012 to say that the strict rule is an owner-specified conservative convention. The inclusive rule is also leakage-free and is consistent with M2-007. Optionally, cite the October sensitivity above.

## B. Calibration implementation

- **Inputs unchanged.** The raw Model C predictions in the M2-012 output are identical to M2-008, with a maximum difference of 0. The M2-008 predictions, models and run-manifest hashes are unchanged. The code reconstructs B and C from the frozen coefficients and preprocessing and asserts the M2-008 metrics. Nothing is refitted.
- **Offsets reproduced.** The offset is an intercept-only MLE with the slope fixed at 1, using `logit(clip(p, 1e-6))`. I reproduced each δ by independent Newton iteration. My adjusted probabilities match the saved ones to within 2e-15.
- **Correct month, ranks preserved.** Each δ is applied only to its target month. Within-month ranking is identical for September, October and November.

## C. Evaluation

Values reproduced independently:

| | Prevalence | Mean prediction, raw → adjusted | Brier, raw → adjusted | Gap (pp), raw → adjusted | Calibration intercept / slope, raw → adjusted |
| --- | ---: | --- | --- | --- | --- |
| September | 24.12% | 17.44 → 18.40% | 0.15050 → 0.14901 | 6.69 → 5.72 | 0.519 / 1.000 → 0.435 / 1.000 |
| October | 24.04% | 17.76 → 18.74% | 0.15694 → 0.15577 | 6.27 → 5.29 | 0.259 / 0.853 → 0.188 / 0.853 |
| November | 32.14% | 18.07 → 21.90% | 0.19700 → 0.18625 | 14.06 → 10.24 | 0.930 / 0.979 → 0.633 / 0.979 |
| **Pooled (13,032 snapshots)** | 26.76% | 17.76 → 19.68% | **0.16815 → 0.16369** | **9.01 → 7.08** | see note → 0.435 / 0.949 |

Pooled metrics are unweighted means over snapshots, as intended.

**Ranking and targeting.** Monthly AUC, average precision and precision/lift at 5%, 10% and 20% match the report for both B and C in all five months. Capacity uses `ceil(capacity × n)`, and no ties occur at the boundaries.

- Model C's AUC ranges from 0.742 to 0.812 over July–November, and from 0.742 to 0.773 over September–November.
- Model C's top-10% precision ranges from 64.5% to 80.0%, with lift from 2.49 to 3.68.
- The report correctly explains the small change in pooled AUC (0.754 → 0.758) as reordering across months, not improved discrimination within months.

**Note (Low, optional): the raw pooled calibration diagnostic is estimable.** The report lists the raw pooled diagnostic as "unavailable". It is estimable: an independent Newton fit gives intercept 0.566, slope 0.936. The `calibration_diagnostic()` stability check uses a fixed absolute gradient tolerance (`1e-7`) that does not scale with sample size, so it can reject a converged fit on large pools. This is the same class of false negative recorded in M1-010.

The diagnostic does not affect any adjustment. The optional fixes are to note the value in the report and, in a later milestone, to make the tolerance relative to sample size.

## D. Statistical uncertainty

The bootstrap resamples the 4,999 test customers with `PCG64(20261112)`:

- Each row is weighted by its customer's draw multiplicity, so multiplicity is preserved.
- The same weights apply across the pool and evaluation months.
- Each replicate refits δ on the weighted historical pool.
- Raw and adjusted predictions are evaluated on the same weighted rows.

**Independent reproduction:** **[−0.00553, −0.00340]**, replicate mean −0.00446, 2,000 valid and 0 omitted. This is identical to the report.

## E. Scientific interpretation

The report states the following accurately:

- The Brier improvement and its interval.
- That underprediction persists, especially November's gap of about 10 pp.
- That the analysis is exploratory, on a holdout that had already been examined.
- That ranking is unchanged and is not CRM uplift.
- That there is no claim of deployment readiness or independent confirmation.

**Is the improvement practically meaningful? Modest.**

- The Brier score falls by about 2.7% relative to raw.
- The pooled level gap closes by about a fifth (9.0 → 7.1 pp).
- Ranking is unchanged, so selection at a fixed capacity is unaffected.
- The benefit applies only where predicted volumes or absolute probabilities matter, such as forecasting the number of purchasers or using probability thresholds.

A lagged intercept will always trail a rising seasonal prevalence, which is visible in November. The report's framing as motivation for prospective validation is appropriate.

## F. Tests and reproducibility

- **Tests:** 7 of 7 calibration tests pass. They cover the strict boundary, pool expansion, exclusion of incomplete or unknown labels, rank preservation, cluster multiplicity, the intercept-fit property and determinism. The full `tests/` suite runs 109 tests, all passing except the existing Spark skip.
- **Hashes:** the aggregate and prediction output hashes match the M2-012 manifest. Input hashes match the frozen M2-004 and M2-008 artifacts.
- **Storage:** customer-level outputs are outside Git, with no tracked Parquet files.
- **Scope:** no committed files were modified. The only new files are the two M2-011/M2-012 documents, the calibration module and its tests.

## Readiness

After the Finding 1 wording correction to the M2-012 report, **M2-011 through M2-013 are ready for a scoped local commit**:

- `src/monthly_purchase_calibration.py`
- `tests/test_monthly_purchase_calibration.py`
- the M2-011, M2-012 and M2-013 documents

The calibration outputs stay outside Git. No rerun is needed, because the executed strict-rule results remain valid as reported.

No code, data, prior reports or Git state were modified by this review. Reviewer scripts are kept outside the repository.

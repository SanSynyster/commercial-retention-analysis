# M2-009 — Independent Review of M2-008 Established-Customer Baseline Results

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS**

The M2-008 experiment followed the frozen M2-007 protocol. Every reported model metric, the primary customer-clustered interval, the calibration diagnostics, the calibration bands and the capacity metrics reproduce independently. The primary criterion was met, and the conclusions are appropriately cautious. Three optional disclosures would sharpen the interpretation; none affects validity.

## A. Protocol adherence

**Inputs and hashes.** All of the following match the protocol and the run manifest:

- protocol `790d5377…e7b4`
- dataset `44c580a8…52a8`
- dataset manifest `3d7ee78a…6a13`
- builder `58f29d27…a82b`
- models JSON, predictions Parquet and run manifest

**Execution order.** From the implementing agent's session log (UTC):

| Time | Action |
| --- | --- |
| 15:28–15:34 | Hashes and aggregate counts checked. No fits. |
| 15:31:12 | Protocol finalised |
| 15:37–15:40 | Code and synthetic-data tests written |
| **15:41:21** | **The single experiment run** |

No model fit or test metric was computed before the protocol was frozen, and the experiment ran once.

**Partitions.** Training and test are selected by the stored `evaluation_partition`:

- training: 25,647 snapshots / 4,808 customers / 4,573 positives
- test: 21,672 / 4,999 / 5,092
- 4,265 customers in both

All labels are mature 0/1.

**Features and preprocessing.** Feature lists and order match exactly (RFM = recency, 365-day occasions, 365-day gross). Preprocessing follows the protocol:

- `log1p`, then training-only median imputation
- training-only mean and population SD (`ddof=0`)
- no constant columns
- the test set is transformed with the frozen statistics

**Models.** These match the protocol: `lbfgs`, L2, `C=1.0`, `tol=1e-8`, `max_iter=5000`, no class weights. B converged in 12 iterations and C in 86.

**Tuning and selection.** No test-driven tuning, threshold selection or recalibration occurred.

**Deviations.** No substantive deviation was found. The scikit-learn 1.8 `penalty="l2"` FutureWarning is harmless.

## B. Independent model reproduction

The models were refitted with independent Newton–Raphson code minimising `C·Σ logloss + ½‖w‖²`, with the intercept left unpenalised. At convergence the maximum gradient was 1e-12 or smaller.

| | B (RFM) | C (full 11) |
| --- | --- | --- |
| Maximum coefficient difference vs. saved model | 4e-8 | 4e-6 |
| Maximum test-probability difference vs. saved predictions | 5e-8 | 2e-6 |

The saved predictions align row for row with the test partition.

| Model | ROC-AUC | Average precision | Brier | Mean predicted |
| --- | ---: | ---: | ---: | ---: |
| A | 0.50000 | 0.23496 | 0.18296 | 0.17831 |
| B | 0.75995 | 0.54830 | 0.14968 | 0.17758 |
| C | **0.76599** | 0.56595 | 0.14744 | 0.17692 |

All values are identical to the report. The AUC and average precision were recomputed with independent tie-aware implementations.

## C. Customer-clustered bootstrap

The code resamples customers, not snapshots:

- the 4,999 test customer IDs are sorted
- `Generator(PCG64(20261112))` draws 4,999 clusters with replacement
- each row is weighted by its cluster's draw multiplicity, so all of a selected customer's snapshots are kept, with multiplicity preserved
- single-class replicates are omitted without redrawing
- the interval is the 2.5th–97.5th percentile of the valid replicates

**Independent reproduction:** **[0.75646, 0.77490]**, with 2,000 valid and 0 omitted. This is identical to the report, so the primary criterion (lower bound > 0.50) is met.

For comparison, a naive row-level bootstrap gives roughly [0.759, 0.774]. Clustering widens the interval by about 25%, as expected.

The point estimate is snapshot-weighted: customers with more test months contribute more pairs, and the pooled AUC compares rows across months. Monthly AUCs for C range from 0.742 to 0.812 and bracket the pooled 0.766, so pooling does not drive the result. The interval reflects customer-sampling uncertainty within this one period, not variation across time periods. The report says so.

## D. Calibration and targeting

**Calibration diagnostics** (independent Newton fit of `y ~ logit(p)`):

| Model | Intercept | Slope | Standard errors |
| --- | --- | --- | --- |
| B | 0.343 | 0.932 | 0.031 / 0.017 |
| C | 0.411 | 0.973 | 0.032 / 0.017 |

Both match the report. Model C's "stationary optimum after optimizer warning" status is correct this time: the corrected diagnostic accepts a converged optimum, unlike M1-009. Model A's calibration-in-the-large of 0.347 = logit(0.2350) − logit(0.1783) is also correct.

**Calibration bands and capacity.**

- Every band count, mean predicted value and observed rate matches the report.
- At 10% capacity, Model C selects exactly 2,168 rows with precision **0.6928** and lift **2.949**. Model B: 0.6734 / 2.866.
- At 5% and 20%, both models match the report.
- No probability ties occur at any capacity boundary.

**Ranking versus calibration.** The report correctly distinguishes the two. Ranking is strong. The slope is close to 1, but there is a level shift: the logit offset is about +0.45, and C's mean prediction is 17.7% against 23.5% observed.

## E. Temporal validity

All checks pass:

- Training decisions fall in January–June 2011, with every outcome window ending at or before 2011-07-01.
- Test decisions fall in July–November 2011, and every test outcome is mature.
- Preprocessing used training data only.
- The features are the fixed-window M2-004 set verified in M2-005.
- Repeated customers are allowed by design.

The monthly counts, prevalences and AUCs in the report match the reviewer's recomputation.

## F. Scientific interpretation

| Claim | Supported? |
| --- | --- |
| Useful retrospective discrimination | **Yes.** AUC is about 0.76–0.77 and average precision is 0.55–0.57 against a 0.235 base rate. |
| Primary success | **Yes.** It was predeclared, the interval reproduces, and the lower bound is far above 0.50. |
| The full feature set adds only a little over RFM | **Yes.** ΔAUC is +0.006. The report makes no inferential claim and states that none was predeclared. |
| Material underprediction of prevalence | **Yes.** It is worded accurately. |
| Cautious view of targeting lift | **Yes.** The report explicitly says lift is not incremental effect, and frames the CRM pilot as a randomised research hypothesis. |

The report makes no claim of causal effect, deployment readiness or generalisation beyond July–November 2011.

## Optional disclosures (not required for closure)

1. **Underprediction is seasonal, not uniform.**
   - Model C's monthly mean prediction is almost flat at 17.4–18.1%.
   - Observed prevalence is 18.8% in July, 18.4% in August, 24.1% in September, 24.0% in October and 32.1% in November.
   - The level shift is therefore concentrated in September–November, and July–August are approximately calibrated.

   The monthly probability summaries are in the run manifest, as the protocol requires. Adding one sentence to the report would make the seasonal source of miscalibration explicit.
2. **How much discrimination a simple rule achieves (reviewer post-hoc, descriptive).** Ranking test rows by the raw 365-day purchase-date count alone gives AUC 0.745, and recency alone gives 0.706. Most of the discrimination is therefore available from a simple frequency rule. This is useful context for "useful", and for any comparison with a business heuristic.
3. **Model C versus Model B (reviewer post-hoc, not predeclared).** A paired customer-clustered bootstrap of AUC(C) − AUC(B) gives [+0.004, +0.008]. The gain is consistent but practically negligible. This is consistent with the report's "modest, descriptive" wording and must not be presented as a confirmatory result.

## Readiness

There are no required corrections:

- 6 of 6 baseline tests pass
- the `tests/` suite runs 102 tests with 1 Spark skip
- no prediction or Parquet files are tracked by Git

**M2-007 through M2-009 are ready for milestone closure and a scoped local commit**:

- `src/monthly_purchase_baselines.py`
- `tests/test_monthly_purchase_baselines.py`
- the M2-007, M2-008 and M2-009 documents

All model, prediction and customer-level artifacts must stay outside Git.

No code, data, protocol or Git state was modified by this review. Reviewer scripts are kept outside the repository.

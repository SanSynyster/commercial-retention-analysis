# M2-003 — Independent Review of M2-002 Monthly Customer Snapshots

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS WITH CONDITIONS**

Eligibility, labels, maturity and the chronological split are correct and reproduce exactly. Two problems in the feature set must be fixed before modelling:

- Lifetime "observed" features grow with each anchor's history depth, which builds a train/test shift into the data.
- `snapshot_month` is listed as a predictor although training and test share no months.

Neither problem involves future information, and neither affects eligibility, labels or partitions.

## Evidence base

| Item | Value |
| --- | --- |
| `src/monthly_customer_snapshots.py` SHA-256 | `5a884ee803db68d293e90ece188c466350c43f9272179a60b490d4cd15aab1c8` (matches manifest `builder_sha256`) |
| External Parquet `…/source_data/uci_online_retail_ii/monthly_customer_snapshots_m2_002.parquet` | `ee6d3f11736283022a28b85e7ecde140c26add0e3828335cb7c352f367af98a0` (matches manifest and report) |
| Source pins in manifest | V1 `43465a06…`, V2 `32569a66…`: match the Phase 1 pins |
| Tests | 9 of 9 snapshot tests pass. No customer-level files are tracked by Git. |

**Method of independent reconstruction.** The canonical occasions were loaded through `load_validated_purchase_input()` and `build_purchase_occasions()`, the reviewed Phase 1 API. From there, everything was recomputed with separate reviewer code:

- the earliest-line occasion timestamps
- the anchors and the exact 365-day eligibility
- the 30-day half-open labels
- maturity
- the partitions

The results were then joined to the Parquet on `(customer_id, decision_time)`.

## Independently verified counts

| Quantity | Reviewer result |
| --- | --- |
| Canonical source | 1,044,848 rows; 36,594 occasions; 5,852 customers |
| Eligible snapshots / unique customers | **51,612 / 5,735**: keys match 1:1 (0 rows only in the reviewer's output, 0 only in the Parquet) |
| Mature positive / mature negative | **9,665 / 37,654** |
| Observed positive with incomplete follow-up / unknown | **573 / 3,720** (all December 2011) |
| Label and partition mismatches against Parquet | **0 / 0** |
| Training: rows / customers / positives / prevalence | **25,647 / 4,808 / 4,573 / 17.83%** |
| Test: rows / customers / positives / prevalence | **21,672 / 4,999 / 5,092 / 23.50%** |
| Customers in both partitions | **4,265** |
| Monthly eligible and positive counts, Jan–Dec 2011 | Identical to the M2-002 table |

## Review 1: canonical definitions

- **Occasions and gross merchandise:** these reuse the corrected-V2 occasion API. The code cross-checks lineage, line counts, dates and the merchandise-only category for every occasion.
- **Gross semantics:** gross uses the canonical `qualifying_gross_merchandise`, so the meaning is unchanged.
- **Frequency:** frequency is reported both as occasions and as distinct dates, which keeps the Phase 1 date-level repeat semantics available rather than redefining them.
- **Same-day purchases:** these cannot affect labels, because every decision falls at 00:00 and no occasion is stamped at exactly 00:00.

**Exact 365-day coverage and December 2010.** The exact rule is applied consistently to both the history and outcome windows, and no future information enters eligibility. It differs from M2-001, which counted December 2010 (4,239 snapshots) under date-level coverage.

The source evidence does not support treating 00:00–07:45 on 1 December 2009 as unobserved:

- the daily first-invoice time has a 5th percentile of 07:46 and a median of 08:41
- 95% of trading days start at or after 07:45

So 07:45 is an ordinary opening time, and that day is effectively covered. The exact rule is conservative and introduces no bias or leakage, so it is **not a defect**. It does discard 4,239 valid training rows (808 positive), and it departs from M2-001 without approval (Finding 3).

## Review 2: anchors and label boundaries

All boundaries are correct, and tests cover them:

- **Features:** use `< T`.
- **Outcome window:** `[T, T + 30d)`. A purchase exactly at `T` is a positive, and a purchase exactly at `T + 30d` is excluded.
- **Maturity:** the whole window must lie within the observed source.
- **December 2011 rows:** these stay as partial positives or unknown, never zero. No immature negative exists, since every `outcome_label == 0` row has `outcome_window_mature == True`.
- **Coverage gaps:** these block negatives.

Consecutive 30-day windows overlap by up to 2 days (February) or leave a 1-day gap (after 31-day months). Each anchor labels its own window independently, so this is handled consistently. The overlap is a source of within-customer dependence, not a defect.

## Review 3: point-in-time features

No genuine leakage was found:

- Every feature is computed from occasions before `T`.
- A June training label feeding a July test feature is legitimately available at July 1.
- No target-derived column is included in `FEATURE_COLUMNS`. Label, status, maturity and partition fields exist in the Parquet, so modelling must select features by allowlist.

### Finding 1 (Medium, required): lifetime features are non-stationary by construction

`_features_for_history()` computes these features over **all** observed history before `T`:

- `observed_*` totals
- `days_since_first_observed_qualifying_purchase`
- the average basket value, quantity and diversity
- `median_interpurchase_interval_days`

That history is left-censored at December 2009, so its depth grows from 13 months (January 2011 anchor) to 23 months (November 2011 anchor).

**Evidence.**

| Measure | Training | Test |
| --- | --- | --- |
| Maximum `days_since_first_observed…` | 547 | 700 (test values fall outside the training range) |
| Median `days_since_first_observed…` | 309 | 416 |
| Median lifetime-to-365-day occasion-count ratio, customers in both partitions | 1.00 | 1.43 |
| Missing `median_interpurchase_interval_days` | 30% | 24% |

**Consequence.** The test features drift systematically relative to training through an artefact of the data window, not through customer behaviour. Coefficients or splits learned on training will be misapplied in test. M2-001 explicitly advised keeping lifetime totals out because history is left-censored.

**Smallest correction.** Compute every history feature over the fixed `[T − 365 days, T)` window, the window that already defines eligibility. Remove `days_since_first_observed_qualifying_purchase` and the lifetime `observed_*` totals from `FEATURE_COLUMNS`. They can stay in the Parquet as metadata if wanted. Then regenerate the dataset to a new output path.

### Finding 2 (Medium, required): `snapshot_month` cannot be used as a predictor

Training contains 2011-01 to 2011-06 and test contains 2011-07 to 2011-11, so there is no category overlap. A model cannot estimate test-month effects, and one-hot encoding would silently map every test row to the baseline. This repeats the M1 calendar-feature issue (protocol rule L9).

**Correction:** remove `snapshot_month` from `FEATURE_COLUMNS` and keep it as a grouping column for month-level reporting.

**Not a defect: missing values.** `median_interpurchase_interval_days` is null for single-date histories. That is defensible, but the modelling protocol must predeclare how it is handled, for example with an indicator.

## Review 4: temporal evaluation

- Training anchors run from January to June 2011, all with `T + 30d ≤ 2011-07-01`. The June label ends exactly at the cutoff, so no training label needs post-cutoff information.
- Test anchors run from July to November 2011, all mature. December is excluded as immature.
- No snapshot is in both partitions. Mature rows reconcile: 47,319 = 25,647 + 21,672 + 0 unavailable.
- Repeated customers (4,265) are intentional, under the approved estimand. This is a credible as-of-July-1 historical scoring scenario.
- Prevalence rises from 17.8% to 23.5%, and November reaches 32.1% (Q4 onset). The report documents this.

## Review 5: repeated-customer dependence

`customer_id`, `decision_time` and `snapshot_month` are kept on every row. That is enough for:

- customer-clustered bootstrap intervals
- snapshot-level and month-level reporting
- a one-snapshot-per-customer sensitivity analysis

Nothing more is required before modelling. The modelling protocol should predeclare the clustered bootstrap and acknowledge both the repeated rows and the overlapping windows.

## Review 7: tests and reproducibility

The tests cover the boundaries that matter scientifically:

- anchor history
- `T` excluded from features and included in the outcome
- `T + 30d` excluded from the outcome
- mature, unknown and partial-positive labels
- coverage gaps
- the earliest line timestamp
- uniqueness
- repeated customers
- as-of availability

Provenance is pinned, the CLI refuses to write inside the repository or overwrite outputs, and no customer-level data is committed.

**Optional additions:**

- one truncation-invariance test (adding future events leaves features unchanged)
- one test asserting `FEATURE_COLUMNS` excludes calendar and lifetime fields after the fix

## Findings summary

| # | Severity | Item | Required? |
| --- | --- | --- | --- |
| 1 | Medium | Lifetime/left-censored features are non-stationary across anchors (`_features_for_history`, `FEATURE_COLUMNS`) | **Required:** fix the features to the trailing 365-day window, then regenerate |
| 2 | Medium | `snapshot_month` is a predictor with disjoint train/test categories (`FEATURE_COLUMNS`) | **Required:** remove from the feature list |
| 3 | Low | Exact-timestamp coverage drops December 2010 (4,239 rows, 808 positive), unlike M2-001. Evidence indicates 1 Dec 2009 is effectively fully covered. | Owner decision: keep (conservative) or adopt date-level coverage. Either way, record the decision. |
| 4 | Low (documentation) | The report's test-partition row omits the unique-customer count, which is 4,999 (the 5,092 shown is positives). The "snapshot month" label is the month of `T`, so its history runs through the end of the previous month. | Correct the report text |

## Readiness

Eligibility, labels, maturity, partitions and provenance are **valid and verified**. Findings 1 and 2 are bounded changes to `_features_for_history()` and `FEATURE_COLUMNS`. After regeneration, keys, labels and partitions should be unchanged. **M2-002 is ready for a scoped local commit once Findings 1–2 are fixed, the dataset is regenerated, and the report is corrected (Finding 4).** Modelling should not start on the current feature set.

No code, data or Git state was modified by this review. Reviewer scripts are kept outside the repository.

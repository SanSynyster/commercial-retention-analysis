# M2-005 — Targeted Verification of M2-004 Fixed-Window Feature Corrections

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS**

Both required M2-003 conditions are resolved, and the cohort, labels, maturity and partitions are unchanged. One test-count wording nit remains (D). It is optional.

## A. Feature list

`FEATURE_COLUMNS` in `src/monthly_customer_snapshots.py` and `feature_columns` in the M2-004 manifest both contain exactly the 11 expected predictors, in the expected order:

1. `days_since_last_qualifying_purchase`
2. `qualifying_purchase_occasions_365d`
3. `qualifying_purchase_dates_365d`
4. `qualifying_gross_merchandise_365d`
5. `average_qualifying_basket_value_365d`
6. `average_qualifying_basket_quantity_365d`
7. `average_basket_product_diversity_365d`
8. `qualifying_unique_product_count_365d`
9. `median_interpurchase_interval_days_365d`
10. `qualifying_purchase_occasions_90d`
11. `qualifying_gross_merchandise_90d`

The list excludes:

- `snapshot_month`
- every `observed_*` lifetime total
- `days_since_first_observed_qualifying_purchase`
- any other expanding-history or calendar field

`snapshot_month` and `first_observed_qualifying_purchase_timestamp` remain as metadata only. The 16 old feature columns are gone from the Parquet.

## B. Fixed-window semantics

`_features_for_history()` builds every predictor from a single filtered list, `window_history = [e for e in history if T − 365d <= e.occasion_timestamp < T]`. Because recency, counts, dates, gross, averages, products and intervals all derive from that list, no purchase before the lower bound and none at or after `T` can contribute.

| Feature | How it is computed |
| --- | --- |
| Recency | Latest event in the window. Eligibility guarantees the window is non-empty, and the code checks this explicitly. |
| 90-day features | `T − 90d <= ts` within the same window, i.e. `[T − 90d, T)` |
| Median interpurchase interval | Distinct in-window purchase dates; null when there are fewer than 2 dates. No imputation, so a modelling protocol must declare how to handle the nulls. |

**Independent recomputation.** I built features from canonical occasions using separate reviewer code: the earliest-line timestamp, canonical gross, and per-occasion quantity and StockCode sets. I compared all 11 features on a deterministic sample of 339 customer-months:

- all 11 snapshot months covered
- 251 rows whose customer's first purchase predates the window, so older history had to be excluded
- 100 rows with an event in the 2 days just outside the 365-day or 90-day lower bound

**Result: 0 mismatches.**

**Drift check.** Training and test medians are now close:

| Feature | Training median | Test median |
| --- | --- | --- |
| Recency (days) | 97.4 | 96.6 |
| Occasions, 365 days | 2 | 2 |
| Gross merchandise, 365 days | 660 | 643 |
| Unique products, 365 days | 36 | 34 |
| Share with null median interval | 36.8% | 38.1% |

The structural drift from M2-003 Finding 1 (for example, days since first purchase at most 547 in training versus 700 in test) is gone.

## C. Cohort invariance (M2-002 vs. M2-004 Parquet)

The two Parquets have the same 51,612 rows when sorted by `(customer_id, decision_time)`. These 15 columns are **identical**:

- `customer_id`, `decision_time`
- `feature_window_start`, `feature_window_end_exclusive`
- `historical_feature_coverage_complete`, `active_in_trailing_365d`
- `outcome_window_end_exclusive`, `outcome_window_mature`, `observed_positive_in_incomplete_window`
- `outcome_label`, `outcome_status`, `outcome_coverage_status`
- `evaluation_partition`, `training_label_available_at_cutoff`
- `snapshot_month`

The strict 365-day rule still holds: there are no December 2010 rows, and the earliest decision is 2011-01-01.

Recomputed from the M2-004 Parquet:

| Quantity | Value |
| --- | --- |
| Eligible snapshots / customers | 51,612 / 5,735 |
| Mature positive / mature negative / partial positive / unknown | 9,665 / 37,654 / 573 / 3,720 |
| Training: snapshots / customers / positives | 25,647 / 4,808 / 4,573 |
| Test: snapshots / customers / positives | 21,672 / 4,999 / 5,092 |
| Customers in both partitions | 4,265 |

All values match the expected table.

## D. Reproducibility and tests

**Hashes.**

| Item | SHA-256 | Agreement |
| --- | --- | --- |
| M2-004 Parquet | `44c580a8…952a8` | Equals manifest `output_sha256` |
| Builder | `58f29d27…fa82b` | Equals manifest `builder_sha256` |
| Source V2 pin | `32569a66…` | Unchanged |
| M2-002 Parquet | `ee6d3f11…af98a0` | Still equals its manifest (not overwritten) |

**Storage.** Both datasets are outside the repository, and no Parquet file is tracked by Git.

**Tests.** The 11 snapshot tests pass, including the new fixed-window boundary and allowlist tests. The boundary tests check:

- inclusion at exactly `T − 365d` and exclusion just before it
- inclusion just before `T` and exclusion at `T`
- window-restricted averages, intervals and recency
- the undefined interval
- `snapshot_month` and lifetime fields excluded from the allowlist

**Regression suite.** The `tests/` suite ran 96 tests: 95 passed and 1 Spark test was skipped (Java unavailable). M2-004 reports this as "96 passed; 1 skipped", but the skipped test is part of the 96. This wording nit is optional to fix.

The `docs/recovery` tests pass when run from their own directory, as before.

## E. Documentation closure

The M2-002 report now states:

- test partition: 21,672 snapshots, 4,999 customers, 5,092 positives
- the snapshot month is the month containing the decision timestamp, and its features cover data through the end of the preceding month
- December 2010 is excluded by owner decision under the strict 365 × 24-hour rule
- the M2-004 amendment converting lifetime predictors to the fixed window

The M2-003 review's findings and conclusions are intact; its section headings and findings table match the review as written.

## Readiness

There are no remaining required corrections. **M2-002 through M2-004 are ready for a scoped local commit** of:

- `src/monthly_customer_snapshots.py`
- `tests/test_monthly_customer_snapshots.py`
- `docs/research/COMMERCIAL_DS_P2_M2_001`–`M2_005`

Customer-level Parquet and manifest files must stay outside Git.

No code, data, tests or Git state were modified by this review.

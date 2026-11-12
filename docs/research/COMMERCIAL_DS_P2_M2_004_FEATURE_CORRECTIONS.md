# M2-004 — Fixed-Window Feature Corrections

## Summary

Implemented the two required M2-003 corrections: all predictive history aggregates now use `[T − 365 days, T)`, and `snapshot_month` is metadata rather than a predictor. The owner-approved strict history-coverage rule remains unchanged, including December 2010 exclusion. Eligibility, labels, maturity and chronological partitions are invariant against the independently reviewed M2-002 artifact.

## Files changed

- `src/monthly_customer_snapshots.py` — fixed-window feature calculation and predictive allowlist.
- `tests/test_monthly_customer_snapshots.py` — exact 365-day boundary, feature aggregation, missing-value and allowlist tests.
- `docs/research/COMMERCIAL_DS_P2_M2_002_MONTHLY_SNAPSHOT_IMPLEMENTATION.md` — corrected feature and month semantics, owner decision, test-partition customer count, and M2-004 amendment.
- This correction report.

The pre-existing M2-001 feasibility report and M2-003 independent review were left unchanged. No Phase 1 code/data or M1 baseline artifacts were changed.

## Feature correction

The M2-002 allowlist had 18 entries, including `snapshot_month`, `days_since_first_observed_qualifying_purchase`, lifetime `observed_*` aggregates, and additional overlapping trailing-365-day copies. Those expanding-history predictors are no longer allowlisted. The corrected 11-feature list is:

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

`_features_for_history()` filters every occasion to the inclusive lower and exclusive upper bounds `[decision_time - 365 days, decision_time)`. Recency uses the most recent event inside that window; eligibility guarantees at least one such event, so recency is defined and cannot reach to an older purchase. Occasion and distinct-date counts remain separate. Gross uses the existing canonical qualifying gross merchandise. Basket averages use only in-window canonical occasions. Median interpurchase interval uses distinct qualifying dates in the same window and is null when fewer than two dates exist; this is undefined rather than zero. The 90-day counts and gross use `[T - 90 days, T)` and are subsets of the 365-day window. No imputation is applied.

`snapshot_month` remains in the output for grouping/reporting, and first-observed timestamp remains diagnostic metadata; neither is in `FEATURE_COLUMNS`. No direct calendar identifier remains in the predictor allowlist. Customer/snapshot timestamps, labels, maturity and partition fields remain output metadata and must be excluded from model predictors by using the allowlist.

## Owner decision and population

The owner approved retaining the exact 365-day observed-history requirement. December 2010 remains excluded because the look-back begins at 00:00 on 1 December 2009 and the verified source begins at 07:45 that day. No approximate source-start exception or sensitivity cohort was introduced. The source hashes and canonical occasion definitions are unchanged.

A snapshot's month refers to the month containing its decision timestamp. Its features therefore use transactions strictly before the first day of that month. For example, the 2011-07 snapshot uses information available through the end of June and excludes transactions at or after 00:00 on 1 July.

## Regeneration and cohort invariance

The corrected Parquet was written to a new external path; the reviewed M2-002 artifact was not overwritten:

- Parquet: `<LOCAL_DATA_DIR>/monthly_customer_snapshots_m2_004.parquet`
- Manifest: `<LOCAL_DATA_DIR>/monthly_customer_snapshots_m2_004.parquet.manifest.json`
- Parquet SHA-256: `44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8`
- Builder SHA-256 in manifest: `58f29d2780f541c591312c8d7773815b28d3d828c4be2adea5994c47c8cfa82b`

The manifest source pins match the verified Phase 1 sources (V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; corrected V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`; taxonomy `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`). The Parquet is readable, its SHA-256 matches the manifest, and the builder hash matches the current implementation.

The corrected output was independently compared row-for-row with the original M2-002 Parquet, sorted by `(customer_id, decision_time)`. All 51,612 snapshot keys match. Decision/feature-window timestamps, eligibility flags, outcome endpoints, labels, maturity, observed-positive status, coverage status, partition assignments and training-label-availability flags each match with zero mismatches. Only predictor values/names and feature allowlisting changed.

| Measure | Corrected result |
| --- | ---: |
| Eligible snapshots / unique customers | 51,612 / 5,735 |
| Mature positives / mature negatives | 9,665 / 37,654 |
| Partial-follow-up observed positives / unknown outcomes | 573 / 3,720 |
| Training snapshots / customers / positives / negatives | 25,647 / 4,808 / 4,573 / 21,074 |
| Training positive prevalence | 17.83% |
| Test snapshots / customers / positives / negatives | 21,672 / 4,999 / 5,092 / 16,580 |
| Test positive prevalence | 23.50% |
| Customers appearing in both partitions | 4,265 |

These counts exactly match the independently verified M2-003 baseline. Mature/partial/unknown labels sum to 51,612. Training and test mature rows sum to 47,319; no mature pre-cutoff label is unavailable at the July 1 cutoff.

Aggregate checks on the regenerated dataset found no 365-day date count greater than occasion count, no 90-day occasion count greater than 365-day count, and no 90-day gross greater than 365-day gross. Recency ranges from 0.161 to 364.624 days. The output allowlist has 11 unique fields and excludes both `snapshot_month` and lifetime/first-observed predictors.

## Tests

Eleven focused monthly snapshot tests pass. New tests verify inclusion at exactly `T − 365 days`, exclusion immediately before it, inclusion immediately before `T`, exclusion at `T`, fixed-window gross and basket averages, fixed-window purchase gaps, recency, undefined interval handling, and exclusion of `snapshot_month`/lifetime fields from `FEATURE_COLUMNS`. Existing tests continue to cover outcome boundaries, maturity, coverage gaps, customer-month uniqueness, repeated customers and as-of label availability.

Full repository regression: **95 passed; 1 skipped (96 tests total)**. The skipped test is the existing Spark test because Java is unavailable. This includes the canonical Phase 1 pipeline regressions and M1 baseline unit tests. The historical Day-21 experiment was not rerun; no model was trained. No customer-level output is in the repository or staged. No commit or push was made.

## Readiness

No material blocker remains. The fixed-window feature allowlist and output provenance are ready for targeted Claude verification. After that verification, M2-002 can proceed to a scoped local commit when authorized.

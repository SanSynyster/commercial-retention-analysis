# M2-002 — Monthly Established-Customer Snapshot Implementation

## Result

Implemented a reproducible monthly customer snapshot with point-in-time features, a fixed 30-day qualifying-purchase outcome, explicit maturity, and a July 1, 2011 as-of chronological split. No predictive model was trained. The completed Day-21 experiment and Phase 1 outputs were not changed.

The original M2-002 customer-level Parquet and manifest are local and outside Git, preserved as the independent-review comparison baseline:

- `monthly_customer_snapshots_m2_002.parquet` — 51,612 eligible customer-month rows.
- `monthly_customer_snapshots_m2_002.parquet.manifest.json` — aggregate accounting, source pins, schema rules, and output SHA-256.

Both are in the verified local UCI source-data directory. The manifest records Parquet SHA-256 `ee6d3f11736283022a28b85e7ecde140c26add0e3828335cb7c352f367af98a0`.

## Definitions and implementation

The population follows the M2-001 Direction A definition: one monthly row for an identifiable customer with at least one canonical qualifying purchase in the complete trailing 365-day interval `[T − 365 days, T)`. This is an established active-base population, not the M1 12-month new-customer acquisition proxy. A customer may recur across months and across train/test.

`T` is 00:00 on the first day of the snapshot month. Features include only canonical occasions with timestamp `< T`. A qualifying occasion timestamp is the earliest valid qualifying line timestamp in the canonical customer × invoice occasion. The outcome interval is `[T, T + 30 days)`: any canonical occasion in the interval is positive; no occasion is negative only if the complete interval is observed. Positive events observed in incomplete windows retain label 1 and are marked immature; no-event incomplete windows remain null/unknown.

Implemented in [monthly_customer_snapshots.py](../../src/monthly_customer_snapshots.py):

- `generate_monthly_anchors()` identifies month-start anchors with complete history.
- `_canonical_events()` derives timestamped qualifying occasions and basket attributes from Phase 1 classified rows and occasion lineage.
- `_features_for_history()` constructs pre-decision features.
- `build_monthly_customer_snapshots()` builds eligible rows, labels, maturity and split membership.
- `snapshot_accounting()` validates key uniqueness, eligibility, label accounting, chronology, and as-of label availability.
- `build_from_source_paths()` loads the verified sources through `load_validated_purchase_input()` and `build_purchase_occasions()`.
- CLI `main()` writes Parquet plus its provenance/accounting manifest outside the repository, refusing to overwrite existing files.

The builder reuses the frozen transaction classification, corrected-V2 validation, canonical customer × invoice occasion, qualifying merchandise and gross-value definitions from `docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py` and `docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py`. It does not alter these Phase 1 definitions. Existing whole-history aggregates in `src/customer_metrics.py` were not reused as snapshot features.

## Source and feature coverage

The validated source spans `2009-12-01 07:45:00` to `2011-12-09 12:50:00` (source-naive timestamps). The pinned SHA-256 values match the recovered source manifest:

| Input | SHA-256 |
| --- | --- |
| V1 workbook | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Corrected V2 CSV | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |
| Taxonomy seed | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |

Canonical reconciliation: 1,044,848 corrected source rows; 788,127 qualifying merchandise lines; 36,594 qualifying customer × invoice occasions; and 5,852 customers represented in qualifying occasions. These match the existing Phase 1/M2-001 canonical counts.

Every history-based predictive aggregate uses the fixed interval `[T − 365 days, T)`: the lower boundary is inclusive and the decision timestamp is exclusive. The allowlisted features are days since the last qualifying occasion in that interval; qualifying occasion/date counts; qualifying gross merchandise; average basket value, quantity and per-occasion product diversity; distinct product count; median interval between distinct qualifying purchase dates; and trailing-90-day occasion count and gross. The 90-day features are a fixed-window subset. No feature uses a purchase before the 365-day lower bound or at/after `T`.

`median_interpurchase_interval_days_365d` is null when fewer than two distinct purchase dates occur in the window. This is an undefined interval, not zero. Eligibility guarantees at least one occasion in the window, so recency and basket averages are defined. Model-specific imputation, if needed, must be learned from training data only. Gross merchandise is not net revenue or profit. SKU diversity is not a product-category taxonomy. Country and return/cancellation features remain excluded because their point-in-time aggregation or attribution is not established by the current contracts.

The corrected source is treated as a continuous observation span from its first to last recorded timestamp; it provides no independent system-uptime calendar. The owner explicitly approved retaining the strict 365 × 24-hour history rule and excluding December 2010: that anchor's look-back begins at 00:00 on December 1, 2009, before the earliest source timestamp at 07:45. No source-start exception or approximate coverage is applied. January 2011 is the first anchor with fully covered exact history. `first_observed_qualifying_purchase_timestamp` remains output metadata only; expanding-history predictors, including days since first observed purchase, are excluded from the feature allowlist.

**Snapshot month semantics:** a snapshot's month refers to the calendar month containing its decision timestamp. Its historical features therefore cover information available through the end of the preceding calendar month. For example, a snapshot dated 1 July 2011 uses historical transactions strictly before 1 July 2011. `snapshot_month` remains reporting metadata and is not a predictive feature.

## Cohort accounting

The 92,124 candidate rows are known-customer/month combinations at observed month-start anchors (a customer must have at least one qualifying occasion before that anchor). They reconcile as follows:

| Disposition | Customer-months |
| --- | ---: |
| Eligible: complete trailing-365-day history and at least one qualifying purchase in it | 51,612 |
| Excluded: incomplete trailing-history coverage | 32,288 |
| Excluded: no qualifying purchase in complete trailing 365 days | 8,224 |
| **Candidate total** | **92,124** |

Eligibility categories are mutually exclusive and exhaustive. Eligible rows have one unique `(customer_id, decision_time)` key. There are 5,735 unique customers across eligible snapshots.

| Label status | Snapshots |
| --- | ---: |
| Mature positive (label 1) | 9,665 |
| Mature negative (label 0) | 37,654 |
| **Fully mature** | **47,319** |
| Observed positive, incomplete horizon (label 1; not in mature evaluation) | 573 |
| Unknown, incomplete horizon (null; never negative) | 3,720 |
| **Eligible total** | **51,612** |

Mature prevalence is 20.43%. Counts reconcile to `9,665 + 37,654 + 573 + 3,720 = 51,612`.

### Monthly distribution

| Snapshot month | Eligible | Mature positive | Mature negative | Partial positive | Unknown | Train | Test |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2011-01 | 4,205 | 634 | 3,571 | 0 | 0 | 4,205 | 0 |
| 2011-02 | 4,221 | 676 | 3,545 | 0 | 0 | 4,221 | 0 |
| 2011-03 | 4,260 | 755 | 3,505 | 0 | 0 | 4,260 | 0 |
| 2011-04 | 4,318 | 739 | 3,579 | 0 | 0 | 4,318 | 0 |
| 2011-05 | 4,319 | 901 | 3,418 | 0 | 0 | 4,319 | 0 |
| 2011-06 | 4,324 | 868 | 3,456 | 0 | 0 | 4,324 | 0 |
| 2011-07 | 4,314 | 809 | 3,505 | 0 | 0 | 0 | 4,314 |
| 2011-08 | 4,326 | 795 | 3,531 | 0 | 0 | 0 | 4,326 |
| 2011-09 | 4,324 | 1,043 | 3,281 | 0 | 0 | 0 | 4,324 |
| 2011-10 | 4,364 | 1,049 | 3,315 | 0 | 0 | 0 | 4,364 |
| 2011-11 | 4,344 | 1,396 | 2,948 | 0 | 0 | 0 | 4,344 |
| 2011-12 | 4,293 | 0 | 0 | 573 | 3,720 | 0 | 0 |

December is a partial terminal snapshot: 573 observed positives and 3,720 unknown outcomes. It contributes no negatives and is excluded from train/test evaluation.

## Chronological split and maturity

The training cutoff is `2011-07-01 00:00:00`. Training includes mature snapshots whose decision is before the cutoff and whose full 30-day outcome endpoint is no later than the cutoff. Consequently, the June 1 outcome ending exactly July 1 is available. Testing includes mature snapshots with decision timestamp on/after the cutoff. May/June label-unavailable rows from M2-001’s 90-day analysis become available with this 30-day outcome; there are zero mature pre-cutoff rows left unavailable at this cutoff.

| Partition | Months | Rows | Unique customers | Positive | Negative | Prevalence |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Training, label available by cutoff | Jan–Jun 2011 | 25,647 | 4,808 | 4,573 | 21,074 | 17.83% |
| Mature chronological test | Jul–Nov 2011 | 21,672 | 4,999 | 5,092 | 16,580 | 23.50% |
| Unique customers in both | — | — | **4,265** | — | — | — |

The test decision timestamps are later than the training decisions; test windows are fully mature through November 2011. No training label uses information after the July 1 cutoff. The split does not require a separate arbitrary purge. Monthly 30-day outcome windows are not uniformly disjoint: February anchors overlap the following month’s window by two days, while anchors after 31-day months leave a one-day gap. Repeated snapshots and overlapping outcomes must be accounted for in later clustered uncertainty estimates.

### Reconciliation with M2-001

M2-001 used a 90-day outcome, reported 42,850 mature rows across December 2010–September 2011, 21,243 labels available for training, and 12,964 mature July–September test rows. This implementation uses the approved shorter 30-day horizon, so October–November become mature, June labels are available at the July cutoff, and the test includes five months. It also enforces exact timestamp coverage for the full 365-day history; December 2010’s 4,239 candidates are excluded because the required look-back begins before the first source timestamp. The owner has confirmed retaining this strict exclusion; no December sensitivity analysis is part of M2-004. The final mature set is 47,319 (9,665 positive / 37,654 negative), training 25,647, and test 21,672. Thus the difference is explained by the approved horizon, strict source-boundary coverage, and the resulting split—not by a change to canonical purchase definitions.

Following independent M2-003 review, lifetime and expanding-history aggregate predictors were converted to the fixed 365-day feature window. First-observed purchase timing remains metadata only, and `snapshot_month` was removed from the feature allowlist. Eligibility, labels, maturity, and partitions are unchanged.

Training prevalence (17.83%) and test prevalence (23.50%) differ by 5.66 percentage points. There are five test months but only one later source season, and 4,265 customers occur in both partitions. This supports an initial baseline research exercise, not a claim of broad seasonal generalisation. Later uncertainty should cluster at customer level; rows are not independent.

## Validation and reproduction

The M2-002 baseline had nine focused snapshot tests and the full repository suite passed 94 tests (one existing Spark test skipped because Java was unavailable). M2-004 adds fixed-window boundary and feature-allowlist tests; its latest test result is recorded in `COMMERCIAL_DS_P2_M2_004_FEATURE_CORRECTIONS.md`.

Reproduce from the repository root using the verified source files and a new output path outside Git:

```sh
DATA_DIR=/path/to/uci_online_retail_ii
.venv/bin/python src/monthly_customer_snapshots.py \
  --v1-xlsx "$DATA_DIR/Online Retail.xlsx" \
  --v2-csv "$DATA_DIR/online_retail_II_pandas_csv.csv" \
  --output "$DATA_DIR/monthly_customer_snapshots_m2_004.parquet" \
  --train-cutoff '2011-07-01 00:00:00'
```

The CLI checks the frozen canonical source through the existing Phase 1 loader, writes no data into the repository, and refuses to overwrite an existing Parquet file or manifest. The corrected output is written to the new `monthly_customer_snapshots_m2_004.parquet` path; the reviewed M2-002 artifact remains unchanged.

## Limitations and next step

- This is an observational purchase-propensity target, not a CRM treatment-effect or incremental-uplift estimate.
- Customer histories are left-censored before December 2009; observed-first-purchase time is not true tenure.
- The test is short and later-season; prevalence drift and customer reuse constrain generalisation.
- Unattributed returns/cancellations, country, product categories, and full-history metrics are intentionally absent.
- The monthly 30-day targets can overlap; subsequent uncertainty calculations must cluster by customer and respect month-level temporal variation.

**Recommended next modelling step:** predeclare a small, regularised RFM baseline, fit preprocessing on training snapshots only, evaluate once on the mature July–November test rows, and report customer-clustered uncertainty plus month-specific results. Do not interpret propensity ranking as causal campaign value.

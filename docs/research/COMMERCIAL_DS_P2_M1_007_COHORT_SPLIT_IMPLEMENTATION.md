# M1-007 — Day-21 Cohort and Chronological Split

## Implementation summary

Updated `src/day21_cohort.py` to apply the approved 12-month qualifying-purchase look-back and the July 1, 2011 as-of split. The cohort retains all identifiable customers for accounting, with distinct `acquisition_eligible`, `eligible` (Day-21), and `primary_eligible` fields. Insufficient-history customers carry `acquisition_exclusion_reason = insufficient_12_month_qualifying_history`; this does not overwrite their Day-21 exclusion reason.

The look-back threshold is computed from the actual corrected source start timestamp, `2009-12-01 07:45:00`, plus 12 calendar months: `2010-12-01 07:45:00`. No earlier non-qualifying-activity exclusion was added. Existing exact timestamp, same-calendar-day repeat, Day-21 and Day-111 rules are unchanged. First-purchase month was removed from the output feature set; weekday remains available as a calendar feature and should be handled categorically in a later model.

`apply_approved_temporal_split()` assigns training only when the Day-21 decision is before the cutoff and the complete outcome deadline is at or before the cutoff. It assigns test only to decisions on/after the cutoff with complete follow-up at the source boundary. It emits `training_label_available_at_cutoff` and explicit dispositions for pre-cutoff labels not yet available, immature post-cutoff rows, and rows outside the primary population. Partial positives are not used as fixed-horizon training labels.

The referenced M1-004 assessment and M1-006 report were read. M1-006 records the independent review's acquisition-look-back blocker and documents why the earlier January split had no mature training labels. A separate M1-004 Claude review file was not present alongside those artifacts; the blocker was addressed as specified in M1-006. The relevant source contract/review history is in `docs/recovery/COMMERCIAL_DS_001_DECISION_LOG.md` and `docs/recovery/COMMERCIAL_DS_003_STAGE_B1_INDEPENDENT_REVIEW.md`; the latter's any-category prior-activity exclusion remained pending and is not applied under the current owner decision.

## Cohort and label reconciliation

The rebuilt cohort contains 5,852 identifiable customers and 5,852 valid first qualifying timestamps. Counts are mutually exclusive as shown:

| Cohort accounting | Customers |
| --- | ---: |
| Insufficient 12-month qualifying history | 4,239 |
| Sufficient 12-month history | 1,613 |
| └ Day-21 decision unobserved | 94 |
| └ Second qualifying purchase by Day 21 | 195 |
| └ Day-21 eligible primary population | **1,324** |

`5,852 = 4,239 + 94 + 195 + 1,324`.

| Outcome among 1,324 primary-eligible customers | Customers |
| --- | ---: |
| Mature positive | 312 |
| Mature negative | 526 |
| **Mature total** | **838** |
| Observed positive, incomplete horizon | 168 |
| Unknown / immature, no observed positive | 318 |
| **Incomplete-horizon total** | **486** |

`1,324 = 838 + 168 + 318`. Mature prevalence is `312 / 838 = 37.23%`. Unknown outcomes remain null and are not counted as negatives.

## July 1 split and the 326 mature-label reconciliation

| Disposition | Count | Positive | Negative | Meaning |
| --- | ---: | ---: | ---: | --- |
| Training labels available at cutoff | **304** | **90** | **214** | Decision before cutoff; complete 90-day deadline at/before July 1 |
| Pre-cutoff labels unavailable at cutoff | **326** | 125* | 201* | Decisions before July 1, but deadline after cutoff; excluded from training and test |
| Mature later-decision test | **208** | **97** | **111** | Decision at/after July 1; complete source follow-up |
| Later-decision immature | **486** | 168* | 0* | Decision at/after cutoff, incomplete horizon; excluded from fixed-horizon test |

`838 mature = 304 available training + 326 not yet available at cutoff + 208 test`.

`*` For the 326 and 486 rows, counts describe eventual cohort outcomes where observed, solely for reconciliation. The 326 labels were **not available** on July 1 and are not selected for training. The 486 later decisions have incomplete horizons; 168 have observed partial positives and 318 remain unknown. The split manifest separately records the 326 as `pre_cutoff_label_not_available` and 486 as `test_immature`.

Training decisions are strictly before `2011-07-01 00:00:00`; test decisions are at or after it. Every training deadline is at/before the cutoff, and every test row has a complete horizon through the source boundary (`2011-12-09 12:50:00`). These constraints were checked against the generated cohort. No model was trained.

## Tests and validation

Focused tests were added for the exact 12-month threshold and explicit insufficient-history reason, plus exclusion of a label that matures after the as-of cutoff. Existing timestamp boundary, maturity, feature leakage, accounting and split-order tests remain in place. The first-purchase-month feature absence is asserted.

Executed:

```sh
.venv/bin/python -m unittest tests.test_day21_cohort tests.test_pipeline \
  docs.recovery.test_COMMERCIAL_DS_003_STAGE_B2B3 \
  docs.recovery.test_COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS \
  docs.recovery.test_COMMERCIAL_DS_007C_VALUE_SEGMENTS -v
```

Result: **72 tests run; 71 passed and 1 skipped** (the Spark test requires Java). Source regeneration used the existing corrected-V2 loader, source validation, and canonical purchase-occasion builder. The resulting 5,852-row cohort and manifests are outside the repository; no Phase 1 source code or outputs were changed.

## Provenance and reproducibility

External cohort: `../source_data/uci_online_retail_ii/day21_customer_cohort_m1_007.parquet` (319,468 bytes; SHA-256 `0f2217598c5e58c83946edcb4f6a5eeb652b987d9e46f8b7779616c26342810e`).

Adjacent `.manifest.json` records the verified input hashes and definitions:

- V1 SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`
- Corrected V2 CSV SHA-256: `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`
- Taxonomy seed SHA-256: `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`

The adjacent `.split.manifest.json` records the cohort hash, cutoff, split rule and disposition counts. Regenerate from the configured external source directory with:

```sh
DATA_DIR=/path/to/verified/uci_online_retail_ii
.venv/bin/python -m src.day21_cohort \
  --v1-xlsx "$DATA_DIR/Online Retail.xlsx" \
  --v2-csv "$DATA_DIR/online_retail_II_pandas_csv.csv" \
  --output "$DATA_DIR/day21_customer_cohort_m1_007.parquet"
```

The builder refuses to write inside the repository or overwrite existing outputs.

## Remaining blockers to initial baseline modelling

No cohort or split blocker remains for a small, predeclared baseline. The training set has only 304 labels and the test set 208 labels over a short calendar period, so do not tune on this test or make broad generalisation claims. The 12-month proxy remains left-censored and must not be described as verified first-ever acquisition. Initial modelling should use the explicit `train` partition only, preserve the `test` partition for one evaluation, and leave all other dispositions out. The owner has already approved the acquisition rule, cutoff and no-extra-exclusion policy; no additional decision is required for this implementation.

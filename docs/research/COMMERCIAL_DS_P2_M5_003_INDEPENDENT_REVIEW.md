# M5-003R — Independent Scientific Review: Purchase Propensity Dashboard

## Verdict

**PASS WITH CONDITIONS.**

- **Numbers:** every number shown on the Purchase Propensity page matches the frozen M1-009 report (with the M1-010 erratum), the M2-008 report and run manifest, and the M2-012 report and aggregate. M2-013 independently reproduced the M2-012 values.
- **Bundle:** it rebuilds byte-for-byte equivalent from hash-verified sources. A tampered bundle with a recomputed embedded hash is rejected. The bundle contains no customer-level content.
- **App:** it runs from a clean checkout without private data.

Three small presentation corrections are required. None changes the data, the bundle or a research report.

| ID | Severity | Topic |
| --- | --- | --- |
| R1 | Medium | Baseline and adjusted calibration intercept/slope are shown side by side as if they were a before/after pair, but they cover different evaluation windows. |
| R2 | Low | The M1/M2 non-comparability warning is only inside collapsed expanders, while two visible metrics share the label "Model C ROC-AUC". |
| R3 | Low | The Brier improvement is shown with Streamlit's default delta colour, so the improvement appears as a red down arrow. |

## Scope and baseline

- **Repository:** HEAD `d0aeb9ac937adefbb9ac2d3b8e0de4e1b28b759b`.
- **Uncommitted M5-003 changes:**
  - Four modified files: `app/README.md`, `app/streamlit_app.py`, `app/views/placeholders.py`, `tests/test_dashboard_app.py`.
  - Six new files: `app/views/purchase_propensity.py`, `app_data/propensity_summary_v1.json`, `src/propensity_summary_bundle.py`, two test modules and the M5-003 note.
- **Sources read:**
  - `COMMERCIAL_DS_P2_M5_003_PROPENSITY_DASHBOARD.md`.
  - M1-009 results and protocol, and the M1-010 erratum section.
  - M2-008 results, and the M2-007 protocol hash.
  - M2-012 results and the M2-013 review.
  - The external `monthly_purchase_baselines_m2_008_run_manifest.json` and `m2_012_sequential_calibration_aggregate.json` under `retention_analysis/source_data/uci_online_retail_ii/`.
- **No changes:** no implementation, data or report was modified. Probe scripts, clean copies and the venv were kept in a session scratch directory outside the repository.

## A. Scientific correctness

| # | Item | Dashboard / bundle | Frozen source | Result |
| --- | --- | --- | --- | --- |
| 1 | M1 Model C ROC-AUC and CI | 0.519; [0.441, 0.596] (bundle 0.5189, [0.4410, 0.5963]); 2,000 resamples; seed 20261112 | M1-009: 0.5189, [0.4410, 0.5963], 2,000/2,000 valid, seed `20261112` | ✔ |
| 2 | M1 criterion | "Not met"; warning that the interval spans chance | M1-009/M1-010: lower bound 0.4410 ≤ 0.50, not met; inconclusive | ✔ |
| 1a | M1 supporting values | Training 304 (90+); test 208 (97+); B AUC 0.5439; Brier 0.2779 / 0.2761 / 0.2743; C calibration 0.172 / 0.376 (SE 0.45 / 0.53); B calibration 0.112 / 0.295; prior M1-008 prevalence look disclosed | M1-009 tables and M1-010 erratum | ✔ |
| 3 | M2 A/B/C metrics | AUC 0.500 / 0.760 / 0.766; AP 0.235 / 0.548 / 0.566; Brier 0.1830 / 0.1497 / 0.1474 | M2-008: 0.50000 / 0.75995 / 0.76599; 0.23496 / 0.54830 / 0.56595; 0.18296 / 0.14968 / 0.14744 | ✔ |
| 3a | M2 C clustered CI | [0.756, 0.775]; 2,000 resamples, 2,000 valid, 0 omitted | [0.75646, 0.77490]; 2,000/2,000; seed 20261112 | ✔ |
| 4 | M2 samples and prevalence | Training 25,647 snapshots / 4,808 customers / 17.83%; test 21,672 / 4,999 / 23.50%; overlap 4,265 | M2-008 partition table | ✔ |
| 5 | Top-decile precision and lift | A 23.5% / 1.00× (labelled random expectation); B 67.3% / 2.87×; C 69.3% / 2.95× | M2-008 capacity table: 0.235 / 1.00; 0.673 / 2.87; 0.693 / 2.95 | ✔ |
| 6 | Monthly results and order | 2011-07 → 2011-11 in chronological order; snapshots, positives, prevalence and AUC B/C per month | M2-008 monthly table (e.g. Nov 4,344, 32.14%, B 0.745, C 0.751) | ✔ |
| 7 | Baseline C calibration | 0.411 / 0.973; underprediction 17.69% vs 23.50% in limitations | M2-008: 0.4114 / 0.9730, "stationary optimum after optimizer warning" | ✔ values; see R1 |
| 8 | Sequential calibration | Pools 8,640 / 8,640 / 17,328; δ +0.0833 / +0.0833 / +0.3029; pooled Brier 0.1682 → 0.1637; diff −0.00446, CI [−0.00553, −0.00340]; mean prediction 17.8% → 19.7% vs 26.8%; gap 9.0 → 7.1 points; adjusted pooled 0.435 / 0.949 | M2-012 tables; M2-013 independent pool rebuild | ✔ values; see R1 and R3 |

**Separation and caveats.**

- M1 and M2 have separate `st.header` sections, each with its own question, decision, outcome and evaluation unit. No table or chart combines their metrics.
- Model letters are task-specific (M1 B = gross only; M2 B = RFM).
- The following are all stated on the page:
  - **Repeated M2 customers:** the evaluation unit caption, the 4,265 overlap and clustered uncertainty.
  - **Temporal drift:** training versus test prevalence, a monthly prevalence chart, and the November rise to 32.14%.
  - **Previously examined holdout.**
  - **Exploratory calibration status:** "not prospective validation", "conditional on the same, previously examined holdout", and that within-month ranking is unchanged.
- Calibration is never described as prospectively validated.

## B. Aggregate bundle

| Check | Result |
| --- | --- |
| Rebuild | With `LOCAL_DATA_DIR` set, `build_bundle` reproduces the tracked `m1`, `m2`, `m2_calibration` and `provenance` exactly, including `builder_sha256` `a3068ab2…`. Content hash equal; the rebuild test passes. |
| Source hashes | All seven `source_sha256` values match the current tracked reports and protocols and the two external aggregates. All six `upstream_artifact_sha256` values (dataset, dataset manifest, snapshot builder, protocol, models, predictions) match the files on disk and the hashes in the M2-008 run manifest. |
| Independent content pin | `EXPECTED_CONTENT_SHA256 = a4fcc6d6…5535562` is checked after the embedded hash. Setting M2 C AUC to 0.9 and recomputing the embedded hash is **rejected** ("differs from the independently approved application bundle"). So is deleting the M1 limitations. |
| Field and type validation | Exact key sets are enforced at every level, with finite-number checks and count/prevalence reconciliation. A fuzz pass replaced every leaf with None, a string, 0, −1, [], {} and True: **no uncaught exception**, and every real change was rejected except two trivial cases. `schema_version: True` passes because `True == 1`, and the free-text `provenance.builder` path is unchecked. `builder_sha256` is format-checked but not pinned, which is reasonable because the builder can change without changing content. |
| Customer-level content | No customer IDs, prediction rows, feature matrices, coefficients or individual outcomes. Monthly and pool rows are aggregates of 4,300 or more snapshots. The file is 16 KB on disk (the note says 14.2 KB). Model coefficients and month-specific score distributions are left out. |
| Granularity | Proportionate. Only fields used on the page plus their supporting counts are included. Monthly July/August calibration rows repeat the raw values (unadjusted warm-up months), and the page plots only September–November. |

No bundle finding requires correction.

## C. Dashboard behaviour

AppTest checks were run in a clean copy (HEAD archive plus the M5-003 changes, **no `data/` directory**, `LOCAL_DATA_DIR` unset) using a fresh Python 3.11 venv installed from `requirements-app.txt`.

| Check | Result |
| --- | --- |
| Four-page navigation | Each page rendered through the real `st.navigation` routing: Customer Overview (4 metrics), Purchase Propensity (14 metrics, 3 headers), and Targeting Explorer and Experiment Feasibility (placeholders). No exceptions or errors. AppTest's `switch_page` cannot target callable pages, so each page was made the default in turn using a probe copy of `streamlit_app.py`. |
| M1/M2 separation | Separate headers, questions and captions, with dividers between them. See R2 for visibility of the non-comparability statement. |
| Metric labels | The M2 table is correctly labelled. Model A's 10% precision and lift are labelled as the random-selection expectation. M1 average precision and capacity metrics are absent and explained. |
| CIs and percentages | M1 [0.441, 0.596] and M2 [0.756, 0.775] round correctly; 69.3%, 2.95× and 26.8% are correct. The risk gap is shown as "9.0% to 7.1%"; it is a percentage-point gap (optional O1). |
| Monthly labels | The x-axis title is "2011 test decision month", with labels 2011-07 … 2011-11. Calibration charts use "Target month". This is unambiguous. |
| Calibration view toggle | The selectbox switch to "Mean prediction vs prevalence" renders without error. |
| Calibration pairing | **R1**, described below. |
| Brier delta | **R3**, described below. |
| Missing or malformed bundle | The test suite covers a missing file, empty `provenance` and bad JSON: each gives one `st.error` and no metrics. Fuzzing found no path to an uncaught exception. |
| Customer Overview | Unchanged and functional, including the M5-002R corrections already present in `customer_overview_bundle.py` and the README. Its tests pass. |
| Runtime file access | A Python audit hook during a full four-page run showed the only data files opened were `app_data/customer_overview_v1.json` and `app_data/propensity_summary_v1.json`. No `source_data` or Parquet file was opened. |
| Live server | `streamlit run` in the clean copy: health `ok`, `/purchase-propensity` HTTP 200, no errors in the server log. |

### R1 — Calibration diagnostics from different windows shown as a pair (Medium)

**Evidence.** In `_calibration_section`, two adjacent `st.metric` tiles show:

- "Baseline C calibration (Jul–Nov) 0.411 / 0.973"
- "Sequential adjusted pooled diagnostic (Sep–Nov) 0.435 / 0.949"

M2-012 reports the comparable raw September–November pooled diagnostic as **unavailable**, because the stability checks rejected it. The bundle already records this as `pooled.raw.calibration.status = "not_estimable_or_unstable"`.

**Impact.** Readers will see a before/after pair and conclude that the adjustment slightly worsened the calibration intercept (0.411 → 0.435) and slope (0.973 → 0.949). The two values cover different snapshot sets (21,672 versus 13,032), so the comparison is not valid. This misstates item A7/A8 evidence, even though each number is individually correct.

**Smallest correction.** Add one caption under the two tiles, for example: "Not a before/after pair: different evaluation windows; the raw Sep–Nov pooled diagnostic was not estimable." Optionally show the raw Sep–Nov status from the bundle. Alternatively, remove the Jul–Nov tile from this section, since it already appears in M2 context. No bundle change is needed.

### R2 — Non-comparability guard is hidden; duplicate metric labels (Low)

**Evidence.** Both visible headline tiles are labelled "Model C ROC-AUC" (0.519 in M1, 0.766 in M2). The sentences "Its AUC must not be compared … head-to-head with M2" and "Their AUCs are not a controlled head-to-head comparison" appear only inside the collapsed "M1 population and evaluation" and "Scientific interpretation and sources" expanders.

**Impact.** The page does not combine the results. However, a reader scanning the tiles sees two identically labelled AUCs without the guard. M5-001 required that M1 and M2 AUCs never be presented as a league table.

**Smallest correction.**

1. Label the tiles "M1 Model C ROC-AUC" and "M2 Model C ROC-AUC".
2. Move the one-sentence non-comparability statement out of the expander, for example into the evidence caption under the page title.

### R3 — Brier improvement shown with default delta colour (Low)

**Evidence.** `cols[1].metric("Sep–Nov adjusted Brier", …, delta="-0.0045")` uses Streamlit's default `delta_color="normal"`, which renders a negative delta as a red down arrow.

**Impact.** The lower Brier score is the main calibration improvement, but the styling signals a deterioration.

**Smallest correction.** Pass `delta_color="inverse"`.

## D. Reproducibility and tests

| Run | Result |
| --- | --- |
| Focused M5 suites (4 modules), dev venv | **29 tests OK, 1 skip** (propensity rebuild, `LOCAL_DATA_DIR` unset) |
| Propensity bundle tests with `LOCAL_DATA_DIR` set | **6/6 OK**, including the external-aggregate rebuild equality test |
| Full `tests/` discovery | **156 tests OK, 2 skips**: the existing Spark/Java skip plus the propensity rebuild without `LOCAL_DATA_DIR`. The note's "1 skip" corresponds to a run with `LOCAL_DATA_DIR` set. |
| Corrected-V2 007 recovery tests | **15 OK** |
| Clean copy (no `data/`, no `LOCAL_DATA_DIR`), fresh venv from `requirements-app.txt` | **29 OK, 2 expected private-input rebuild skips**. A full four-page AppTest render shows only the two tracked bundles opened. The live server is healthy. |

**Test content.** The tests check scientific invariants, not just rendering:

- Approved M1/M2 values.
- The M1 criterion is false.
- Task definitions.
- September–November calibration pools.
- Rejection of a rehashed tamper.
- No identifiers.
- Controlled errors for missing or malformed bundles.
- Page headers and metric values.

The tests do not cover R1–R3; these are presentation checks to confirm by inspection after the correction.

## E. Findings summary

### Required for closure

| ID | Severity | File | Correction |
| --- | --- | --- | --- |
| R1 | Medium | `app/views/purchase_propensity.py` (`_calibration_section`) | Caption the intercept/slope tiles as non-comparable windows and state that the raw Sep–Nov pooled diagnostic was not estimable, or drop the Jul–Nov tile from this pair. |
| R2 | Low | `app/views/purchase_propensity.py` (`_m1_section`, `_m2_section`, `render`) | Prefix the tile labels with M1/M2, and show the one-line non-comparability statement outside expanders. |
| R3 | Low | `app/views/purchase_propensity.py` (`_calibration_section`) | `delta_color="inverse"` on the adjusted-Brier tile. |

Optionally, add an AppTest assertion for the R2 labels.

### Optional (not blocking)

- **O1:** Show the risk gap in percentage points ("9.0 pp → 7.1 pp"), matching M2-012.
- **O2:** Order the calibration pool table columns so that Target month comes first. JSON key sorting currently puts it last.
- **O3:** Reject `bool` for `schema_version` (`True == 1` currently passes).
- **O4:** In the M5-003 note, give the full-suite skip count with and without `LOCAL_DATA_DIR`, and correct the bundle size (16 KB on disk).
- **O5:** Optionally state the M1 split date (1 July 2011) beside the M1 test-size tile.

## Commit readiness

After R1–R3, **M5-003 is ready for a scoped local commit**. The commit should contain:

- The four modified files.
- The six new files.
- This review.

The corrections touch only the view module, so the bundle and its pinned hash stay the same. Re-run the four focused test modules after editing.

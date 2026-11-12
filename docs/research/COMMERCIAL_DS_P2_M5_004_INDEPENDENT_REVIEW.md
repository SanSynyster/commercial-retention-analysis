# M5-004R — Independent Review: CRM Targeting Explorer

## Verdict

**PASS WITH CONDITIONS.**

The CRM Targeting Explorer faithfully reproduces the frozen M3-002 results, as independently verified in M3-003.

- **Accuracy:** every displayed count, rate, lift, overlap, repeated-selection aggregate, paired difference and interval matches the frozen aggregate and reports at 5%, 10% and 20%.
- **Bundle:** it rebuilds identically from the hash-verified M3 aggregate. A recomputed embedded hash cannot bypass the independent pin. No customer-level content is present.
- **Wording:** the page does not claim equivalence or causal effect, and does not fabricate standalone intervals.

Two bounded corrections are required:

| ID | Severity | Topic |
| --- | --- | --- |
| R1 | Low–Medium | Malformed bundle sections cause uncaught `TypeError`/`AttributeError`/`KeyError` (a page traceback) instead of a controlled error. Provenance fields are not validated. |
| R2 | Low–Medium | The tie-sensitivity disclosure is weaker than M3-003 Finding 1 requires: the tie table is unlabelled, and the page does not say that tie-rule shifts are the same size as the Model C − frequency differences. |

Neither correction changes the bundle data or its pinned content hash.

## Scope and baseline

- **Repository:** HEAD `48a330ada72b845caa9aa0a1492f96adb7a7dce5`.
- **Uncommitted M5-004 changes:**
  - Modified: `app/README.md`, `app/views/placeholders.py` (now contains the Targeting Explorer page), `tests/test_dashboard_app.py`.
  - New: `app_data/targeting_v1.json`, `src/targeting_bundle.py`, `src/targeting_metrics.py`, `tests/test_targeting_bundle.py`, the M5-004 note.
- **Sources read:**
  - `COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md`.
  - `COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md`.
  - The external final M3 aggregate and manifest in `source_data/uci_online_retail_ii/m3_002_targeting_outputs_final/`.
- **External hashes:**
  - Aggregate `5e9558f7…b509d`, matching the report.
  - Manifest `7422a915…358fe`, matching the report.
- **No changes:** no implementation, data or report was modified. Probe scripts and clean copies were kept in a session scratch directory.

## A. Scientific accuracy

### Pooled policy results (bundle = M3-002 = M3-003)

The holdout is 21,672 mature customer-month snapshots, 5,092 positives (23.50%) and 4,999 customers, July–November 2011.

- **Selected counts:** the sums of the monthly ceilings: 1,087, 2,170 and 4,336.
- **Precision denominator:** selected snapshots.
- **Capture denominator:** all positive snapshots (5,092).
- **Lift denominator:** pooled prevalence.

| Capacity | Policy | Selected | Precision | Capture | Lift |
| --- | --- | ---: | ---: | ---: | ---: |
| 5% | Model C | 1,087 | 82.24% | 17.56% | 3.50× |
| | RFM | 1,087 | 78.75% | 16.81% | 3.35× |
| | Frequency | 1,087 | 80.77% | 17.24% | 3.44× |
| | Random expectation | 1,087 | 23.50% | 5.02% | 1.00× |
| 10% | Model C | 2,170 | 69.35% | 29.56% | 2.95× |
| | RFM | 2,170 | 67.24% | 28.65% | 2.86× |
| | Frequency | 2,170 | 68.80% | 29.32% | 2.93× |
| | Random expectation | 2,170 | 23.50% | 10.01% | 1.00× |
| 20% | Model C | 4,336 | 54.89% | 46.74% | 2.34× |
| | RFM | 4,336 | 53.57% | 45.62% | 2.28× |
| | Frequency | 4,336 | 54.20% | 46.15% | 2.31× |
| | Random expectation | 4,336 | 23.50% | 20.01% | 1.00× |

All 48 values match. Rendered page tables were compared programmatically with the bundle at each capacity, with no mismatches.

**Uncertainty.** The frozen aggregate contains no standalone policy intervals. The bundle stores `null`, the page shows none, and a caption states they were unavailable. A bundle with a fabricated policy interval is rejected by the pin.

### Paired Model C differences (percentage points, 95% paired customer-cluster percentile interval)

| Capacity | C − RFM precision / capture | C − Frequency precision / capture | C − Random precision / capture |
| --- | --- | --- | --- |
| 5% | +3.50 [+1.67, +5.44] / +0.75 [+0.36, +1.17] | +1.47 [−0.09, +3.21] / +0.31 [−0.02, +0.68] | +58.75 [+55.83, +61.61] / +12.54 [+11.89, +13.22] |
| 10% | +2.12 [+0.79, +3.26] / +0.90 [+0.34, +1.37] | +0.55 [−0.50, +2.17] / +0.24 [−0.21, +0.91] | +45.86 [+42.69, +48.79] / +19.54 [+18.37, +20.65] |
| 20% | +1.31 [+0.51, +1.80] / +1.12 [+0.43, +1.53] | +0.69 [−0.28, +1.26] / +0.59 [−0.23, +1.08] | +31.39 [+29.41, +32.97] / +26.73 [+25.28, +27.90] |

- **Intervals:** all 18 intervals are copied unchanged from `paired_customer_cluster_bootstrap.difference_intervals`. They match the M3-002 table and M3-003's independent re-implementation (2,000/2,000 valid replicates, seed 20261112).
- **Point differences:** derived as pooled Model C minus pooled alternative, which is exactly how M3-002 reports them. The source aggregate stores no separate point difference.
- **Non-significance:** not presented as equivalence. The caption reads: "Intervals crossing zero mean this analysis does not distinguish a difference, not that policies are equivalent". The intervals are labelled "exploratory, not confirmatory" and conditional on the frozen holdout and tie rule. The warning describes the frequency advantage as "small, inconclusive differences".

## B. Policy overlap, tie sensitivity and repeated selection

| Check | Result |
| --- | --- |
| Model C/frequency overlap | 86.9% / 85.9% / 87.2% of Model C selections; Jaccard 0.769 / 0.754 / 0.773. Matches M3-002 and M3-003. |
| Model C/RFM overlap | 88.7% / 87.9% / 90.5%; Jaccard 0.797 / 0.784 / 0.827. Matches. |
| Frozen tie rule | Score descending, then customer key ascending, outcome-independent. Stated on the page as "frozen retrospective evaluation used ascending customer-key tie-breaking". |
| Alternative tie rules (frequency pooled precision) | Key ascending 80.77 / 68.80 / 54.20; random expectation 81.02 / 68.58 / 53.89; key descending 81.23 / 68.48 / 53.57; SHA-256(key, month) 81.14 / 68.43 / 54.24. Matches M3-003 Finding 1 and the M3-002 disclosure table. |
| Primary result unchanged | Yes. The policy table and pairwise differences use the frozen key-ascending selections. Alternatives appear only in the separate tie table, and the frozen column equals the frozen frequency precision at every capacity. The hash-tie-break is described only as a prospective option. |
| Repeated selection | Model C: 292 / 598 / 1,205 distinct customers and 252 / 498 / 1,008 selected in multiple months. Frequency: 268 / 540 / 1,085 and 241 / 481 / 967. Maximum 5 months. Matches the frozen aggregate and the report. |
| Selection vs contact | The source field `total_customer_month_contact_events` is renamed to "customer-month selection events". The caption reads "Repeated selection describes retrospective list membership, not repeated actual CRM contact… would need an approved contact-frequency and suppression policy." |

### R2 — Tie-sensitivity disclosure is incomplete (Low–Medium)

**Evidence.**

- The tie table has four rule columns and no row or caption saying the values are **frequency-rule pooled precision**, or that Model C is unaffected.
- The prose says only that tie-breaking "moves some performance estimates".
- M3-003 Finding 1, carried into the M3-002 report, requires the following:
  - About 17% of frequency selections at 10% come from the tied boundary pool.
  - Tie-rule shifts of up to about 0.5–0.7 pp are the same size as the Model C − frequency differences (+1.47, +0.55, +0.69 pp).
  - Those point differences, and their sign in individual months, should therefore not be read as meaningful.

The dashboard shows these signed differences prominently in the pairwise table.

**Impact.** A reader can treat "+0.55 pp" as a stable Model C advantage, and cannot tell what the tie numbers measure. This understates the reviewed disclosure. It does not alter any value.

**Smallest correction.**

1. Add a caption to the tie table: "Pooled precision of the frequency rule under alternative outcome-independent tie rules; Model C has no material ties."
2. Add one sentence: "About 17% of frequency selections at 10% come from tied scores; tie-rule changes move frequency precision by up to ~0.5–0.7 pp, comparable to the Model C − frequency differences, so those point differences are not robust."

No bundle change is needed.

## C. Aggregate bundle

| Check | Result |
| --- | --- |
| Exact rebuild | `build_bundle(final aggregate)` returns a bundle **identical** to `app_data/targeting_v1.json`, with content hash `44bcf667…c6f9` equal to `EXPECTED_CONTENT_SHA256`. |
| Upstream provenance | The bundle `source_manifest_input_sha256` values (dataset `44c580a8…`, source manifest `3d7ee78a…`, predictions `facdd362…`, baseline run manifest `81bb760a…`) match the M3 aggregate, the M3 manifest and the M3-002 report. The builder refuses any aggregate whose SHA-256 is not `5e9558f7…`. |
| Independent pin | Three probes edited a value, recomputed the embedded hash, and were **rejected** ("differs from independently pinned approved bundle"): frequency 10% precision set to 0.60, the C − frequency interval moved above zero, and an added policy interval. |
| Schema | Exact key sets for every section. Capacities must be exactly `5pct/10pct/20pct` with values 0.05/0.10/0.20. Approved policy set and labels, frozen holdout counts, and finite numbers with ordered intervals are enforced. |
| Customer-level content | None. No customer IDs, scores, prediction rows, outcomes or selection lists. The key-name blocklist is applied. The selection Parquet is not referenced at runtime, and no Parquet or selection file is tracked by Git. Granularity is pooled only; monthly cells are not included. |
| Controlled errors | Missing file, bad JSON and tampered values give a single `st.error`. Malformed section types do not (**R1**). |

### R1 — Malformed sections and provenance escape the controlled-error path (Low–Medium)

**Evidence.** A fuzz pass replaced every field and section with None, a string, 0, −1, [], {}, True and [1]:

- Wrongly typed **sections** raise uncaught `TypeError`, for example `capacities: null` gives "'NoneType' object is not iterable". This affects capacities, holdout, overlap, tie sensitivity, repeated selection and definitions.
- A non-dict `provenance` raises `AttributeError`, from `b["provenance"].get` being called before its schema check.
- Changes to `provenance.source_documents`, `source_manifest_input_sha256`, `source_manifest` and `builder` are **accepted**, because they are outside the content hash and only the aggregate hash is checked.

AppTest confirms the effect on the page:

- `capacities: null` renders a Streamlit exception with no error message.
- `provenance.source_documents: {}` renders the figures and then crashes with `KeyError: 'results'` in the provenance expander.

**Impact.**

- The page fails with a traceback instead of the documented controlled error.
- The displayed provenance (source document paths and upstream hashes) is unverified.
- The scientific figures themselves remain protected by the pin.

**Smallest correction.**

1. In `validate_bundle`, check that each section is a `dict` (or `list` for `repeated_selection`) before indexing, or convert `TypeError`/`AttributeError`/`KeyError` raised during validation into `BundleError`.
2. Require `provenance` to equal the approved constants (source documents, manifest input hashes, manifest name, builder), as the propensity bundle already does.
3. Add one test for a mistyped section and one for altered provenance.

## D. Interactive application

The checks below were run in a clean copy (HEAD plus the M5-004 changes, **no `data/`**, `LOCAL_DATA_DIR` unset) with a fresh Python 3.11 venv installed from `requirements-app.txt`. Each page was rendered through the real `st.navigation` routing by making it the default in a probe copy of the entry script.

| Check | Result |
| --- | --- |
| Capacity selector | Radio options are exactly `['5%', '10%', '20%']`, with 10% as the default. The validator and `policy_comparison` reject any other capacity (tested with 15%). |
| Consistent updates | Switching to 5%, 10% and 20% updates the subheader, policy table, pairwise table, overlap, tie row and repeated-selection rows, and every value matches the same capacity in the bundle. For example, C − frequency is +1.47 [−0.09, +3.21], +0.55 [−0.50, +2.17] and +0.69 [−0.28, +1.26]. |
| Chart scale | The precision bar chart uses a fixed 0–1 axis, so 1–3 pp differences are not visually exaggerated. Differences appear only as signed values with intervals in a table. |
| Missing intervals | No policy-level interval is displayed or estimated, and a caption says they were unavailable. |
| Pairwise labelling | Conditional, exploratory, not a hypothesis test, crossing zero ≠ equivalence. Conditional on the tie rule (see R2). Bootstrap limitations are shown in the expander. |
| Visible limitations | The evidence label ("Retrospective targeting… not the causal effect of contact") and a visible `st.warning` cover: not randomised treatment response, precision ≠ incremental value, and no eligibility, consent, contact policy or economics. |
| Other pages | Customer Overview (4 metrics), Purchase Propensity (14 metrics) and the Experiment Feasibility placeholder all render with no exceptions. |
| Runtime file access | An audit hook over a full four-page run shows the only data files opened were the three tracked `app_data/*.json` bundles. No `source_data` or Parquet file was opened. |
| Live server | Clean copy: `/_stcore/health` returned `ok`. |

## E. Reproducibility and tests

| Run | Result |
| --- | --- |
| Focused app suites (5 modules), dev venv | **36 OK, 1 skip** (propensity rebuild with `LOCAL_DATA_DIR` unset) |
| Same, clean copy with fresh venv | **36 OK, 2 skips** (both private-input rebuilds) |
| Full `tests/` discovery | **163 OK, 2 skips** (Spark/Java and the propensity rebuild) |
| M3 targeting research tests (`tests.test_monthly_targeting_policies`) | OK |
| Corrected-V2 007 recovery tests | 15 OK |

**Test content.** The tests cover the pin and provenance, exact capacities and policies, null standalone intervals, controlled errors for missing or malformed files, capacity validation, and AppTest rendering with the capacity switch and causal warning.

Gaps (optional, O4):

- There is no rebuild-equality test against the frozen aggregate.
- The identifier test is rejected by the schema check before the pin is reached.
- There is no test that a recomputed-hash metric edit is rejected. This review verified it manually.

## F. Findings summary

### Required for closure

| ID | Severity | File | Correction |
| --- | --- | --- | --- |
| R1 | Low–Medium | `src/targeting_bundle.py` | Type-guard sections, or map `TypeError`/`AttributeError`/`KeyError` to `BundleError`. Pin provenance to approved constants. Add two tests. |
| R2 | Low–Medium | `app/views/placeholders.py` (Targeting Explorer) | Caption the tie table as frequency-rule pooled precision. Add the one-sentence M3-003 disclosure: ~17% tied selections, and tie shifts comparable to the C − frequency differences, so the point differences are not robust. |

### Optional (not blocking)

- **O1:** Move the page from `app/views/placeholders.py` to its own `app/views/targeting_explorer.py`. The placeholder module now imports the targeting bundle at import time, so the Experiment Feasibility placeholder depends on it.
- **O2:** RFM repeated-selection aggregates (321 / 647 / 1,271 distinct; 247 / 490 / 979 multiple) exist in the frozen aggregate but are omitted. Either add them or label the table "Model C and frequency".
- **O3:** The tie-rule precisions are transcribed from M3-003 text. Record SHA-256 hashes of the M3-002 and M3-003 documents in provenance, as the propensity bundle does.
- **O4:** Add a skip-if-unavailable rebuild-equality test, and a recomputed-hash metric-tamper test.
- **O5:** Rename "Lift vs random" to "Lift over pooled prevalence", which is the computed quantity.
- **O6:** Reject `bool` for `schema_version` (`True == 1` currently passes).

## Commit readiness

After R1 and R2, **M5-004 is ready for a scoped local commit**:

- The three modified files.
- The five new files.
- This review.

R1 changes only validation code and tests. R2 changes only page text. The bundle and `EXPECTED_CONTENT_SHA256` stay the same. Re-run the five focused app modules after editing.

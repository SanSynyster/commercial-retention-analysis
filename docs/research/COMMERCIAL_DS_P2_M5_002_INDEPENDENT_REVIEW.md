# M5-002R — Independent Review: Customer Intelligence Dashboard (Customer Overview)

## Verdict

**PASS WITH CONDITIONS.**

The Customer Overview page and its aggregate bundle are scientifically faithful to the accepted corrected-V2 outputs, and the app runs from a clean checkout with a fresh install of `requirements-app.txt`. No customer-level or private data is needed at runtime.

Three small corrections are required before closure:

| ID | Severity | Topic | Correction |
| --- | --- | --- | --- |
| R1 | Medium | Complementary disclosure | Disclose that the four suppressed cells can be recovered exactly from the tracked accepted Figure 2 SVG. Describe suppression as a display convention, not a disclosure guarantee. |
| R2 | Medium | Bundle integrity | Pin the expected content hash in code so that rehashed but internally consistent edits are rejected. |
| R3 | Low | Malformed bundle handling | Schema-check `provenance` and `publication_review` so that a malformed bundle fails closed instead of raising an uncaught exception. |

None of the three requires a change to the published data values, the research outputs or the page design.

## Review scope and baseline

- **Repository:** `commercial-retention-analysis-dev`, HEAD `d01434fb04850630d8e7747aca10ea773af1300c`. The M5-001 and M5-002 files are untracked: 14 files, with `__pycache__/` correctly ignored.
- **Read:**
  - The M5-001 plan and the M5-002 implementation note.
  - `src/customer_overview_bundle.py` and `src/customer_overview_metrics.py`.
  - `app/streamlit_app.py`, `app/views/*.py` and `app/README.md`.
  - `app_data/customer_overview_v1.json`.
  - `reports/corrected_v2/corrected_v2_scientific_results.md` and Figure 2.
  - The local corrected-V2 aggregate inputs.
  - Both new test modules.
- **Unchanged:** no implementation, dataset or existing report was modified. The only artifact written is this review.
- **Scratch work:** clean-checkout copies, a fresh venv and probe scripts were kept in a session scratch directory outside the repository.

## A. Scientific accuracy

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Headline metrics use corrected-V2 definitions | **Pass** | The bundle matches the accepted report exactly: 5,852 customers; 36,594 occasions; 788,127 lines; £17,123,740.997 qualifying gross; £2,575,930.13 unattributed; 5,256 mature / 596 immature. The values are pinned in `REFERENCE` (`src/customer_overview_bundle.py:40`). The rendered metrics are 5,852, 36,594, £17.12m and 63.8%. |
| 2 | Identified vs unattributed merchandise | **Pass** | Unattributed £2.58m is stated as excluded from every customer measure (headline caption) and from the concentration caption. It is never added to a denominator. |
| 3 | Concentration denominator | **Pass** | Top ceil(10%) = 586 customers. £10,926,893.967 ÷ £17,123,740.997 (identified qualifying gross only) = 63.8114%, which matches the report. The validator checks the ceiling rule and that numerator ÷ denominator equals the share. |
| 4 | Two 90-day populations kept separate | **Pass** | 25 strata (12 pre-cutoff, 13 on/after) are drawn as separate coloured series, with no pooled row. The validator rejects `ALL`. All 25 rows of eligible, mature, numerator, conversion and insufficient follow-up match the report table exactly. Median days match the source. |
| 5 | Partly mature and immature months | **Pass** | 2011-09 is labelled partly mature (32 of 188). 2011-10, 2011-11 and 2011-12 have null conversion, are not plotted and are named in a caption. The mature-only denominator is stated. Optional: mark the 2011-09 point differently (O2). |
| 6 | Cohort and observation-window definitions | **Pass** | Cohorts are first-observed months, and the cell denominator is cohort size. The last complete month is 2011-11. Month 0 is omitted as "entry, 100% by construction". The December 2011 cohort's month 0 is null. The caption says first observed is not acquisition. The grid has 296 observed + 4 suppressed = 300 complete cells and 325 unobserved cells, which matches the report (300 / 325). |
| 7 | Unobservable or suppressed cells never shown as zero | **Pass** | Such cells are stored as `null` with an explicit status. The validator rejects non-null values in non-observed cells. The heatmap colours only cells where `isValid(activity_pct)` and leaves the rest grey. A 0/0.0 injection into a future cell is rejected (tested). Optional: add a legend key for grey cells (O3). |
| 8 | Frequency/recency groups are descriptive | **Pass** | The six counts and gross values match the report. The caption reads "Descriptive groups only: not churn predictions, validated segments or CRM targeting rules". Recency bands (0–59, 60–89, 90+ days relative to the partial 2011-12-09 end) match 007C. |

**No material discrepancy with the accepted research outputs was found.** Minor wording gap (optional, O1): the definitions expander does not state that the 90-day window is half-open (day +89 included, day +90 excluded) and counts only strictly later purchase dates. The accepted report does state this.

## B. Aggregate bundle

### Schema, provenance and pinned totals — pass

- **Schema:** exact field allowlists exist per section. A type check rejects bools in place of ints, and non-finite numbers are rejected. Decimal money is stored as strings.
- **Source hashes:** all five recorded `source_aggregate_sha256` values match the local corrected-V2 aggregate files byte for byte. `builder_sha256` (`08c3b4ea…`) matches the current builder.
- **Rebuild:** the rebuild test (run here with private aggregates present) reproduces every data section exactly. The builder re-applies the accepted 007D `validate` contract before extracting anything.
- **Consistency checks:** these are substantive:
  - Repeat strata sum to the headline.
  - Eligible = mature + immature.
  - Conversion = numerator ÷ mature.
  - Month 0 = cohort size, and the entry sizes reconcile to first-observed counts.
  - Segment counts and gross sum to the totals.
  - The concentration rule holds.
- **No customer-level content:** no customer-level records or identifier fields are present. The key-name blocklist is enforced recursively. The excluded source files are all listed with a reason.

### R2 — Content hash is self-attested (Medium)

**Evidence.** `validate_bundle` compares `content_sha256` only with a hash recomputed from the same file (`src/customer_overview_bundle.py:219`). Repeat-stratum numerators and cohort-cell counts are not pinned elsewhere. Two probes edited a field, kept it internally consistent and rehashed the bundle; both were **accepted**:

- Pre-cutoff 2009-12 repeat numerator changed from 558 to 900, with the conversion fraction updated to match.
- A month-1 cohort cell changed to 100% active.

**Impact.**

- The hash detects accidental corruption only, not a substituted or regenerated bundle.
- 650 of the scientific values on the page (25 strata and 625 cells) are protected by internal consistency checks only, not by reference to accepted values.
- The implementation note says the hash "the loader verifies". That is literally true but overstates the guarantee.

**Smallest correction.**

1. Add a module constant `EXPECTED_CONTENT_SHA256 = "5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c"`.
2. Reject any bundle whose `content_sha256` differs from it. The builder should also print the hash, so the constant is updated deliberately with any new bundle version.
3. Add one test showing that a consistent, rehashed repeat-numerator edit is rejected.

This pins every published value without a new framework.

### R3 — `provenance` and `publication_review` are not validated (Low)

**Evidence.** Replacing `provenance` with `{}` passes `validate_bundle`. The page then renders all the figures and raises an uncaught `KeyError: 'reference_report'` in `_provenance` (`app/views/customer_overview.py:255`). These two sections are also outside the content hash.

**Impact.** A malformed bundle shows a Streamlit traceback instead of the documented fail-closed message, and the provenance shown is unverified. This does not affect the scientific figures.

**Smallest correction.** Add field-set checks in `validate_bundle` for both sections (`provenance` keys including `source_aggregate_sha256`; `publication_review` keys including `small_cell_threshold` and `suppressed_cohort_cells`), and add a one-line test.

### Small-cell handling and focused complementary-disclosure check

**Within the bundle: no reconstruction is possible.** All four suppressed cells are in the December 2010 cohort (n = 76) at months 2, 6, 8 and 9. The bundle publishes no cross-cohort activity-month totals, no row totals and no other cohort-specific counts that could be differenced. The related fields only give bounds:

- The 90-day repeat numerator for 2010-12 is 12, with a median of 38 days.
- The neighbouring cells are 7, 7, 9, 5, 7, 7 and 15.
- The suppression rule and `active > 0` imply each suppressed cell is 1–4.

None of these pins any suppressed cell exactly.

### R1 — Suppressed cells are recoverable from the tracked accepted Figure 2 (Medium)

**Evidence.** `reports/corrected_v2/figures/fig02_first_observed_cohort_activity.svg` is tracked at HEAD. It encodes every complete cell, including the four the dashboard suppresses, as a continuous fill colour.

A linear map from RGB to fraction was fitted on the 272 unsuppressed post-entry cells, with a maximum absolute error of 0.0024. Inverting it on the December 2010 row gives:

| Month index | Recovered count (×76) | Source count |
| --- | --- | --- |
| 2 | 4.07 | 4 |
| 6 | 4.07 | 4 |
| 8 | 4.07 | 4 |
| 9 | 2.04 | 2 |

Every suppressed count is recovered exactly. The fill resolution (~0.2 percentage points) is much finer than one customer in a cohort of 76 (1.3 percentage points).

**Impact.**

- In this repository, the M5-002 suppression is not an effective disclosure control. It adds a convention that the accepted corrected-V2 report never applied.
- The practical risk is low. The underlying data is the public UCI Online Retail II dataset, and the exposure is counts of 2–4 customers active in a calendar month.
- The defect is mainly an **overstated assurance**: `publication_review.suppression_rule`, the implementation note's "Data-publication checks" and the page's "Publication review" line present suppression as a publication safeguard.

**Smallest correction that keeps the dashboard useful.** Keep the dashboard suppression; it removes only 4 of 300 complete cells.

1. Reword `publication_review.suppression_rule`, the implementation note and `app/README.md` to say that it is a dashboard display convention. State that the accepted, already-tracked corrected-V2 Figure 2 encodes these cells, so suppression is not a disclosure guarantee.
2. Leave Figure 2 unchanged under this milestone.

If the owner wants <5 to be a hard publication rule, that needs a separate corrected-V2 report amendment to regenerate Figure 2. It is out of M5 scope and not required for closure. Removing suppression from the dashboard instead would also be consistent, but it reverses an explicit conservative choice, so it is not recommended.

`publication_review` is outside the content hash, so rewording it does not change `content_sha256`. It will change `builder_sha256` if the wording lives in the builder.

No other small-count exposure was found within this page's scope. The smallest segment has 125 customers. The smallest repeat strata (12 of 76; 21 of 32) are already published in the accepted report table.

## C. Application functionality

Smoke tests ran in a clean copy of the repository. The copy was built from `git archive HEAD` plus the 14 untracked M5 files, and has **no `data/` directory**. The environment was a **fresh Python 3.11 venv** installed only from `requirements-app.txt` (Streamlit 1.66.1, Altair 6.3.0, pandas 3.0.2).

| Check | Result |
| --- | --- |
| `streamlit run app/streamlit_app.py` (headless, port 8599) | Server started. `/_stcore/health` returned `ok`. `/` and `/targeting-explorer` returned HTTP 200. |
| Customer Overview render (AppTest) | No exceptions or errors. 4 metrics, 4 subheaders, 5 Vega-Lite charts, 3 dataframes, 2 expanders and the evidence label caption. |
| Chart labels and denominators | Each section caption states the population and denominator: mature-only for the 90-day chart, identified qualifying gross for concentration, cohort size for the cohort heatmap, and all 5,852 customers for segments. Tooltips show numerators and mature denominators. |
| Population toggle | Switching to the on/after population works without error. The caption reports "4 cell(s) suppressed in this view". |
| Four-page navigation | Four `st.Page` entries with `st.navigation` are present. The three placeholder pages render with a title, evidence type and "Planned for" notice. |
| Missing bundle | Fails closed with an error message and no metrics. |
| Non-JSON bundle | Fails closed. |
| Inconsistent edited bundle | Fails closed with "content hash does not match". |
| Malformed `provenance` | **Uncaught `KeyError`** (R3). |
| Runtime file access | A Python audit hook on `open` during a full page run showed the only repository data file read was `app_data/customer_overview_v1.json`, besides the app source files. |
| Separation of interface and calculations | Bundle I/O and validation are in `customer_overview_bundle.py`. Pure table functions with no Streamlit code are in `customer_overview_metrics.py`. The view does only label formatting and caption assembly. |

## D. Reproducibility

- **Launch:** `pip install -r requirements-app.txt` followed by `streamlit run app/streamlit_app.py` works from a clean checkout. The fresh-install check is above.
- **Runtime dependencies:** normal runtime does **not** require raw UCI data, corrected-V2 private outputs, customer-level Parquet/CSV files, or local prediction files. Confirmed by:
  - Running with `data/` absent.
  - The audit hook result.
  - The fact that `customer_overview_bundle` imports only the standard library unless `build_bundle` is called.
- **Documented clean-checkout test:** the method (tracked plus new files, no `data/`) is meaningful, because `ROOT` resolves to the copy and the private source path does not exist there. However, the note's evidence that "the app server responds healthy" does not execute the page script. The health endpoint answers before any session runs. The meaningful evidence is the focused AppTest suite passing in that copy, which this review reproduced: 18 tests, OK, 1 expected skip. Optional O5: say so in the note, and state that the clean check used a fresh install.
- **Rebuild:** rebuilding the bundle needs the private aggregates, as documented. That step is maintainers-only and is not on the runtime path.

## E. Tests

| Suite | Result |
| --- | --- |
| Focused (`tests.test_customer_overview_bundle`, `tests.test_dashboard_app`), dev venv with private aggregates present | **18 OK**, including the rebuild-equality test |
| Focused, clean copy with fresh venv | **18 OK, 1 skipped** (rebuild needs private data, by design) |
| Full `tests/` discovery | **145 OK, 1 skipped** (existing Spark skip) |
| Corrected-V2 007 recovery (`discover -s docs/recovery -p 'test_COMMERCIAL_DS_007*.py'`) | **15 OK** |

The tests do cover material scientific invariants, not only successful rendering:

- Pinned corrected-V2 totals.
- No pooled repeat stratum.
- Immature strata remain null.
- The 2011-09 partial-maturity label.
- Unavailable cohort cells remain null.
- A zero injected into a future cell is rejected.
- Small cells are suppressed.
- Concentration and segment reconciliation.
- Rehashed inconsistent edits are rejected.
- Rebuild equality with the private sources.

Gaps:

- **Per-stratum and per-cell values are not tied to accepted values** in a clean checkout. This is addressed by R2.
- **Malformed provenance is untested.** This is addressed by R3.
- **Navigation is checked weakly** (O4). `test_navigation_registers_four_pages` asserts on source text rather than navigating. The placeholder pages are tested separately through their functions.

## F. Findings summary

### Closure conditions (required)

| ID | Severity | Finding | Smallest correction |
| --- | --- | --- | --- |
| R1 | Medium | The four suppressed cohort cells (Dec 2010 cohort, months 2, 6, 8 and 9) are exactly recoverable from the colours in the tracked accepted Figure 2 SVG. Bundle-internal reconstruction is not possible. | Reword `publication_review.suppression_rule`, the M5-002 note and `app/README.md`: suppression is a display convention, not a disclosure guarantee, because accepted Figure 2 encodes these cells. A hard <5 rule would need a separate corrected-V2 figure amendment. |
| R2 | Medium | The content hash is self-referential. Consistent rehashed edits to repeat numerators or cohort cells are accepted. | Pin `EXPECTED_CONTENT_SHA256` (`5bd05077…6c4c`) in the loader and add one tamper test. Adjust the note's wording. |
| R3 | Low | `provenance` and `publication_review` are not schema-checked. A malformed section crashes the page with `KeyError`. | Add field-set checks to `validate_bundle` and one test. |

### Optional improvements (not blocking)

- **O1:** State the half-open 90-day window and the "strictly later date" rule in the definitions expander.
- **O2:** Visually mark the partly mature 2011-09 point (n = 32 mature of 188), for example with a hollow marker.
- **O3:** Add a legend key for grey (unavailable or suppressed) cohort cells. Low-activity teal and grey are close in hue.
- **O4:** Replace the source-text navigation assertion with an AppTest page switch, or an assertion on the registered pages.
- **O5:** In the M5-002 note, cite the clean-copy AppTest run rather than the health endpoint as clean-checkout evidence, and note that it used a fresh install.
- **O6:** Page names differ between M5-001 ("CRM Targeting Explorer", "Pilot & Value Scenarios") and the app ("Targeting Explorer", "Experiment Feasibility"). Align them in M5-003 or later.

## Commit readiness

After R1–R3, **M5-001 and M5-002 can be committed together** as one coherent change. Its 14 files are:

- The plan and the implementation note.
- `requirements-app.txt`.
- The two `src` modules.
- The four `app/` files and `app/README.md`.
- The bundle.
- The two test modules.

`__pycache__/` is already ignored.

- **R2 and R3:** these change only code and tests.
- **R1:** this changes text in the builder, the note and the README. If the bundle is regenerated for the reworded `publication_review`, its data sections and `content_sha256` stay the same, and only `builder_sha256` changes. Re-run the focused and full suites after the corrections.

This review document can be committed with them.

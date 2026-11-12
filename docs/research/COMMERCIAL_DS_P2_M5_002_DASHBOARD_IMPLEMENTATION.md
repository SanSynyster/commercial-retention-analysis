# M5-002 — Aggregate Data Bundle and Customer Overview Dashboard

## Result

This milestone delivers a local four-page Streamlit app with a fully working **Customer Overview** page, backed by a tracked, validated, aggregate-only bundle (`app_data/customer_overview_v1.json`). A clean checkout runs the app without raw UCI files, ignored `data/processed/` outputs or any customer-level artifact.

- **Pages:** Purchase Propensity, Targeting Explorer and Experiment Feasibility are labelled placeholders for later M5 milestones.
- **No research re-run:** no model was fitted, no experiment was run, and no M1–M4 artifact was changed.

## Files

| File | Purpose |
| --- | --- |
| `app/streamlit_app.py` | Entry point; `st.navigation` over four `st.Page` entries |
| `app/views/customer_overview.py` | Customer Overview UI only (Altair charts, tables, captions) |
| `app/views/placeholders.py` | Three placeholder pages stating their question, evidence type and planned milestone |
| `src/customer_overview_bundle.py` | One-time bundle builder plus runtime loader/validator (`BundleError` on any failure) |
| `src/customer_overview_metrics.py` | Pure table-preparation functions for the page; no I/O, no Streamlit |
| `app_data/customer_overview_v1.json` | Versioned aggregate bundle (v1.0.0, schema 1, 208 KB) |
| `requirements-app.txt` | `-r requirements-minimal.txt` plus `streamlit==1.66.1` |
| `app/README.md` | Install, launch, test and rebuild instructions |
| `tests/test_customer_overview_bundle.py`, `tests/test_dashboard_app.py` | Focused tests |

## Bundle contents and provenance

The bundle has two sources:

- **Source data:** the accepted corrected-V2 007B/007C aggregate outputs (`reconciliation.json`, `concentration_summary.csv`, `repeat_90d_by_first_observed_month.csv`, `first_observed_cohort_activity.csv`, `segment_summary.csv`). The builder first re-applies `COMMERCIAL_DS_007D_PACKAGE.validate`, the same accepted contract used to produce `reports/corrected_v2/`.
- **Recorded provenance:** the builder records each source file's SHA-256, the 007B/007C source commits and its own SHA-256 (`c53e6a52…`). It also stores a content hash of the data sections (`5bd05077…`), which the loader checks against an independent application-side pin.

| Section | Contents | Verified against |
| --- | --- | --- |
| `headline` | 5,852 identified customers; 36,594 qualifying occasions; 788,127 lines; £17,123,740.997 qualifying gross; £2,575,930.13 unattributed merchandise (excluded); 5,256 mature / 596 immature for 90-day follow-up; source span 2009-12-01 to 2011-12-09 12:50 (partial day); last complete month 2011-11 | README and `corrected_v2_scientific_results.md`; pinned in the validator |
| `concentration` | Top 586 customers (ceil 10%) hold £10,926,893.967 = 63.81% of identified qualifying gross | Ceiling rule and numerator/denominator checked |
| `repeat_90d` | 25 first-observed-month strata (two populations): eligible, mature, repeaters, conversion (null when no mature customers), median days, immature count | Sums reconcile to 5,852 / 5,256 / 596; no pooled row |
| `cohort_activity` | 625 cohort × month cells with size, active count and fraction, plus status (observed, not yet observable, suppressed) | Month 0 equals cohort size; unobservable cells null; fraction = active ÷ size |
| `segments` | Six frequency × recency groups: customer count, qualifying gross, share | The six accepted counts are pinned; counts and gross sum to totals |

Signed merchandise sensitivity, segment flags and the value-segment reconciliation are not needed for this page and are excluded. V1 metrics are not used anywhere.

## Aggregate handling and display convention

- **Not loaded at runtime:** raw transactions, customer-level Parquet/CSV files, customer IDs, predictions and targeting selections.
- **Schema enforcement:** the validator enforces exact field allowlists and rejects any field name containing customer, invoice, stock-code, description, prediction, probability, selection or email fragments.
- **Small-cell display:** 4 post-entry cells in the December 2010 cohort of 76 (months 2, 6, 8 and 9; 1–4 active customers) are stored as `suppressed_small_cell` with null values, and the validator rejects any unsuppressed observed cell below 5. This is a dashboard display convention, not a disclosure guarantee: the already tracked accepted corrected-V2 Figure 2 SVG encodes the underlying cell values.
- **Smallest published counts:** the smallest segment has 125 customers. The smallest repeat strata (12 repeaters of 76; 21 of 32 mature in September 2011) are counts in published report tables, not attribute combinations, and are retained.
- **Excluded fields:** the concentration tie-break text that references customer IDs, and redundant cohort flags.
- **Bundle content pin:** the loader checks the canonical data-section hash against both the bundle's recorded hash and an independent application-side expected hash (`5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c`). This detects content changes relative to the approved bundle; it is not a cryptographic authenticity guarantee if both the bundle and source code are modified.
- **Metadata validation:** required provenance and display-review fields and types are checked before rendering, so malformed metadata fails through the page's controlled bundle-error message.

## Customer Overview page

**Evidence label.** *Historical description*, with the population and observation window shown at the top of the page.

1. **Headline:** four metrics (identified customers, qualifying purchase occasions, qualifying gross, top-10% gross share) with definitions in tooltips. A caption gives occasions per customer and the excluded unattributed merchandise.
2. **Second purchase within 90 days:** a line chart by first-observed month, with the two populations kept separate and no pooled rate.
   - Partly mature and not-yet-mature months are named; immature months are not plotted.
   - Tooltips and an expandable table show numerators, mature denominators and median days.
3. **Revenue concentration:** top-10% versus remaining customers' share of identified qualifying gross. The caption explains the denominator and that this is not net sales.
4. **Monthly activity after first observed purchase:** a cohort heatmap with a population toggle. Month 0 is omitted. Grey cells mark not-yet-observable or suppressed cells, which are never shown as zero, and first observed is described as not a verified acquisition date.
5. **Purchase frequency × recency groups:** customer share and gross share for the six groups, plus a table. They are labelled as descriptive, not churn predictions or CRM rules.
6. **Definitions and provenance:** an expander covering occasion and gross definitions, which population each section uses, the bundle version and hash, the publication review and the source hashes.

## M5-002C review corrections

- The four December 2010 cohort cells with 1–4 active customers remain null in the dashboard as a display convention. They are recoverable from the accepted, tracked corrected-V2 Figure 2 SVG, so this is not a disclosure guarantee. The historical SVG and corrected-V2 results are unchanged.
- The canonical data-section SHA-256 remains `5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c` and is pinned independently in the application validator. This detects differences from the approved application bundle; it does not authenticate source code changed alongside the bundle.
- Required `provenance` and `publication_review` fields and types are validated before rendering. Missing or malformed metadata uses the controlled bundle error.
- Regeneration changed bundle metadata (`suppression_rule` and `builder_sha256`) only; accepted numerical values and the canonical data-section hash are unchanged.

The headless `AppTest` checks found no errors. A rendered headless-Chrome screenshot was inspected, and colour, label and number-format issues were fixed.

## Launch

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

## Tests

- **Focused:** 21 tests cover the bundle schema, fields and types, approved hash pin, accepted values, metric consistency, absence of identifiers, suppression, missing, invalid and tampered bundles, the builder with missing private inputs, the metric functions, app rendering, the population toggle, the placeholder pages, navigation registration and graceful handling of missing or malformed bundles.
- **Results:**
  - Full `tests/` suite: **148 tests, OK (1 existing Spark skip: Java unavailable)**.
  - Corrected-V2 007 recovery tests: **15 OK**.
  - Clean-checkout copy (tracked plus M5 files, no `data/`, fresh Python 3.11 install from `requirements-app.txt`): **21 focused tests OK (1 expected private-data rebuild skip)**. The Customer Overview page itself renders with AppTest and no errors; no private datasets are present or needed at runtime.

## Limitations and blockers

- **Rebuild needs private data.** Rebuilding the bundle requires the ignored corrected-V2 aggregates. The app itself does not.
- **Pinned bundle.** The approved application content hash is independently pinned; any accepted source/content revision needs a deliberate new application pin. This is a change detector, not source authenticity protection.
- **Local research exhibit.** No deployment or publication decision has been made.

## Recommended next milestone

**M5-003 — Purchase Propensity page.** Extend the bundle with an allowlisted aggregate section built from the M1 report metrics and the M2-008 run-manifest and M2-012 aggregate JSON (no prediction rows). Show M1 and M2 separately, with seasonal-shift, repeated-customer and exploratory-calibration caveats.

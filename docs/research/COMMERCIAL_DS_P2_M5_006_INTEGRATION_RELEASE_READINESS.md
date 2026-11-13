# Commercial DS P2 M5-006 — Integration and Release Readiness

**Status:** implementation and reproducibility checks complete; public release not performed.
**Development HEAD at start:** `6b4b98d079559b628b277794a2e1eb0a324257bb`.

## Four-page integration findings

The four pages are registered in the existing Streamlit multipage navigation and read the three approved aggregate JSON bundles. The M4 scenario page calculates in memory. None of the pages requires private transaction tables, customer-level predictions, selection lists, or fitted model binaries.

The review found one user-facing integration inconsistency: the navigation labels for the last two pages omitted “CRM”, and the targeting implementation lived in a module named `placeholders.py`. The navigation labels now match the page titles and the targeting implementation is named `targeting_explorer.py`. Its imports and tests use the new module path. The targeted page title, app navigation, default state, and bundle-error handling otherwise follow the existing conventions.

The content preserves the accepted scientific boundaries:

- **Customer Overview:** corrected-V2 aggregate results distinguish identified from unattributed merchandise and mature from incomplete 90-day follow-up. Frequency/recency groups are descriptive, not validated CRM segments.
- **Purchase Propensity:** M1 Day-21 and M2 established-customer results remain separate tasks and populations. M1 performance is weak; M2 is stronger. Calibration is exploratory and uses a previously examined holdout.
- **CRM Targeting Explorer:** M3 compares historical future-purchase capture, not causal response to contact. Model C versus frequency differences are small and inconclusive; the frequency tie sensitivity is visible. Historical selection is not contact.
- **CRM Experiment Feasibility:** M4 is a hypothetical pilot calculator. MDE is not expected uplift; net ITT and average contribution per enrolled customer are distinct. Eligibility, consent, costs, margins, and contact operations remain unknown.

## Changes implemented

- Updated `app/streamlit_app.py` navigation labels to **CRM Targeting Explorer** and **CRM Experiment Feasibility**.
- Renamed `app/views/placeholders.py` to `app/views/targeting_explorer.py` and updated imports and focused tests.
- Updated `README.md` to distinguish the separate interactive application from corrected-V2 findings.
- Reworked `app/README.md` for external readers: page summaries, Python 3.11 setup, bundle/data boundary, evidence limits, and focused/full test commands.

No M1–M4 calculations, frozen findings, bundle contents, or bundle pins were changed. No dependency was added.

## Reproducibility and verification

The clean-checkout exercise used a temporary source archive at `/tmp/commercial-m5-006-clean-20261112`, populated from tracked `HEAD` plus the working application files. It did not copy ignored `data/processed/` contents or `.local` files. The environment was Python 3.11 and installed only the documented application requirements.

Commands:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python -m unittest \
  tests.test_customer_overview_bundle \
  tests.test_dashboard_app \
  tests.test_propensity_summary_bundle \
  tests.test_purchase_propensity_page \
  tests.test_targeting_bundle \
  tests.test_experiment_feasibility_page \
  tests.test_crm_pilot_feasibility -v
.venv/bin/python -m unittest discover -s tests
.venv/bin/streamlit run app/streamlit_app.py --server.headless true --server.port 8769 --browser.gatherUsageStats false
curl --fail --silent --show-error http://127.0.0.1:8769/_stcore/health
```

Results:

- Development environment focused suite: **53 tests run, 1 skipped (52 passed)**. The skip needs the external M2 aggregate source.
- Development environment full suite: **170 tests run, 2 skipped (168 passed)**. Skips require external private aggregate inputs or a local Java runtime.
- Clean-checkout focused suite with only `requirements-app.txt`: **53 tests run, 2 skipped (51 passed)**. The skips require external/private aggregate inputs.
- Clean-checkout full suite: **170 tests run, 4 skipped (166 passed)**. Additional skips are expected because the isolated checkout has no private corrected-V2/M2 aggregates and no Java runtime.
- Streamlit started using the documented command. Its `/_stcore/health` endpoint returned `ok`; the server was stopped after the check.
- The focused AppTests render all four page modules and verify the registered four-page navigation. Runtime bundle paths resolve to the three JSON files in `app_data/` only.

The full suite emits existing Streamlit bare-mode warnings and scikit-learn deprecation warnings. They do not fail tests. The clean archive contained the three aggregate bundles and no raw/customer-level data files. Ignored local customer tables were not included.

## Proposed public-release manifest

This is a curated application addition to the existing public Phase 1 project, not a recommendation to publish the development repository wholesale.

### Public application code

- `app/streamlit_app.py`
- `app/views/__init__.py`
- `app/views/customer_overview.py`
- `app/views/purchase_propensity.py`
- `app/views/targeting_explorer.py`
- `app/views/experiment_feasibility.py`
- `src/customer_overview_bundle.py`
- `src/customer_overview_metrics.py`
- `src/propensity_summary_bundle.py`
- `src/targeting_bundle.py`
- `src/targeting_metrics.py`
- `src/experiment_feasibility_metrics.py`
- `src/crm_pilot_feasibility.py`

### Reviewed aggregate JSON bundles

- `app_data/customer_overview_v1.json`
- `app_data/propensity_summary_v1.json`
- `app_data/targeting_v1.json`

These are aggregate-only application bundles. Keep their independent content pins and schema/provenance checks with the code. The small-cell display convention in Customer Overview is not a disclosure guarantee: the corrected-V2 report and figures already contain related aggregate results.

### Application tests

- `tests/test_customer_overview_bundle.py`
- `tests/test_dashboard_app.py`
- `tests/test_propensity_summary_bundle.py`
- `tests/test_purchase_propensity_page.py`
- `tests/test_targeting_bundle.py`
- `tests/test_experiment_feasibility_page.py`
- `tests/test_crm_pilot_feasibility.py`

### Required documentation and attribution

- `app/README.md`
- `LICENSE`
- `docs/DATA_PROVENANCE.md`
- `reports/corrected_v2/corrected_v2_scientific_results.md`
- `reports/corrected_v2/README.md` and the four referenced SVG figures, if the root project README is included
- M1/M2 source summaries and protocols referenced by the propensity bundle: `docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md`, `COMMERCIAL_DS_P2_M1_009_BASELINE_RESULTS.md`, `COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md`, `COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md`, and `COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md`
- M3 targeting result and review references: `COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md` and `COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md`
- M4 design and feasibility context: `COMMERCIAL_DS_P2_M4_001_CRM_PILOT_DESIGN.md`, `COMMERCIAL_DS_P2_M4_002_CRM_PILOT_FEASIBILITY.md`, and `COMMERCIAL_DS_P2_M4_003_INDEPENDENT_FEASIBILITY_REVIEW.md`

Those research files are in `docs/research/`. Before publication, prepare a reader-facing research subset from the approved results and protocols. In particular, M2/M3 documents contain local reproduction instructions and references to excluded predictions, model artifacts, selection Parquet files, or external manifests. Do not include those underlying files; remove machine-specific paths and private artifact details from any public-facing copy. The app itself runs without them.

### Public-safe dependency specifications

- `requirements-app.txt`
- `requirements-minimal.txt` (the app requirements file includes this pinned research/runtime dependency set)

### Keep outside the application release

- Raw datasets and all of `data/raw/`, `data/processed/`, and `data/warehouse/`, including customer tables, feature snapshots, prediction rows, selection lists, and model artifacts.
- External M1/M2 manifests and aggregate rebuild inputs, calibration artifacts, and M3 customer-selection outputs.
- `.local/`, `.venv/`, logs, caches, credentials, editor state, and machine-specific outputs.
- M5-001 through M5-006 integration/review working notes, including this readiness report; they are implementation records rather than application documentation.
- The legacy recovery scripts and internal development notes, except where an existing public Phase 1 repository already contains a curated equivalent needed for its own README and report links.

The current app/source scan found no customer identifiers, credentials, or machine-specific absolute paths in the runtime modules or three bundles. The bundle provenance retains approved source hashes and references, not local paths. The full source research documents need the curation described above before they accompany a public app release.

## Exclusions and publication questions

No application or test blocker was found. Two release-preparation decisions remain:

1. The configured development `origin` is `https://github.com/SanSynyster/commercial-retention-analysis.git`, while the requested public Phase 1 URL is `https://github.com/SanSynyster/commercial-retention-analytics`. Confirm the intended target when a release is authorized; this milestone made no remote changes.
2. The application’s provenance links point to research documents that include excluded external/private artifact details. Publish curated reader-facing versions or omit detailed research source documents and provide concise reviewed summaries with the application. Keep the source bundle pins and scientific interpretation intact.

The local development repository has 45 commits and is not the public Phase 1 repository history. A clean working tree does not establish that its entire history is suitable for publication. Do not push this development history. Prepare a fresh curated release commit/tree from the existing public Phase 1 baseline or a new repository history containing only the approved manifest after content curation.

## Recommended release approach

Treat this as a release candidate only. First curate the required M1–M4 reading material and confirm the target repository. Then assemble the manifest as a clean tree based on the existing public Phase 1 content (or a new curated history), rerun the documented app tests and health check from that tree, and let the owner publish it separately. No public release, commit, or push was made for M5-006.

# Customer Intelligence & Decision Support (local Streamlit app)

A four-page research exhibit. **Customer Overview** and **Purchase Propensity** are implemented; Targeting Explorer and Experiment Feasibility remain placeholders.

## Run

From the repository root (Python 3.11):

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

At runtime the app reads only the tracked aggregate bundles `app_data/customer_overview_v1.json` and `app_data/propensity_summary_v1.json`. It needs no raw UCI files, `data/processed/` outputs, row-level predictions or customer-level data. If a bundle is missing or fails validation, its page shows a controlled error instead of figures.

## Tests

```sh
.venv/bin/python -m unittest tests.test_customer_overview_bundle tests.test_dashboard_app tests.test_propensity_summary_bundle tests.test_purchase_propensity_page -v
```

## Rebuilding the bundle (one-time research step, maintainers only)

This step needs the accepted corrected-V2 aggregate outputs in the ignored `data/processed/corrected_v2_customer_analytics/` directory. It is not part of normal app use.

```sh
.venv/bin/python src/customer_overview_bundle.py --output app_data/customer_overview_v1.json
```

Before writing, the builder re-applies the accepted 007D contract checks. It keeps only allowlisted aggregate fields and records source hashes and a content hash. The four small post-entry cohort cells are null in this dashboard as a display convention only; they are recoverable from the already tracked accepted corrected-V2 Figure 2 SVG, so this is not a disclosure guarantee.

The loader checks the data-section hash against an independently pinned approved application-bundle hash. This detects changes relative to that approved bundle; it is not a cryptographic authenticity guarantee if both the bundle and application source are changed.

## Rebuilding Purchase Propensity summary (maintainers only)

The propensity bundle builder reads only the frozen M2 aggregate run manifest and calibration aggregate, checks their SHA-256 values plus the tracked M1/M2 report and protocol hashes, then extracts an allowlisted summary. Pass local paths explicitly; generated bundle provenance stores hashes and repository-relative source references, not local paths.

```sh
.venv/bin/python src/propensity_summary_bundle.py \
  --m2-run-manifest "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json" \
  --m2-calibration-aggregate "$LOCAL_DATA_DIR/m2_012_sequential_calibration_outputs/m2_012_sequential_calibration_aggregate.json" \
  --output app_data/propensity_summary_v1.json
```

The propensity bundle has an independent application-side content hash pin. A changed research source is rejected for deliberate review rather than silently substituted. The dashboard does not read prediction Parquets or model artifacts.

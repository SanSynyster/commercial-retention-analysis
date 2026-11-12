# Customer Intelligence & Decision Support (local Streamlit app)

A four-page research exhibit. **Customer Overview**, **Purchase Propensity**, **Targeting Explorer** and **CRM Experiment Feasibility** are implemented.

## Run

From the repository root (Python 3.11):

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

At runtime the first three pages read only their tracked aggregate bundles `app_data/customer_overview_v1.json`, `app_data/propensity_summary_v1.json` and `app_data/targeting_v1.json`. CRM Experiment Feasibility calculates explicitly hypothetical scenarios in memory with the existing M4 functions. The app needs no raw UCI files, `data/processed/` outputs, row-level predictions or customer-level data.

## Tests

```sh
.venv/bin/python -m unittest tests.test_customer_overview_bundle tests.test_dashboard_app tests.test_propensity_summary_bundle tests.test_purchase_propensity_page tests.test_targeting_bundle tests.test_experiment_feasibility_page tests.test_crm_pilot_feasibility -v
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

## Rebuilding CRM Targeting Explorer summary (maintainers only)

Use only the final frozen M3-002 aggregate JSON. The builder verifies its approved aggregate hash and exports allowlisted metrics; it does not read customer-level selections.

```sh
.venv/bin/python src/targeting_bundle.py \
  ../source_data/uci_online_retail_ii/m3_002_targeting_outputs_final/m3_002_targeting_aggregate.json \
  --output app_data/targeting_v1.json
```

The loader pins the aggregate source and canonical content hashes independently. The app displays the three evaluated capacities only.

## CRM Experiment Feasibility

This page does not use a data bundle. Its inputs are visibly hypothetical and its calculations reuse `allocate_enrollment`, `mean_difference_mde`, `commercial_scenarios` and `capacity_sensitivity` from `src/crm_pilot_feasibility.py`. The default scenario follows the M4 primary 10% total-enrollment design, 1:1 allocation, two-sided α=0.05 and 80% power. Changing capacity is shown as a sensitivity scenario and may change the target population and estimand. No experiment, treatment effect, eligible count, margin variance or campaign cost is inferred from the historical data.

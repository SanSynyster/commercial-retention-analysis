# Customer Intelligence & Decision Support

A local Streamlit application presenting research and planning views built from corrected Online Retail II analysis. Historical pages describe or predict purchasing in the 2009–2011 data; they do not show current CRM customers or estimate the effect of marketing contact. The experiment page is a hypothetical calculator, not a launched campaign.

## Pages

- **Customer Overview** — corrected-V2 purchasing, mature 90-day follow-up, revenue concentration, cohort activity and descriptive frequency/recency groups.
- **Purchase Propensity** — separate M1 new-customer and M2 established-customer prediction results, plus exploratory calibration. M1 and M2 are different tasks; calibration reuses a previously examined holdout.
- **Predictive Intelligence** — aggregate-only P3 M2 comparisons for Logistic C, Random Forest, HistGradientBoosting, XGBoost, LightGBM and frequency; global Random Forest SHAP and stability summaries; P3-005 calibration diagnostics. Development results used for selection are separated from the previously examined July–November exploratory replay.
- **CRM Targeting Explorer** — retrospective purchase capture for four policies at the evaluated 5%, 10% and 20% capacities. Purchase propensity is not causal CRM uplift.
- **CRM Experiment Feasibility** — hypothetical enrollment, allocation, MDE and economics for the proposed M4 randomized pilot. No treatment effect or business input is estimated from the historical data.

## Install and launch

Use Python 3.11 from the repository root:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

The app runs locally and makes no network or database calls.

## Data and evidence limits

The historical research pages read only reviewed aggregate JSON bundles in `app_data/`. The feasibility page calculates in memory using the M4 scenario functions. The app does not require raw transactions, customer-level records, prediction rows, targeting lists or model binaries.

### P3 predictive bundle

`app_data/p3_predictive_v1.json` is an aggregate-safe projection of the exact P3-002, P3-003, P3-004 and P3-005 research outputs. It contains pooled metrics, supported paired intervals, global and period-level SHAP summaries, and calibration summaries; it contains no individual predictions or customer records. Its schema, canonical content checksum and source hashes are checked by `src/p3_predictive_bundle.py`.

To rebuild it, run from the repository root when the reviewed private aggregate files are available in the sibling `source_data/` tree:

```sh
.venv/bin/python -m src.p3_predictive_bundle --build
```

The builder uses explicit source paths and pinned SHA-256 values; it does not search for a newer or similarly named run. It fails on missing or mismatched sources. Tests that need those external sources skip when they are unavailable; tests of the committed bundle continue to run. Rebuilding writes only the app bundle and does not rerun models.

The underlying retail data are observational and historical, with a partial source endpoint in December 2011. First observed purchase is not verified acquisition; gross merchandise is not net sales, margin or profit; and descriptive groups are not validated CRM segments. Prediction and retrospective targeting metrics measure purchasing patterns, not treatment response. The July–November UCI holdout was previously examined and is exploratory, not untouched confirmation. RF is a development reference, not prospectively validated deployment inference; calibration remains a provisional research candidate, and SHAP is predictive attribution rather than causal importance. Actual eligibility, consent, contact rules, margin variance and costs are not established. See the root [project README](../README.md) and [data provenance and attribution](../docs/DATA_PROVENANCE.md) for research definitions and source terms.

## Tests

Run the focused application and M4 tests:

```sh
.venv/bin/python -m unittest \
  tests.test_customer_overview_bundle \
  tests.test_dashboard_app \
  tests.test_propensity_summary_bundle \
  tests.test_purchase_propensity_page \
  tests.test_p3_predictive_bundle \
  tests.test_predictive_intelligence_page \
  tests.test_targeting_bundle \
  tests.test_experiment_feasibility_page \
  tests.test_crm_pilot_feasibility
```

Run the full repository suite:

```sh
.venv/bin/python -m unittest discover -s tests
```

Some research-input rebuild tests skip when the external source aggregates are unavailable. They are not needed to run the app or its page tests.

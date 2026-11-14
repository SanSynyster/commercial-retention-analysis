# Customer Intelligence & Decision Support

A local seven-page Streamlit application presenting research and planning views built from corrected Online Retail II analysis and a separate historical randomised email experiment. UCI-based pages describe or predict purchasing in the 2009–2011 data; they do not show current CRM customers. The causal evidence page summarizes Hillstrom assignment effects and does not provide UCI customer scores or campaign execution. The experiment-feasibility page is a hypothetical calculator, not a launched campaign.

## Pages

- **Customer Overview** — corrected-V2 purchasing, mature 90-day follow-up, revenue concentration, cohort activity and descriptive frequency/recency groups.
- **Purchase Propensity** — separate M1 new-customer and M2 established-customer prediction results, plus exploratory calibration. M1 and M2 are different tasks; calibration reuses a previously examined holdout.
- **Predictive Intelligence** — aggregate-only P3 M2 comparisons for Logistic C, Random Forest, HistGradientBoosting, XGBoost, LightGBM and frequency; global Random Forest SHAP and stability summaries; P3-005 calibration diagnostics. Development results used for selection are separated from the previously examined July–November exploratory replay.
- **Segmentation Intelligence** — March 2011 historical RFM profiles and subsequent April–June purchase behaviour, with the selected three-cluster K-Means solution as supplementary exploratory evidence. It links to the existing retrospective CRM Targeting Explorer; it does not assign current customers or estimate contact effects.
- **Causal Evidence & Experimentation** — aggregate-only Hillstrom randomised-study evidence, with the locked-test assignment effect and Holm-adjusted secondary visit comparisons separated from exploratory development uplift-policy comparisons. Hillstrom is distinct from the observational UCI retail population; no customer scoring or campaign execution is provided.
- **CRM Targeting Explorer** — retrospective purchase capture for four policies at the evaluated 5%, 10% and 20% capacities. Purchase propensity is not causal CRM uplift.
- **CRM Experiment Feasibility** — hypothetical enrollment, allocation, MDE and economics for the proposed M4 randomised pilot. No treatment effect or business input is estimated from the historical data.

## Install and launch

Use Python 3.11 from the repository root:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

The app runs locally and makes no network or database calls.

It does not perform live P3 model inference, train models at startup, read private source datasets, create customer-level scores or lists, or execute campaigns. It loads the committed aggregate bundles and calculates only the documented M4 planning scenarios in memory.

## Data and evidence limits

The historical research pages read only reviewed aggregate JSON bundles in `app_data/`. The feasibility page calculates in memory using the M4 scenario functions. The app does not require raw transactions, customer-level records, prediction rows, targeting lists or model binaries.

### Optional bundle path overrides

Aggregate-backed pages use the committed `app_data/` bundle by default. For local inspection or controlled error testing, set an override to a compatible, content-pinned bundle JSON path before startup:

| Page | Environment variable |
|---|---|
| Customer Overview | `CUSTOMER_OVERVIEW_BUNDLE` |
| Purchase Propensity | `PURCHASE_PROPENSITY_BUNDLE` |
| Predictive Intelligence | `P3_PREDICTIVE_BUNDLE` |
| Segmentation Intelligence | `P3_SEGMENTATION_BUNDLE` |
| Causal Evidence & Experimentation | `P3_CAUSAL_BUNDLE` |
| CRM Targeting Explorer | `TARGETING_BUNDLE` |

For example: `P3_CAUSAL_BUNDLE=/path/to/p3_causal_v1.json .venv/bin/streamlit run app/streamlit_app.py`. Missing, unreadable, malformed, unsupported or checksum-mismatched bundles produce a page-level error and suppress results. Overrides do not bypass schema or content-SHA validation. CRM Experiment Feasibility has no bundle; it uses the frozen scenario calculator.

### P3 predictive bundle

`app_data/p3_predictive_v1.json` is an aggregate-safe projection of the exact P3-002, P3-003, P3-004 and P3-005 research outputs. It contains pooled metrics, supported paired intervals, global and period-level SHAP summaries, and calibration summaries; it contains no individual predictions or customer records. Its schema, canonical content checksum and source hashes are checked by `src/p3_predictive_bundle.py`.

To rebuild it, run from the repository root when the reviewed private aggregate files are available in the sibling `source_data/` tree:

```sh
.venv/bin/python -m src.p3_predictive_bundle --build
```

The builder uses explicit source paths and pinned SHA-256 values; it does not search for a newer or similarly named run. It fails on missing or mismatched sources. Tests that need those external sources skip when they are unavailable; tests of the committed bundle continue to run. Rebuilding writes only the app bundle and does not rerun models.

### P3 segmentation bundle

`app_data/p3_segmentation_v1.json` is an aggregate-only allowlisted projection of the exact P3-007 aggregate cited in the research report. Its builder verifies the raw aggregate SHA-256 and sibling manifest SHA-256 before extraction, validates its schema and content checksum, and excludes the private customer-month assignment Parquet. Rebuild it from the exact sibling `source_data/uci_online_retail_ii/p3_007_outputs/` directory with:

```sh
.venv/bin/python -m src.segmentation_bundle --build
```

RFM remains the primary CRM-facing grouping; K-Means k=3 is supplementary exploratory evidence. April–June rates are retrospective outcomes, not calibrated future probabilities. Reviewer-derived April–June AUC diagnostics mentioned in the research report are absent from the verified aggregate source and are not displayed. See [the P3-009C integration report](../docs/research/COMMERCIAL_DS_P3_009C_SEGMENTATION_CRM_INTEGRATION.md) for provenance, results and limitations.

### P3 causal evidence bundle

`app_data/p3_causal_v1.json` is a verified aggregate-only projection of the exact P3-008A audit, P3-008B development, and P3-008C locked-test aggregates, with P3-008D interpretation traceable to its committed synthesis report. The builder pins the raw SHA-256 for each exact source file and verifies the frozen dataset/split hashes. It does not read the raw Hillstrom CSV, the P3-008A split-assignment CSV, the P3-008B development-prediction Parquet, or the P3-008C test-row Parquet. Rebuild when the authorized sibling aggregate sources are available:

```sh
.venv/bin/python -m src.causal_evidence_bundle --build
```

The page labels the primary visit assignment effect as confirmatory locked-test evidence, secondary visit contrasts as Holm-adjusted, and CATE/policy comparisons as exploratory development. Its only development policy-value budget is the verified 20% comparison. No personalized policy was evaluated on the locked test; conversion/spend contrasts were inconclusive. See [the P3-009D integration report](../docs/research/COMMERCIAL_DS_P3_009D_CAUSAL_EVIDENCE_INTEGRATION.md) for hashes, evidence and limitations.

Evidence labels distinguish historical description, historical prediction, development model selection, the previously examined exploratory holdout, retrospective targeting, hypothetical scenarios, confirmatory randomised locked-test evidence, secondary randomised comparisons, and exploratory development policy evaluation. These labels do not make historical results prospective evidence. The underlying retail data are observational and historical, with a partial source endpoint in December 2011. First observed purchase is not verified acquisition; gross merchandise is not net sales, margin or profit; and descriptive groups are not validated CRM segments. Prediction and retrospective targeting metrics measure purchasing patterns, not treatment response. The July–November UCI holdout was previously examined and is exploratory, not untouched confirmation. Random Forest is a development reference, not prospectively validated deployment inference; calibration remains a provisional research candidate, and SHAP is predictive attribution rather than causal importance. Hillstrom is a separate historical experiment and its effects are not assumed to transport to UCI customers. Actual eligibility, consent, contact rules, margin variance and costs are not established. See the root [project README](../README.md) and [data provenance and attribution](../docs/DATA_PROVENANCE.md) for research definitions and source terms.

## Tests

Run the focused application and M4 tests:

```sh
.venv/bin/python -m unittest \
  tests.test_customer_overview_bundle \
  tests.test_dashboard_app \
  tests.test_application_quality \
  tests.test_propensity_summary_bundle \
  tests.test_purchase_propensity_page \
  tests.test_p3_predictive_bundle \
  tests.test_predictive_intelligence_page \
  tests.test_segmentation_bundle \
  tests.test_segmentation_intelligence_page \
  tests.test_causal_evidence_bundle \
  tests.test_causal_evidence_page \
  tests.test_targeting_bundle \
  tests.test_experiment_feasibility_page \
  tests.test_crm_pilot_feasibility
```

Run the full repository suite:

```sh
.venv/bin/python -m unittest discover -s tests
```

Some research-input rebuild tests skip when the external source aggregates are unavailable. They are not needed to run the app or its page tests.

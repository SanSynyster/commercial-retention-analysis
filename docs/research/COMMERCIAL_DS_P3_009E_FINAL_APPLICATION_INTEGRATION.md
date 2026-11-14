# COMMERCIAL_DS_P3_009E — Final Application Integration and Quality

**Base:** P3-009D commit `50f57235d77b889b5f722b3dbda5f7073120e5be`.
**Scope:** Streamlit integration and quality only. No model training, research-result recomputation, or bundle-value changes.

## Integration

The existing seven-page Streamlit application remains the product. A shared page registry defines all seven page objects and is used by the shell and contextual `st.page_link` links between Customer Overview, Segmentation Intelligence and CRM Targeting Explorer. The links target registered page objects rather than hard-coded route URLs.

Segmentation Intelligence and Causal Evidence now support optional `P3_SEGMENTATION_BUNDLE` and `P3_CAUSAL_BUNDLE` paths; existing override names and default paths for the other aggregate pages are preserved. All six bundle-backed pages validate through their established loaders, show page-level errors, and suppress results if a selected bundle cannot be read or fails schema/content-SHA checks. CRM Experiment Feasibility uses no bundle. The two new loaders also convert filesystem read errors into controlled bundle errors.

## Page summary and evidence boundaries

| Page | Function and evidence classification |
|---|---|
| Customer Overview | Historical description of corrected UCI Online Retail II customer aggregates. |
| Purchase Propensity | Historical M1/M2 prediction summaries and provisional exploratory calibration. |
| Predictive Intelligence | Development model selection and previously examined holdout replay; Random Forest remains the development reference. SHAP remains predictive attribution. The holdout explanation caption states its approximate monthly sample and common January–June fitted model; feature IDs have readable labels. |
| Segmentation Intelligence | Historical March RFM descriptions, with RFM primary and K-Means supplementary/exploratory. RFM cutpoints are presented in recency, frequency, monetary order. Subsequent rates are descriptive, not treatment effects. |
| Causal Evidence & Experimentation | Historical design, confirmatory randomised locked-test primary assignment result, Holm-adjusted secondary randomised comparisons, and exploratory development policy evaluation. The Hillstrom population remains distinct from UCI. |
| CRM Targeting Explorer | Retrospective fixed-capacity purchase capture, not causal response or a generated contact list. |
| CRM Experiment Feasibility | Hypothetical M4 planning scenarios, not observed treatment effects or a launched campaign. |

User-facing copy uses British “randomised/randomisation” consistently while preserving evidence classifications and numeric estimands. Causal development policy values identify the eligible experiment-row unit; the expected-random locked-test value identifies its own locked-test population. Historical findings remain clearly separated from present-day CRM states.

## Reliability and testing

Committed aggregate bundles remain the launch inputs; private source research datasets are not needed to start or render the application. The page render functions consume validated aggregates or the fixed M4 scenario calculator. The app does not train models or run research pipelines at startup. Streamlit AppTest exercises the seven-page navigation shell and all seven page views, including the existing page interactions. New quality checks cover the targeting capacity interaction, contextual registered-page links, and valid, missing, malformed-JSON, incorrect-content-SHA and unsupported-schema segmentation/causal overrides.

Final review corrections: the feasibility sensitivity table now styles the British-spelled display DataFrame, so its MDE values render as currency (for example `£8.86`); its underlying values are unchanged. The segmentation application's `load_bundle` now converts filesystem `OSError` failures, including permission errors, to `BundleError`; the page catches that error and shows its controlled bundle-loading message. A deterministic AppTest mock verifies the unreadable-file path. The causal secondary table was inspected: it already uses neutral first-arm/second-arm rate labels, identifies the selected comparison arms, and states that the difference is first arm minus second arm. No causal-page change was needed.

Focused application suite: **80 passed, 1 skipped**. The skip is the existing external-aggregate rebuild test that requires `LOCAL_DATA_DIR`; all committed-bundle and page tests ran. AppTest covered the shell and each of the seven page views, including key selection/capacity interactions and missing, invalid JSON, wrong content SHA and unsupported schema states for both new bundle overrides. Python compilation passed. All six committed aggregate bundle loaders passed schema and content-SHA validation; privacy checks passed and no application view reads `source_data/` or row-level artifacts. `git diff --check` passed.

The predictive, segmentation and causal application bundle content SHAs remained `40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd`, `590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8` and `720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b`, respectively. The Customer Overview, Purchase Propensity and CRM Targeting bundle pins also validated unchanged.

Observed local startup: `streamlit run app/streamlit_app.py --server.headless=true --server.port=8765` started from committed bundles and returned HTTP 200 from the local app endpoint. No private research inputs were required; the app views contain no model fit or research pipeline calls.

## Known limitations and readiness

This remains a local analytical exhibit, not deployment infrastructure. UCI results are observational and historical; the July–November period was previously examined. Hillstrom is a separate historical randomised experiment and does not establish effects for UCI customers or current campaigns. RFM and K-Means do not represent live CRM states. No validated individual treatment-uplift model, customer-level scoring, campaign execution, authentication, deployment or ongoing data refresh is provided.

**Readiness assessment:** the integrated application is ready to serve as the reviewed analytical prototype for P3-010 planning, subject to the test and verification results recorded above. P3-010 should define operational data access, current-customer eligibility, security and deployment requirements before any production use.

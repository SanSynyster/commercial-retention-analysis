# COMMERCIAL_DS_P3_009A — Existing Application Audit and Integration Architecture

**Audit date:** 2026-11-14
**Repository baseline:** `74dee429ffe401824e6a1159d50bb5985f864520`
**Scope:** read-only repository and artifact inventory; no modelling was rerun.

## 1. Existing application and repository

There is already a functional, local **Streamlit** application. It is a four-page research and planning exhibit, not an API-backed product or live CRM tool.

| Area | Implemented evidence | Status |
|---|---|---|
| App shell | `app/streamlit_app.py`, Streamlit multipage navigation | Implemented; four pages registered |
| Historical customer overview | `app/views/customer_overview.py`; reads `app_data/customer_overview_v1.json` through `src/customer_overview_bundle.py` and metrics | Implemented; aggregate descriptive data |
| Purchase propensity | `app/views/purchase_propensity.py`; reads `app_data/propensity_summary_v1.json` | Implemented; M1/M2 summary metrics, monthly results, prior calibration diagnostics |
| Retrospective targeting | `app/views/targeting_explorer.py`; reads `app_data/targeting_v1.json` and `src/targeting_metrics.py` | Implemented; capacity and paired-comparison views, explicitly noncausal |
| Experiment feasibility | `app/views/experiment_feasibility.py`; uses `src/crm_pilot_feasibility.py` and `src/experiment_feasibility_metrics.py` | Implemented; hypothetical scenario calculator, no measured treatment effect |
| Serving/backend | No FastAPI service, application API, model server, or database connection found in the app; README says it makes no network or database calls | No separate backend; local Python process reads bundles |
| Data and artifacts | Three small aggregate JSON bundles in `app_data/`; private and processed data are excluded by `.gitignore` | Existing approved app data are aggregate-only; no P3 customer-level data is part of the app |
| Model inference | Research runners and model classes exist in `src/`; P3 reports say P3-002 saved no fitted model binaries | No packaged P3 inference artifact or application inference interface found |
| Reporting and exploration | Notebooks 01–09, static dashboard image, reports and aggregate-safe research figures | Implemented research/report assets; not interactive P3 application pages |
| Tests and local run | `tests/test_dashboard_app.py` and page/bundle tests; `app/README.md`, `requirements-app.txt`, Makefile | Documented local install, launch, focused/full test commands; no deployment configuration found for this app |

The app runtime stack is Python 3.11, Streamlit 1.66.1, pandas, NumPy, scikit-learn and Altair. Streamlit is pinned in `requirements-app.txt`; Altair is installed transitively and is not independently pinned in repository requirements. The app uses Altair charts and Streamlit tables/metrics. The repository also has SQL/dbt, Spark and Databricks components for analytical pipelines; those are not app-serving infrastructure. No React frontend or separate API exists. P2 M5 integration reports document the current app and its aggregate-only data boundary.

## 2. Reusable analytical outputs and integration readiness

The scientific reports and aggregate figures are committed. P3 aggregate JSON outputs currently exist privately under the sibling `source_data/` tree; they are **not** committed application assets. Customer-level predictions, fit-time intermediates and experiment artifacts also remain outside Git. Their existence does not itself make them an application interface. Across P3-001 through P3-008, reports and figures are the stable, reviewable integration inputs; no P3 model binaries were identified in the repository. P3-001 is a model-recovery inventory milestone, not a reusable P3 model artifact; the legacy churn prediction pipeline uses a different target and is not an equivalent substitute.

### Aggregate source selection and provenance

A P3-009B bundle builder must use explicitly configured source paths for the exact artifacts cited by the corresponding frozen report. It must not discover sources by scanning directories, choosing the newest timestamp, or accepting an arbitrary filename match. When several run directories exist, record the chosen path and verify its digest before extraction. A missing or mismatched source should fail the rebuild clearly rather than silently falling back to another run.

- **P3-002 canonical aggregate:** `../source_data/uci_online_retail_ii/p3_002_outputs/p3_002_aggregate_results.json`; the P3-002 report records SHA-256 `f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb`. This is the raw-file SHA-256 of that named JSON file, also recorded by its sibling `p3_002_manifest.json`. The locally present `p3_002_repro_check/p3_002_aggregate_results.json` and `p3_002_corrected_rerun_a/p3_002_aggregate_results.json` have different raw-file hashes (`f08170380729c5765ee9499e35585921018e967f59f394b2b467ac9edbc4d852` and `1d4953b61182ac3efe103812844ffe5eb617efc7a717736e718a1ebc7f176cb1`, respectively). The report says their scientific aggregate objects match after excluding runtime/timestamp fields; this does not make them interchangeable raw artifacts.
- **P3-008B development aggregate:** the explicit runner filename is `hillstrom_uplift_aggregate_private.json`, under either `../source_data/hillstrom/p3_008b_outputs/` or `../source_data/hillstrom/p3_008b_repro_outputs/`. The P3-008B report records prediction Parquet SHA-256 `986a88b48c0b062d6fc8a65b0bf8f21efb5d2750d43747af68246dd09b10dae3`, reproduced for both runs; this digest is for the private prediction Parquet, **not** either aggregate JSON file. The report does not record an aggregate JSON raw-file digest. Therefore a 009B builder must not treat that prediction hash as validation of the aggregate: add and independently verify an explicit digest for the chosen aggregate source in the 009B bundle provenance before consuming it.
- **P3-008C locked-test aggregate:** the report names `hillstrom_locked_test_aggregate_private.json` under `../source_data/hillstrom/p3_008c_outputs/`; the report identifies this as private aggregate JSON but does not publish its raw-file checksum. If included in 009D/009B bundle work, pin the exact report-cited path and establish a separately reviewed digest/provenance entry before extraction. Never read the private test-row Parquet into the app bundle.

Application bundles must contain aggregate-safe data only. No private customer rows, identifiers, predictions or split assignments enter Git. Rebuild tests should skip gracefully when external private source files are unavailable, while committed application-bundle schema, content-hash and integrity tests continue to run normally against checked-in app assets.

| Research area | Available assets and data structure | Inference/reproduction status | Application suitability and gaps |
|---|---|---|---|
| Recovery inventory (P3-001) | `COMMERCIAL_DS_P3_001_MODEL_RECOVERY_AND_BENCHMARK_READINESS.md` | Inventory only; no reusable P3 model artifact. The existing churn pipeline has a different target | Context for lineage only; not an application scoring asset |
| Purchase propensity (P3-002/003) | Reports `COMMERCIAL_DS_P3_002_ADVANCED_ML_BENCHMARK.md` and `...P3_003_XGBOOST_LIGHTGBM_BENCHMARK.md`; runner modules; development-fold and prior July–November aggregate results; existing app already contains an M1/M2 aggregate summary | RF, HGB, XGBoost and LightGBM were evaluated. RF is the retained development reference; XGBoost/LightGBM did not meet promotion criteria. No P3 fitted models or customer scoring artifact are committed. Runners can reconstruct from private M2 inputs, but are research experiments, not a stable serving API | Add reviewed aggregate comparisons and a clear distinction between selected development reference and exploratory prior-holdout results. New customer scoring requires a separately approved input/data path and packaged, reproducible model pipeline; do not imply current live scores |
| Explainability (P3-004) | `COMMERCIAL_DS_P3_004_SHAP_EXPLAINABILITY.md`, four aggregate-safe figures, aggregate summaries; private row explanations outside Git | SHAP was computed for the accepted RF on fold samples and an exploratory holdout sample; no reusable explainer/model bundle is present | Global importance and aggregate profiles can be shown with correlation and noncausal caveats. Keep individual explanations private unless an approved customer-scoring workflow exists |
| Calibration (P3-005) | `COMMERCIAL_DS_P3_005_CALIBRATION_UNCERTAINTY.md`, three figures and aggregate results; current app already shows earlier M2 calibration context | Intercept-only recalibration was retained as a provisional research candidate, not selected for deployment. Uncalibrated RF remains the reference; no calibrated scoring artifact exists | Present uncalibrated RF as reference and calibration as an evaluated research question, not an operational probability adjustment. Avoid threshold recommendations |
| Future value, timing and count (P3-006) | `COMMERCIAL_DS_P3_006_FUTURE_VALUE_AND_PURCHASE_TIMING.md`, two aggregate-safe figures, private row predictions and aggregate manifest outside Git | Reproducible runner; 30-day primary and limited 60-day results. Monetary comparisons are mixed; Cox timing has short temporal support; count model value is limited. No deployed forecast artifact | Research summary only. Clearly mark forecasts as historical/unvalidated; do not show customer-level forecasts or imply expected revenue/profit |
| Segmentation (P3-007) | `COMMERCIAL_DS_P3_007_ADVANCED_SEGMENTATION.md`, four aggregate-safe figures, private monthly customer assignments and aggregate outputs outside Git | March-fitted preprocessing/model and RFM rules are reconstructible by runner, but no packaged app artifact was found. K-Means k=3 is optional exploratory visualization; RFM remains primary | Aggregate RFM and cluster profiles/stability are suitable. Customer assignments need a separately defined scoring and operational contract; do not claim ML clusters improve purchase discrimination or CRM results beyond RFM |
| Causal inference (P3-008A–D) | Dataset audit/design, uplift benchmark and synthesis reports; three committed P3-008B development figures; locked-test results in the P3-008C report and private aggregate JSON; Hillstrom source data, frozen splits and row outputs are outside Git | Multiple causal learners were fit for development; constant-ATE/random policy remained selected. Locked test confirms Men's-email assignment effect on visits. No test candidate-model diagnostics or deployable uplift model. P3-008C has no committed locked-test figures | An aggregate historical-experiment evidence panel is appropriate. Never expose private Hillstrom test rows or transplant Hillstrom effects/scores to UCI customers. No model is approved for personalized targeting |

Relevant code includes `src/monthly_targeting_policies.py`, `src/monthly_customer_snapshots.py`, `src/monthly_purchase_shap_analysis.py`, `src/monthly_purchase_calibration_experiment.py`, `src/monthly_purchase_value_timing.py`, `src/monthly_customer_segmentation.py`, `src/hillstrom_uplift_models.py`, and `src/hillstrom_locked_test_evaluation.py`. They are research runners/analysis modules; no shared app-facing schema, inference service, model registry or model serialization contract is established.

## 3. Intended users and focused workflows

- **CRM analyst:** review historical customer and RFM profiles, inspect aggregate propensity/targeting performance at fixed capacity, and distinguish purchase likelihood from contact impact. No campaign list export or sending workflow in the first release.
- **Data scientist:** compare frozen model results by temporal fold, inspect calibration and global SHAP summaries, and read experiment provenance/limitations. The first integration should show reviewed aggregates rather than refit models interactively.
- **Marketing analyst:** review Hillstrom assignment effects and fixed-budget policy evidence, including uncertainty and scope. Show the positive historical visit ATE separately from the lack of demonstrated personalized-policy improvement, conversion/revenue evidence, or transportability.

### Evidence labels

Use two dimensions where needed: **analysis type** (what the result describes) and **evaluation status** (how the result was evaluated). They are related but not interchangeable.

| Dimension | Labels | Meaning |
|---|---|---|
| Analysis type | **Historical description**; **Historical prediction**; **Retrospective targeting**; **Hypothetical scenario**; randomized causal analysis | Preserves existing app terminology. Describes the question/result: observed past behavior, prediction of a future outcome, historical ranking/capture, a planning assumption, or an effect of randomized assignment. |
| Evaluation status | **Development — used for model selection**; **Previously examined holdout — exploratory**; **Confirmatory randomised — locked test**; **Secondary randomised analysis — Holm-adjusted where applicable** | Describes the evidence's role and reuse. Development results supported selection; prior holdouts are exploratory; the Hillstrom primary locked test is confirmatory for its prespecified estimand; secondary randomized contrasts/outcomes are a distinct multiplicity-adjusted family. |

Display both dimensions when relevant, for example **Historical prediction · Development (used for model selection)** or **Historical prediction · Previously examined holdout (exploratory)**. The July–November UCI period is a previously examined holdout, never untouched independent confirmation. Hillstrom development learner comparisons are exploratory and are not confirmatory. The Hillstrom locked-test confirmatory classification applies only to the prespecified randomized ATE; secondary randomized analyses must be labeled secondary and report Holm adjustment where applicable.

Every view should keep observed history, model predictions, calibration diagnostics, exploratory comparisons, and randomized assignment effects distinct. Application labels must not imply stronger evidence than the underlying design supports.

## 4. Recommended smallest useful architecture

**Extend the existing Streamlit application.** Repository evidence favors this over introducing a new frontend/backend: the multipage app, bundle validation, aggregate JSON contracts, charting, test harness, dependency pinning, and local run instructions already exist and have passed prior integration checks.

Use the current pattern for the first iteration:

1. A small page module under `app/views/` renders a versioned, aggregate-only JSON bundle.
2. A corresponding loader/validator under `src/` checks schema, provenance and content hash, following `propensity_summary_bundle.py` and `targeting_bundle.py`.
3. A deterministic builder converts only approved report/aggregate inputs into the bundle. It must not load raw customer rows in the app process.
4. Streamlit, pandas and Altair provide the local UI (Streamlit is pinned; Altair is currently transitive); no new API, database, cloud service, authentication layer or model-serving dependency is justified by current use.
5. Reuse the existing unittest/AppTest pattern and run the documented local app health check for integration closure.

The only credible alternative for this scale is a notebook-first or static-report extension. It requires even less code but does not provide the current app's guided analyst workflow or consistent evidence labels. A second web stack/API would duplicate working functionality without a demonstrated multi-user serving need.

**Local run:** the existing command remains `.venv/bin/streamlit run app/streamlit_app.py` after the documented `requirements-app.txt` install. Existing focused app tests are the baseline; add bundle schema/provenance tests and page AppTests as each page lands.

## 5. Proposed pages and milestones

Keep the current four pages. Extend them or add a single “Model Research” page rather than creating a page per model.

| Milestone | User-facing functionality | Reused assets / new components | Acceptance criteria | Dependencies / complexity |
|---|---|---|---|---|
| **P3-009B — Predictive intelligence integration** | Compare logistic C, RF, HGB, XGBoost and LightGBM on temporal development folds; show prior holdout as exploratory; show global RF SHAP, calibration diagnostics and 30-day value/timing summaries with evidence badges | Reuse P3-002–006 reports, safe aggregate JSON/figures, current propensity page and bundle pattern. Add one aggregate builder/validator and a focused page section; no inference model | All displayed metrics reconcile to reviewed reports; development and examined holdout are unmistakably separated; calibration remains diagnostic; SHAP noncausal/correlation caveats visible; future value labeled unvalidated | Must use explicit report-cited source paths and verify report-recorded hashes; where a report lacks an aggregate-file digest, establish a reviewed digest before use. Never auto-select a run directory or use private customer rows/predictions in the builder. Rebuild may skip when private sources are unavailable; committed bundle integrity tests still run. **Medium**; no model fits at app run time |
| **P3-009C — Segmentation and CRM decision support** | Show RFM definitions/profiles as primary framework, optional frozen k=3 profile, transition/stability and fixed-capacity historical targeting comparison | Reuse P3-007 tables/figures and existing CRM Targeting Explorer; add aggregate segment bundle or integrate into an existing page | RFM is primary; k=3 is exploratory; no claim of incremental discrimination or causal campaign value; any capacity metric states the retrospective outcome | Depends on 009B bundle conventions and aggregate summaries. **Small–medium** |
| **P3-009D — Causal evidence and experimentation** | Historical RCT evidence panel: confirmatory Men's email visit ITT and CI, secondary contrasts, expected random 20% value, development learner comparison with intervals; distinguish hypothetical pilot planning | Reuse P3-008D synthesis, 008B/008C aggregates, existing CRM Experiment Feasibility page. Add aggregate-only validated bundle and evidence panel | Primary result, secondary Holm results, and exploratory development policy comparisons are correctly labeled; no test rows/scores; no transport claim; application does not recommend a targeting model | Depends on approved P3-008 aggregate extraction and existing scenario page. **Small–medium** |
| **P3-009E — End-to-end integration and review** | Consistent navigation, evidence labels, source/provenance panel, readable desktop layout and a coherent analyst walkthrough | Integrate 009B–D pages/bundles and current overview/targeting/calculator; add AppTests and documentation | Clean local install/run; all bundles schema/hash validated; page tests pass; totals and uncertainty reconcile to reports; no private customer-level data required by app; screenshots/manual walkthrough review complete | Depends on earlier milestones. **Medium** |

## 6. First vertical slice

Start with a single **Predictive Intelligence** section reachable from the existing Purchase Propensity page:

- Side-by-side aggregate temporal-development results for frozen Logistic C, RF, HGB, XGBoost, LightGBM and frequency ranking, with the previously examined holdout in a separate, clearly exploratory panel.
- Highlight RF as the retained development reference, not as prospectively validated deployment model; include its small/uncertain CRM advantage and customer-cluster uncertainty.
- Show one reviewed global SHAP feature-importance/profile visualization, its fold stability summary, and correlated-feature caveat.
- Show calibration as diagnostics only (no calibration map selected for operational use) and link 30-day value/timing findings as historical research summaries.
- Feed all display values from one versioned, aggregate-only bundle with provenance/hash checks and page tests. Do not score customers or load private row-level artifacts in the page.

This slice demonstrates the application pattern and immediately makes the strongest completed predictive work discoverable. It avoids expanding research and provides a foundation for later segment and experiment panels.

## 7. Data, evidence and scientific limits

- The existing app bundles are aggregate-only and deliberately avoid raw transactions, customer rows, prediction rows, targeting lists and fitted models. Preserve that pattern for the first P3 integration.
- P3-002/003 development fold metrics were involved in model/configuration selection; uncertainty is conditional and not independent future validation. July–November UCI outcomes were previously examined and must remain labeled exploratory.
- RF propensity is probability of purchasing from historical behavior, not probability of responding incrementally to marketing contact. P3-005 did not select a production calibration map.
- P3-006 monetary forecasts and purchase timing are short-history predictive analyses, not validated future revenue or profit estimates.
- P3-007 supports RFM as the primary CRM-facing framework. The k=3 partition is an optional descriptive visualization, with no demonstrated incremental purchase discrimination beyond RFM.
- P3-008 establishes a historical randomized assignment effect on Hillstrom visits, not deployable CATE scores or effects for UCI customers. It does not establish conversion or profit improvement or personalized targeting benefit.
- If later work proposes customer-level inference, it will require a separately scoped input/output contract and approved private data path; it is not a prerequisite for an aggregate research application.

## 8. Recommendation

Proceed by extending the existing Streamlit app with the aggregate-only predictive intelligence vertical slice. Reuse the existing bundle-validation and page-testing conventions, source only reviewed P3 aggregates and figures, and keep inference out of the app until there is a justified customer-level workflow and a packaged artifact. Follow with RFM/decision-support and causal evidence panels, then conduct one end-to-end consistency and usability review. No new framework, service, deployment platform, or modelling research is justified by the inspected repository state.

## 9. Audit verification

- Confirmed starting `HEAD` equals `74dee429ffe401824e6a1159d50bb5985f864520` and the working tree was clean before this report.
- Inspected the app entry point, all four page modules, app README, pinned app dependencies, Makefile, bundle loaders, app tests, Git ignore rules, P2 M5 integration readiness report, P3-001 through P3-008D research reports, and the external `source_data/` directory structure by artifact path only.
- Confirmed the current app uses the three committed JSON bundles under `app_data/`; no P3 fitted model files with joblib/pickle/ONNX extensions were found in the repository.
- No code, model, dataset, prior report, or prior research figure was changed. This audit report is the only intended repository addition.

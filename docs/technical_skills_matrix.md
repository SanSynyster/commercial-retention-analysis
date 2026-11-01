# Technical Skills Matrix

This index maps repository artifacts to the methods they contain. It is a navigation aid, not an independent assessment of correctness or deployment readiness.

| Area | Evidence | Scope |
|---|---|---|
| Transaction processing | `src/cleaning.py`, `src/validation.py`, `docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py` | Earlier reusable pipeline and corrected-V2 research loader |
| Data modeling | `dbt/models/`, `docs/database_schema.md` | Staging, intermediate, and mart models |
| Product analytics | `notebooks/02_retention_analysis.ipynb`, `dbt/models/marts/` | Historical customer metrics and cohort outputs |
| Experiment design | `reports/crm_experiment_design.md`, `docs/product_analytics_experimentation.md` | Simulated readout and measurement design; no randomized effect is established |
| Predictive modeling | `src/churn_prediction.py`, `notebooks/05_second_purchase_propensity_model.ipynb`, `notebooks/06_lapse_risk_model.ipynb` | Earlier exploratory supervised models and validation outputs |
| Distributed processing | `src/spark_pipeline.py`, `databricks/` | Optional Spark pipeline and deployment scaffolding; no cloud deployment is claimed |
| BI reporting | `dashboards/`, `data/bi_exports/`, `docs/dashboard_data_dictionary.md` | Existing dashboard artifacts and BI data definitions |
| Reconciliation and validation | `tests/`, `dbt/tests/`, `docs/recovery/test_COMMERCIAL_DS_*.py` | Synthetic regression tests and data-pinned research checks |
| Source integrity | `docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py`, `docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py` | Frozen source, category, customer, and row-lineage checks |

## Review Path

1. Read the root README and [research status](RESEARCH_STATUS.md).
2. Review [data provenance](DATA_PROVENANCE.md) and [reproduction instructions](REPRODUCIBILITY.md).
3. Follow the [scientific evidence index](recovery/README.md) in order.
4. Inspect the relevant implementation, tests, and independent review together.

Optional local Spark execution requires Java. Databricks validation requires the CLI. Cloud design documents are architectural examples, not deployment evidence.

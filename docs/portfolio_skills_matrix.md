# Portfolio Skills Matrix

## Purpose

This matrix helps recruiters and hiring managers quickly connect the repository assets to the analytics engineering, product analytics, ML, data engineering, and cloud skills demonstrated by the project.

## Skills To Evidence

| Skill Area | Evidence In Repository | What It Demonstrates |
| --- | --- | --- |
| Advanced SQL | `sql/`, `dbt/models/intermediate`, `dbt/models/marts` | Window functions, cohorts, segmentation, CLV-style windows, retention logic |
| dbt | `dbt_project.yml`, `dbt/models`, `dbt/tests`, `profiles/profiles.yml` | Staging/intermediate/mart layering, schema tests, singular tests, reconciliation checks |
| Product Analytics | `mart_retention_cohorts`, `mart_customer_segments`, `mart_customer_metrics` | Lifecycle analysis, repeat behavior, cohort retention, customer concentration |
| A/B Testing | `mart_second_purchase_experiment_*`, `docs/product_analytics_experimentation.md` | Eligibility, deterministic assignment, readout windows, lift, power, net incremental value |
| Churn Prediction | `src/churn_prediction.py`, `src/run_churn_prediction.py`, `docs/ml_churn_prediction.md` | Rolling snapshots, leakage prevention, time-based validation, risk scoring, lift charts |
| Spark | `src/spark_pipeline.py`, `src/run_spark_pipeline.py`, `docs/spark_pipeline.md` | PySpark customer marts, cohorts, deciles, parity validation |
| Databricks | `databricks/`, `src/run_databricks_pipeline.py`, `docs/databricks_support.md` | Asset Bundles, Delta output design, Unity Catalog-compatible table naming |
| Tableau / BI | `dashboards/`, `docs/dashboard_data_dictionary.md`, `docs/dashboard_standards.md` | BI-ready datasets, KPI definitions, dashboard design standards |
| AWS Architecture | `docs/cloud_architecture.md` | S3, Glue, EMR, Redshift/Athena, SageMaker, orchestration design |
| Azure Architecture | `docs/cloud_architecture.md`, `docs/databricks_support.md` | ADLS Gen2, Azure Databricks, Unity Catalog, Azure ML, Databricks Workflows |
| Testing | `tests/test_pipeline.py`, `dbt/tests` | Unit tests, schema checks, revenue reconciliation, experiment validation, output contracts |
| Data Governance | `reports/kpi_definitions.md`, dbt schema docs, validation modules | Metric definitions, financial reconciliation, semantic consistency |

## Five-Minute Reviewer Path

1. Read `README.md` executive summary and reviewer guide section.
2. Open `dbt/models/marts` to inspect SQL analytics depth.
3. Open `src/churn_prediction.py` to inspect ML productionization.
4. Open `src/spark_pipeline.py` and `databricks/` to inspect scalable data engineering.
5. Open `docs/cloud_architecture.md` to understand AWS/Azure deployment thinking.

## Hiring-Manager Talking Points

- The project starts with messy transactional data and turns it into governed customer analytics.
- Core metrics are implemented across Pandas, SQL/dbt, and Spark with reconciliation checks.
- Experimentation is modeled as an operational measurement system, not just a statistical explanation.
- Churn prediction uses rolling snapshots and time-based validation to avoid leakage.
- Databricks support is packaged as deployable infrastructure using Asset Bundles.
- Cloud architecture docs show how to move the local platform to AWS or Azure without changing the analytical definitions.

## Commands Worth Reviewing

```bash
make test
make pipeline-v1
make churn-v1
make dbt-build
make spark-v1
make databricks-validate
```

`make spark-v1` requires a local Java runtime. `make databricks-validate` requires the Databricks CLI. Azure or AWS accounts are not required for local review.

# Reviewer Guide

## Five-Minute Review

Start with these files:

- `README.md` for the business framing, key findings, and run commands.
- `docs/index.md` for the documentation map.
- `docs/portfolio_skills_matrix.md` for the skills-to-assets summary.
- `docs/database_schema.md` for the warehouse ERD and model grain.
- `src/run_pipeline.py` for the reusable Python pipeline entrypoint.
- `dbt/models/marts` for portfolio-grade SQL marts.
- `dbt/tests` for analytics reconciliation and quality checks.
- `dashboards/dashboard_executive_overview.png` for the executive BI story.

Recommended command path:

```bash
make install
make validate
```

For environments without the raw workbook, use `make validate-ci` to run unit tests, docs link checks, and a synthetic end-to-end pipeline fixture.

Optional checks: run `make spark-v1` if Java is installed and `make databricks-validate` if the Databricks CLI is installed.

## Twenty-Minute Review

Review the project as a production analytics platform:

| Area | Evidence |
| --- | --- |
| Advanced SQL | `dbt/models/intermediate`, `dbt/models/marts`, and `sql/` parity queries |
| dbt | `dbt_project.yml`, `profiles/profiles.yml`, schema tests, singular tests |
| Database Schema | `docs/database_schema.md` |
| Product analytics | Cohorts, lifecycle segments, repeat velocity, retention metrics |
| Experimentation | `int_second_purchase_experiment_customers`, `mart_second_purchase_experiment_lift`, `mart_second_purchase_experiment_power`, and `reports/crm_experiment_design.md` |
| Churn and CLV | `mart_customer_churn_clv`, lapse-risk notebook/report |
| ML productionization | `src/churn_prediction.py`, `src/run_churn_prediction.py`, `docs/ml_churn_prediction.md` |
| Spark | `src/spark_pipeline.py`, `src/run_spark_pipeline.py`, `docs/spark_pipeline.md` |
| Databricks | `databricks/databricks.yml`, `databricks/resources/jobs.yml`, `src/run_databricks_pipeline.py`, `docs/databricks_support.md` |
| Cloud Architecture | `docs/cloud_architecture.md` |
| Portfolio Positioning | `docs/portfolio_skills_matrix.md` |
| Tableau readiness | `docs/dashboard_data_dictionary.md`, dashboard assets |
| Reproducibility | Make targets, validation module, unit tests |

## What To Look For

- Metrics reconcile across transaction, order, and customer grains.
- Retention definitions are explicit and tied to identifiable customer revenue.
- Experimentation uses a persistent customer-level assignment concept rather than post-hoc attribution.
- Experiment readouts separate customer-level outcomes, assignment-level metrics, treatment-control lift, and sample-size/power checks.
- Churn prediction uses rolling snapshots, pre-snapshot features, time-based validation, and output schema checks rather than notebook-only modelling.
- Spark is implemented as a scale path for the same governed definitions and includes parity checks against Pandas outputs.
- Databricks support uses Asset Bundles and a notebook wrapper while keeping business logic in reusable source modules.
- Cloud documentation maps the same local project to AWS and Azure production architectures.
- Marts are BI-ready and avoid notebook-only business logic.
- Documentation distinguishes analytical purchase revenue from finance-style net transactional revenue.

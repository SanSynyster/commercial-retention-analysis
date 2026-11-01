# Documentation Index

## Start Here

| Document | Purpose |
|---|---|
| [`README.md`](../README.md) | Project scope, verified findings, limitations, and quick reproduction path |
| [Research status](RESEARCH_STATUS.md) | Milestone status and pending review gates |
| [Reproducibility](REPRODUCIBILITY.md) | Environment, test commands, and local data requirements |
| [Data provenance](DATA_PROVENANCE.md) | Dataset source, attribution, checksums, and release-safety notes |
| [Review guide](reviewer_guide.md) | Suggested technical reading path |
| [Technical skills matrix](technical_skills_matrix.md) | Map from repository components to engineering methods |
| [Database schema](database_schema.md) | dbt warehouse ERD, model grains, and relationships |

## Scientific Evidence

| Document | Purpose |
|---|---|
| [Recovery evidence index](recovery/README.md) | Chronological navigation for audits, decisions, contracts, tests, and reviews |
| [B2B-1 integrity closure](recovery/COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md) | Latest implementation correction; independent re-review pending |
| [Purchase-occasion contract](recovery/COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md) | Eligibility, lineage, and temporal definitions |

## Analytics Engineering

| Document | Purpose |
|---|---|
| [dbt guide](dbt_analytics_engineering.md) | Model layers, tests, and runbook |
| [Dashboard data dictionary](dashboard_data_dictionary.md) | BI-ready dataset definitions |
| [Dashboard standards](dashboard_standards.md) | Dashboard design and formatting guidance |
| [Spark pipeline](spark_pipeline.md) | Optional local Spark processing and parity checks |
| [Databricks support](databricks_support.md) | Deployment scaffolding and configuration support |

## Product Analytics and Modeling

| Document | Purpose |
|---|---|
| [Product analytics experimentation](product_analytics_experimentation.md) | Experiment eligibility, measurement, power, and interpretation limits |
| [Lapse-risk modeling](ml_churn_prediction.md) | Earlier model design and output references |

Reports and notebooks retain earlier analyses. Their outputs should be interpreted under the methodology and data scope documented alongside them; they are not automatically equivalent to corrected-V2 results.

# dbt Analytics Engineering Layer

## Purpose

The dbt layer turns the project from notebook-led analysis into a governed analytics warehouse pattern. It reuses the processed parquet output from the Python pipeline and builds tested DuckDB models for segmentation, cohorts, churn, CLV, and CRM experimentation.

## Architecture

| Layer | Path | Purpose |
| --- | --- | --- |
| Source parquet | `data/processed/v1_online_retail/clean_transactions.parquet` | Governed transaction output from the Python pipeline |
| Staging | `dbt/models/staging` | Typed, snake-case analytical transaction source |
| Intermediate | `dbt/models/intermediate` | Order facts, order ranks, and lifecycle features |
| Marts | `dbt/models/marts` | Customer metrics, cohorts, segments, churn/CLV, experiment eligibility |
| Tests | `dbt/tests` and schema YAML | Revenue reconciliation, accepted values, uniqueness, not-null checks |

## Model Inventory

| Model | Grain | Business Use |
| --- | --- | --- |
| `stg_clean_transactions` | Transaction line | Canonical source for SQL analytics |
| `int_customer_orders` | Customer invoice | Valid customer order fact table |
| `int_customer_order_features` | Customer invoice | Order rank, first/repeat flags, next-order timing |
| `mart_customer_metrics` | Customer | Revenue, AOV, repeat status, recency, second purchase timing |
| `mart_customer_segments` | Customer | Lifecycle segments and CRM priority groups |
| `mart_customer_churn_clv` | Customer | Lapse flag, churn status, historical CLV, recent value windows |
| `mart_retention_cohorts` | Cohort month x month index | BI-ready long-form retention cohorts |
| `mart_experiment_eligibility` | One-time customer | Second-purchase accelerator eligibility and deterministic assignment |
| `int_second_purchase_experiment_customers` | Customer | Experiment frame with eligibility, deterministic assignment, and observed outcomes |
| `mart_second_purchase_experiment_readout` | Window x assignment | Conversion, revenue, and time-to-second-purchase readout |
| `mart_second_purchase_experiment_lift` | Window | Treatment-control lift, economics, and scale decision |
| `mart_second_purchase_experiment_power` | One row | Approximate power check for the configured MDE |
| `mart_customer_revenue_deciles` | Customer decile | Revenue concentration and top-decile dependency |

## Runbook

Create the processed source parquet first:

```bash
make pipeline-v1
```

Build and test dbt:

```bash
make dbt-build
```

Generate dbt docs:

```bash
make dbt-docs
```

By default, dbt reads `data/processed/v1_online_retail/clean_transactions.parquet` and writes the DuckDB warehouse to `data/warehouse/commercial_retention.duckdb`.

To point dbt at another processed dataset:

```bash
.venv/bin/dbt build --profiles-dir profiles --vars '{clean_transactions_path: data/processed/v2_online_retail_ii/clean_transactions.parquet}'
```

## Testing Strategy

The dbt project uses two complementary test layers:

- Schema tests check nullability, uniqueness, accepted values, and stable semantic categories.
- Singular SQL tests verify revenue reconciliation from transaction lines to orders to customer marts, retention percentage bounds, and valid experiment assignments.

These tests are designed for hiring-manager review because they show analytics engineering discipline: governed definitions, model contracts, finance-sensitive reconciliation, and experiment measurement quality gates.

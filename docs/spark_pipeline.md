# Spark Pipeline

## Purpose

The Spark layer demonstrates that the core retention analytics can run as a scalable batch pipeline while preserving the same governed definitions used by Pandas and dbt. It is intentionally built as local PySpark first so it can run in this repository and later move into Databricks with minimal changes.

## Architecture

| Layer | Asset | Purpose |
| --- | --- | --- |
| Input | `data/processed/<dataset>/clean_transactions.parquet` | Governed transaction layer from the Python pipeline |
| Spark job | `src/spark_pipeline.py` | Rebuilds order, customer, decile, and cohort metrics in PySpark |
| CLI | `src/run_spark_pipeline.py` | Dataset-aware Spark entrypoint |
| Outputs | `data/processed/<dataset>/spark/` | Spark-generated marts and parity summary |
| Validation | `spark_parity_summary.csv` | Compares Spark metrics with Pandas outputs |

## Runbook

Generate the processed input first:

```bash
make pipeline-v1
```

Run Spark metrics and parity validation:

```bash
make spark-v1
```

Local Spark execution requires a Java runtime available on `PATH` or through `JAVA_HOME`.

The expanded dataset uses:

```bash
make pipeline-v2
make spark-v2
```

## Outputs

Spark writes these dataset-local outputs:

| Output | Grain |
| --- | --- |
| `spark/customer_orders.parquet` | Customer invoice |
| `spark/customer_metrics.parquet` | Customer |
| `spark/customer_revenue_deciles.csv/` | Revenue decile |
| `spark/retention_cohorts.csv/` | Cohort month x month index |
| `spark/spark_parity_summary.csv` | Parity metric |

## Parity Checks

The Spark pipeline validates these metrics against the existing Pandas outputs:

- Customer count.
- Identifiable customer revenue.
- Repeat customer count.
- Top-decile revenue share.

The parity check exists to prevent the Spark path from becoming a competing definition. Spark is a scale implementation of the same analytics contract.

## Databricks Readiness

The Spark code avoids local-only assumptions except for input and output paths. In Databricks, the same job can be parameterized to read from mounted cloud storage or Unity Catalog tables and write gold marts back to Delta.

Databricks deployment assets are available under `databricks/`, with detailed guidance in `docs/databricks_support.md`.

Recommended Databricks mapping:

| Local Asset | Databricks Equivalent |
| --- | --- |
| `clean_transactions.parquet` | Silver Delta table |
| `customer_metrics.parquet` | Gold customer mart |
| `customer_revenue_deciles.csv` | Gold concentration mart |
| `retention_cohorts.csv` | Gold cohort mart |
| `spark_parity_summary.csv` | Data quality audit table |

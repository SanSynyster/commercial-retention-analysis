from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

import pandas as pd


GOLD_TABLES = {
    "customer_orders": "gold_customer_orders",
    "customer_metrics": "gold_customer_metrics",
    "customer_revenue_deciles": "gold_customer_revenue_deciles",
    "retention_cohorts": "gold_retention_cohorts",
}


def get_spark_session(app_name: str = "commercial-retention-spark"):
    """Create a local Spark session with conservative defaults."""

    java_path = shutil.which("java")
    if not os.environ.get("JAVA_HOME") and java_path is None:
        raise RuntimeError("A Java runtime is required to start local Spark. Install Java or set JAVA_HOME.")
    if java_path is not None:
        java_check = subprocess.run([java_path, "-version"], capture_output=True, text=True, check=False)
        if java_check.returncode != 0:
            raise RuntimeError("A working Java runtime is required to start local Spark. Install Java or set JAVA_HOME.")

    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise ImportError("PySpark is required for Spark pipeline execution. Install pyspark first.") from exc

    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def get_active_or_local_spark(app_name: str = "commercial-retention-spark"):
    """Use an existing Databricks Spark session when available, otherwise create local Spark."""

    try:
        from pyspark.sql import SparkSession

        active_session = SparkSession.getActiveSession()
        if active_session is not None:
            return active_session
    except ImportError:
        pass
    return get_spark_session(app_name)


def qualified_table_name(catalog: str | None, schema: str, table: str) -> str:
    """Build a Unity Catalog-compatible table name."""

    if catalog:
        return f"{catalog}.{schema}.{table}"
    return f"{schema}.{table}"


def build_spark_metric_outputs(spark, clean_transactions_path: str | Path) -> dict[str, object]:
    """Build Spark customer metric outputs from clean transaction parquet."""

    from pyspark.sql import Window
    from pyspark.sql import functions as F

    clean = spark.read.parquet(str(clean_transactions_path))
    valid_lines = clean.where(F.col("is_valid_order_line") == F.lit(True)).select(
        F.col("CustomerID").cast("long").alias("customer_id"),
        F.col("InvoiceNo").cast("string").alias("invoice_no"),
        F.col("InvoiceDate").cast("timestamp").alias("invoice_date"),
        F.col("analytical_revenue").cast("double").alias("analytical_revenue"),
    )

    customer_orders = (
        valid_lines.groupBy("customer_id", "invoice_no")
        .agg(
            F.min("invoice_date").alias("order_date"),
            F.sum("analytical_revenue").alias("order_revenue"),
        )
        .where(F.col("order_revenue") > 0)
    )

    order_window = Window.partitionBy("customer_id").orderBy("order_date", "invoice_no")
    customer_orders = (
        customer_orders.withColumn("order_rank", F.row_number().over(order_window))
        .withColumn("is_first_order", F.col("order_rank") == F.lit(1))
        .withColumn("is_repeat_order", F.col("order_rank") > F.lit(1))
    )

    customer_metrics = (
        customer_orders.groupBy("customer_id")
        .agg(
            F.countDistinct("invoice_no").alias("total_orders"),
            F.sum("order_revenue").alias("revenue"),
            F.min("order_date").alias("first_purchase"),
            F.max("order_date").alias("last_purchase"),
        )
        .withColumn("aov", F.col("revenue") / F.col("total_orders"))
        .withColumn("active_days", F.datediff("last_purchase", "first_purchase"))
        .withColumn("is_repeat_customer", F.col("total_orders") > F.lit(1))
    )

    ranked_customers = customer_metrics.withColumn(
        "customer_rank", F.row_number().over(Window.orderBy(F.desc("revenue"), "customer_id"))
    ).withColumn("customer_decile_number", F.ntile(10).over(Window.orderBy("customer_rank")))

    total_customers = customer_metrics.count()
    total_revenue = customer_metrics.agg(F.sum("revenue").alias("total_revenue")).collect()[0][
        "total_revenue"
    ]
    customer_revenue_deciles = (
        ranked_customers.groupBy("customer_decile_number")
        .agg(F.count("customer_id").alias("customers"), F.sum("revenue").alias("revenue"))
        .withColumn(
            "customer_decile",
            F.expr(
                "case customer_decile_number "
                "when 1 then 'Top 10%' "
                "when 2 then '10-20%' "
                "when 3 then '20-30%' "
                "when 4 then '30-40%' "
                "when 5 then '40-50%' "
                "when 6 then '50-60%' "
                "when 7 then '60-70%' "
                "when 8 then '70-80%' "
                "when 9 then '80-90%' "
                "else 'Bottom 10%' end"
            ),
        )
        .withColumn("customer_pct", F.col("customers") / F.lit(total_customers))
        .withColumn("revenue_pct", F.col("revenue") / F.lit(total_revenue))
        .select("customer_decile", "customers", "revenue", "customer_pct", "revenue_pct")
        .orderBy("customer_decile_number")
    )

    orders_with_months = customer_orders.withColumn(
        "order_month", F.date_trunc("month", "order_date").cast("date")
    )
    cohort_window = Window.partitionBy("customer_id")
    orders_with_months = orders_with_months.withColumn(
        "cohort_month", F.min("order_month").over(cohort_window)
    ).withColumn("month_index", F.months_between("order_month", "cohort_month").cast("int"))

    cohort_counts = (
        orders_with_months.groupBy("cohort_month", "month_index")
        .agg(F.countDistinct("customer_id").alias("customers"))
    )
    cohort_sizes = cohort_counts.where(F.col("month_index") == 0).select(
        "cohort_month", F.col("customers").alias("cohort_size")
    )
    retention_cohorts = (
        cohort_counts.join(cohort_sizes, on="cohort_month", how="inner")
        .withColumn("retention_pct", F.col("customers") / F.col("cohort_size"))
        .orderBy("cohort_month", "month_index")
    )

    return {
        "customer_orders": customer_orders,
        "customer_metrics": customer_metrics,
        "customer_revenue_deciles": customer_revenue_deciles,
        "retention_cohorts": retention_cohorts,
    }


def write_spark_metric_outputs(outputs: dict[str, object], spark_output_dir: str | Path) -> None:
    """Persist Spark outputs under a dataset-local spark directory."""

    output_dir = Path(spark_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs["customer_orders"].write.mode("overwrite").parquet(str(output_dir / "customer_orders.parquet"))
    outputs["customer_metrics"].write.mode("overwrite").parquet(str(output_dir / "customer_metrics.parquet"))
    outputs["customer_revenue_deciles"].coalesce(1).write.mode("overwrite").option("header", True).csv(
        str(output_dir / "customer_revenue_deciles.csv")
    )
    outputs["retention_cohorts"].coalesce(1).write.mode("overwrite").option("header", True).csv(
        str(output_dir / "retention_cohorts.csv")
    )


def write_delta_metric_outputs(
    spark,
    outputs: dict[str, object],
    target_schema: str,
    catalog: str | None = None,
    write_mode: str = "overwrite",
) -> dict[str, str]:
    """Persist Spark outputs to Databricks Delta tables."""

    schema_name = qualified_table_name(catalog, target_schema, "")[:-1]
    spark.sql(f"create schema if not exists {schema_name}")
    written_tables = {}
    for output_name, table_name in GOLD_TABLES.items():
        full_table_name = qualified_table_name(catalog, target_schema, table_name)
        outputs[output_name].write.mode(write_mode).format("delta").saveAsTable(full_table_name)
        written_tables[output_name] = full_table_name
    return written_tables


def validate_delta_outputs(spark, target_schema: str, catalog: str | None = None) -> pd.DataFrame:
    """Run Databricks-compatible quality checks over gold Delta outputs."""

    from pyspark.sql import functions as F

    customer_metrics = spark.table(qualified_table_name(catalog, target_schema, GOLD_TABLES["customer_metrics"]))
    retention_cohorts = spark.table(qualified_table_name(catalog, target_schema, GOLD_TABLES["retention_cohorts"]))
    metrics = customer_metrics.agg(
        F.count("customer_id").alias("customer_count"),
        F.sum("revenue").alias("customer_revenue"),
        F.sum(F.when(F.col("customer_id").isNull(), F.lit(1)).otherwise(F.lit(0))).alias("null_customer_ids"),
    ).collect()[0].asDict()
    retention_bounds = retention_cohorts.where(
        (F.col("retention_pct") < 0) | (F.col("retention_pct") > 1)
    ).count()

    checks = pd.DataFrame(
        [
            {
                "check_name": "customer_count_positive",
                "check_value": float(metrics["customer_count"]),
                "passed": metrics["customer_count"] > 0,
            },
            {
                "check_name": "customer_revenue_positive",
                "check_value": float(metrics["customer_revenue"]),
                "passed": metrics["customer_revenue"] > 0,
            },
            {
                "check_name": "customer_id_not_null",
                "check_value": float(metrics["null_customer_ids"]),
                "passed": metrics["null_customer_ids"] == 0,
            },
            {
                "check_name": "retention_pct_bounds",
                "check_value": float(retention_bounds),
                "passed": retention_bounds == 0,
            },
        ]
    )
    failed = checks[~checks["passed"]]
    if not failed.empty:
        raise ValueError(f"Databricks Delta validation failed: {failed.to_dict(orient='records')}")
    return checks


def read_spark_csv_dir(path: Path) -> pd.DataFrame:
    csv_files = sorted(path.glob("part-*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No Spark CSV part file found in {path}")
    return pd.read_csv(csv_files[0])


def validate_spark_parity(processed_dir: str | Path, tolerance: float = 0.01) -> pd.DataFrame:
    """Compare Spark outputs against existing Pandas pipeline outputs."""

    output_dir = Path(processed_dir)
    spark_dir = output_dir / "spark"
    pandas_customers = pd.read_parquet(output_dir / "customer_metrics.parquet")
    spark_customers = pd.read_parquet(spark_dir / "customer_metrics.parquet")
    pandas_deciles = pd.read_csv(output_dir / "customer_revenue_deciles.csv")
    spark_deciles = read_spark_csv_dir(spark_dir / "customer_revenue_deciles.csv")

    comparisons = [
        {
            "metric": "customer_count",
            "pandas_value": float(len(pandas_customers)),
            "spark_value": float(len(spark_customers)),
        },
        {
            "metric": "identifiable_revenue",
            "pandas_value": float(pandas_customers["revenue"].sum()),
            "spark_value": float(spark_customers["revenue"].sum()),
        },
        {
            "metric": "repeat_customer_count",
            "pandas_value": float(pandas_customers["is_repeat_customer"].sum()),
            "spark_value": float(spark_customers["is_repeat_customer"].sum()),
        },
        {
            "metric": "top_decile_revenue_share",
            "pandas_value": float(
                pandas_deciles.loc[pandas_deciles["customer_decile"] == "Top 10%", "revenue_pct"].iloc[0]
            ),
            "spark_value": float(
                spark_deciles.loc[spark_deciles["customer_decile"] == "Top 10%", "revenue_pct"].iloc[0]
            ),
        },
    ]
    parity = pd.DataFrame(comparisons)
    parity["absolute_difference"] = (parity["pandas_value"] - parity["spark_value"]).abs()
    parity["passed"] = parity["absolute_difference"] <= tolerance
    parity.to_csv(spark_dir / "spark_parity_summary.csv", index=False)
    failed = parity[~parity["passed"]]
    if not failed.empty:
        raise ValueError(f"Spark parity validation failed: {failed.to_dict(orient='records')}")
    return parity


def run_spark_pipeline(processed_dir: str | Path, app_name: str = "commercial-retention-spark") -> pd.DataFrame:
    """Run Spark metrics and validate parity against the Pandas pipeline."""

    output_dir = Path(processed_dir)
    clean_path = output_dir / "clean_transactions.parquet"
    if not clean_path.exists():
        raise FileNotFoundError(f"Processed clean transactions not found: {clean_path}")

    spark = get_spark_session(app_name)
    try:
        outputs = build_spark_metric_outputs(spark, clean_path)
        write_spark_metric_outputs(outputs, output_dir / "spark")
    finally:
        spark.stop()
    return validate_spark_parity(output_dir)


def run_delta_pipeline(
    spark,
    clean_transactions_path: str,
    target_schema: str,
    catalog: str | None = None,
    write_mode: str = "overwrite",
) -> pd.DataFrame:
    """Run Spark metrics and write Databricks Delta gold tables."""

    outputs = build_spark_metric_outputs(spark, clean_transactions_path)
    write_delta_metric_outputs(
        spark,
        outputs,
        target_schema=target_schema,
        catalog=catalog,
        write_mode=write_mode,
    )
    return validate_delta_outputs(spark, target_schema=target_schema, catalog=catalog)

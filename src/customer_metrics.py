from __future__ import annotations

from pathlib import Path

import pandas as pd


def standardize_processed_columns(transactions: pd.DataFrame) -> pd.DataFrame:
    """Convert processed transaction columns to snake_case analytical names."""

    standardized = transactions.copy()
    standardized.columns = standardized.columns.str.strip().str.lower().str.replace(" ", "_")
    return standardized.rename(
        columns={
            "invoiceno": "invoice_no",
            "stockcode": "stock_code",
            "invoicedate": "invoice_date",
            "unitprice": "unit_price",
            "customerid": "customer_id",
        }
    )


def build_customer_orders(clean_transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate valid order lines to customer invoice-level orders."""

    transactions = standardize_processed_columns(clean_transactions)
    required_columns = {
        "invoice_no",
        "invoice_date",
        "customer_id",
        "is_valid_order_line",
        "analytical_revenue",
    }
    missing_columns = sorted(required_columns - set(transactions.columns))
    if missing_columns:
        raise ValueError(f"Processed transaction data is missing columns: {missing_columns}")

    transactions["invoice_date"] = pd.to_datetime(transactions["invoice_date"])
    valid_lines = transactions[transactions["is_valid_order_line"]].copy()
    customer_orders = (
        valid_lines.groupby(["customer_id", "invoice_no"], as_index=False)
        .agg(order_date=("invoice_date", "min"), order_revenue=("analytical_revenue", "sum"))
    )
    customer_orders = customer_orders[customer_orders["order_revenue"] > 0].copy()
    customer_orders = customer_orders.sort_values(
        ["customer_id", "order_date", "invoice_no"]
    ).reset_index(drop=True)
    customer_orders["order_rank"] = customer_orders.groupby("customer_id").cumcount() + 1
    customer_orders["is_first_order"] = customer_orders["order_rank"] == 1
    customer_orders["is_repeat_order"] = customer_orders["order_rank"] > 1
    return customer_orders


def build_customer_metrics(customer_orders: pd.DataFrame) -> pd.DataFrame:
    """Build the customer-level retention metric layer."""

    customer_metrics = (
        customer_orders.groupby("customer_id", as_index=False)
        .agg(
            total_orders=("invoice_no", "nunique"),
            revenue=("order_revenue", "sum"),
            first_purchase=("order_date", "min"),
            last_purchase=("order_date", "max"),
        )
    )
    customer_metrics["aov"] = customer_metrics["revenue"] / customer_metrics["total_orders"]
    customer_metrics["active_days"] = (
        customer_metrics["last_purchase"] - customer_metrics["first_purchase"]
    ).dt.days
    customer_metrics["is_repeat_customer"] = customer_metrics["total_orders"] > 1
    return customer_metrics


def build_lifecycle_revenue_split(customer_orders: pd.DataFrame, customer_metrics: pd.DataFrame) -> pd.DataFrame:
    """Split identifiable revenue into first/repeat order and customer lifecycle views."""

    first_order_revenue = customer_orders.loc[customer_orders["is_first_order"], "order_revenue"].sum()
    repeat_order_revenue = customer_orders.loc[customer_orders["is_repeat_order"], "order_revenue"].sum()
    one_time_customers = customer_metrics.loc[
        ~customer_metrics["is_repeat_customer"], "customer_id"
    ]
    repeat_customers = customer_metrics.loc[
        customer_metrics["is_repeat_customer"], "customer_id"
    ]
    one_time_revenue = customer_orders.loc[
        customer_orders["customer_id"].isin(one_time_customers), "order_revenue"
    ].sum()
    repeat_customer_revenue = customer_orders.loc[
        customer_orders["customer_id"].isin(repeat_customers), "order_revenue"
    ].sum()
    lifecycle = pd.DataFrame(
        {
            "metric": [
                "first_order_revenue",
                "repeat_order_revenue",
                "one_time_customer_revenue",
                "repeat_customer_revenue",
            ],
            "value": [
                first_order_revenue,
                repeat_order_revenue,
                one_time_revenue,
                repeat_customer_revenue,
            ],
        }
    )
    lifecycle["share_of_identifiable_revenue"] = (
        lifecycle["value"] / customer_orders["order_revenue"].sum()
    )
    return lifecycle


def build_customer_revenue_deciles(customer_metrics: pd.DataFrame) -> pd.DataFrame:
    """Rank customers into revenue deciles."""

    ranked = customer_metrics.sort_values("revenue", ascending=False).copy()
    ranked["rank"] = range(1, len(ranked) + 1)
    decile_labels = [
        "Top 10%",
        "10-20%",
        "20-30%",
        "30-40%",
        "40-50%",
        "50-60%",
        "60-70%",
        "70-80%",
        "80-90%",
        "Bottom 10%",
    ]
    if len(ranked) < 10:
        ranked["customer_decile"] = "Top 10%"
    else:
        ranked["customer_decile"] = pd.qcut(ranked["rank"], 10, labels=decile_labels)
    deciles = (
        ranked.groupby("customer_decile", observed=False)
        .agg(customers=("customer_id", "count"), revenue=("revenue", "sum"))
        .reset_index()
    )
    deciles["customer_pct"] = deciles["customers"] / len(ranked)
    deciles["revenue_pct"] = deciles["revenue"] / ranked["revenue"].sum()
    return deciles


def build_retention_matrix(customer_orders: pd.DataFrame) -> pd.DataFrame:
    """Create monthly acquisition cohort retention matrix."""

    orders = customer_orders.copy()
    orders["order_month"] = orders["order_date"].dt.to_period("M")
    first_purchase_month = orders.groupby("customer_id")["order_month"].min().rename("cohort_month")
    orders = orders.merge(first_purchase_month, on="customer_id", how="left")
    orders["month_index"] = orders["order_month"].astype(int) - orders["cohort_month"].astype(int)
    cohort_counts = (
        orders.groupby(["cohort_month", "month_index"], observed=False)
        .agg(customers=("customer_id", "nunique"))
        .reset_index()
    )
    cohort_sizes = cohort_counts[cohort_counts["month_index"] == 0][
        ["cohort_month", "customers"]
    ].rename(columns={"customers": "cohort_size"})
    retention = cohort_counts.merge(cohort_sizes, on="cohort_month", how="left")
    retention["retention_pct"] = retention["customers"] / retention["cohort_size"]
    return retention.pivot_table(index="cohort_month", columns="month_index", values="retention_pct")


def build_customer_metric_outputs(clean_transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build all customer metric outputs generated by the retention notebook."""

    orders = build_customer_orders(clean_transactions)
    metrics = build_customer_metrics(orders)
    lifecycle = build_lifecycle_revenue_split(orders, metrics)
    deciles = build_customer_revenue_deciles(metrics)
    retention_matrix = build_retention_matrix(orders)
    return {
        "customer_orders": orders,
        "customer_metrics": metrics,
        "customer_lifecycle_revenue_split": lifecycle,
        "customer_revenue_deciles": deciles,
        "retention_matrix": retention_matrix,
    }


def write_customer_metric_outputs(outputs: dict[str, pd.DataFrame], processed_dir: str | Path) -> None:
    """Persist customer metric outputs to the processed directory."""

    output_dir = Path(processed_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs["customer_metrics"].to_parquet(output_dir / "customer_metrics.parquet", index=False)
    outputs["customer_lifecycle_revenue_split"].to_csv(
        output_dir / "customer_lifecycle_revenue_split.csv", index=False
    )
    outputs["customer_revenue_deciles"].to_csv(output_dir / "customer_revenue_deciles.csv", index=False)
    outputs["retention_matrix"].to_csv(output_dir / "retention_matrix.csv")

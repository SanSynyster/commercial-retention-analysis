from __future__ import annotations

from pathlib import Path

import pandas as pd


EXPECTED_CLEAN_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
    "line_revenue_gross",
    "is_valid_order_line",
    "analytical_revenue",
}

EXPECTED_CUSTOMER_METRIC_COLUMNS = {
    "customer_id",
    "total_orders",
    "revenue",
    "first_purchase",
    "last_purchase",
    "aov",
    "active_days",
    "is_repeat_customer",
}

EXPECTED_OUTPUT_COLUMNS = {
    "clean_transactions.parquet": EXPECTED_CLEAN_COLUMNS,
    "data_audit_summary.csv": {"metric", "value"},
    "customer_metrics.parquet": EXPECTED_CUSTOMER_METRIC_COLUMNS,
    "customer_lifecycle_revenue_split.csv": {
        "metric",
        "value",
        "share_of_identifiable_revenue",
    },
    "customer_revenue_deciles.csv": {
        "customer_decile",
        "customers",
        "revenue",
        "customer_pct",
        "revenue_pct",
    },
}


def read_output(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def validate_expected_columns(frame: pd.DataFrame, expected_columns: set[str], label: str) -> None:
    missing_columns = sorted(expected_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(f"{label} is missing columns: {missing_columns}")


def validate_output_files(processed_dir: str | Path) -> None:
    """Validate core pipeline outputs exist and contain expected columns."""

    output_dir = Path(processed_dir)
    for file_name, expected_columns in EXPECTED_OUTPUT_COLUMNS.items():
        path = output_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Expected output was not created: {path}")
        output = read_output(path)
        validate_expected_columns(output, expected_columns, file_name)


def validate_revenue_reconciliation(processed_dir: str | Path, tolerance: float = 1e-6) -> None:
    """Validate core revenue audit formulas reconcile."""

    audit = pd.read_csv(Path(processed_dir) / "data_audit_summary.csv").set_index("metric")["value"]
    gross = float(audit.loc["gross_purchase_revenue"])
    refunds = float(audit.loc["cancelled_refund_revenue"])
    net = float(audit.loc["net_transactional_revenue"])
    identifiable = float(audit.loc["identifiable_customer_revenue"])
    identifiable_pct = float(audit.loc["identifiable_revenue_pct"])

    if abs((gross + refunds) - net) > tolerance:
        raise ValueError("Net transactional revenue does not equal gross purchase revenue plus refunds.")
    if abs((identifiable / gross * 100) - identifiable_pct) > tolerance:
        raise ValueError("Identifiable revenue percentage does not reconcile to audit revenue values.")


def validate_customer_metrics(processed_dir: str | Path) -> None:
    """Validate customer metric outputs do not contain invalid critical values."""

    customers = pd.read_parquet(Path(processed_dir) / "customer_metrics.parquet")
    validate_expected_columns(customers, EXPECTED_CUSTOMER_METRIC_COLUMNS, "customer_metrics.parquet")
    critical_columns = ["customer_id", "total_orders", "revenue", "first_purchase", "last_purchase", "aov"]
    missing_counts = customers[critical_columns].isna().sum()
    failed = missing_counts[missing_counts > 0]
    if not failed.empty:
        raise ValueError(f"Customer metrics contain missing critical values: {failed.to_dict()}")
    if (customers["total_orders"] <= 0).any():
        raise ValueError("Customer metrics contain non-positive total order counts.")
    if (customers["revenue"] <= 0).any():
        raise ValueError("Customer metrics contain non-positive revenue values.")


def validate_pipeline_outputs(processed_dir: str | Path) -> None:
    """Run all lightweight validations for core pipeline outputs."""

    validate_output_files(processed_dir)
    validate_revenue_reconciliation(processed_dir)
    validate_customer_metrics(processed_dir)


def validate_v2_contains_v1(raw_v1_path: str | Path, raw_v2_path: str | Path) -> dict[str, float]:
    """Validate the expanded V2 raw dataset contains all rows from the V1 baseline."""

    v1 = pd.read_excel(raw_v1_path)
    v2 = pd.read_csv(raw_v2_path).rename(
        columns={"Invoice": "InvoiceNo", "Price": "UnitPrice", "Customer ID": "CustomerID"}
    )
    columns = [
        "InvoiceNo",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "CustomerID",
        "Country",
    ]
    for frame in [v1, v2]:
        frame["InvoiceNo"] = frame["InvoiceNo"].astype(str)
        frame["StockCode"] = frame["StockCode"].astype(str)
        frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"])
        frame["Description"] = frame["Description"].astype("string").fillna("<NA>")
        frame["CustomerID"] = frame["CustomerID"].fillna(-1).astype(float).astype(int)

    v1_counts = v1.groupby(columns, dropna=False).size().rename("v1_count").reset_index()
    v2_counts = v2.groupby(columns, dropna=False).size().rename("v2_count").reset_index()
    overlap = v1_counts.merge(v2_counts, on=columns, how="left")
    overlap["v2_count"] = overlap["v2_count"].fillna(0).astype(int)
    overlap["matched_rows"] = overlap[["v1_count", "v2_count"]].min(axis=1)
    matched_rows = int(overlap["matched_rows"].sum())
    matched_pct = matched_rows / len(v1)
    if matched_rows != len(v1):
        raise ValueError(f"V2 does not contain all V1 rows: matched {matched_rows:,} of {len(v1):,}.")
    return {"v1_rows": float(len(v1)), "v2_rows": float(len(v2)), "matched_pct": matched_pct}

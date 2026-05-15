from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_TRANSACTION_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
    "line_revenue_gross",
    "is_cancelled_invoice",
    "is_refund_or_return",
    "is_positive_purchase",
    "is_identified_customer",
    "exclusion_reason",
    "is_valid_order_line",
    "analytical_revenue",
}


def build_clean_transactions(raw_transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the transaction-level analytical layer and audit summary."""

    clean_transactions = raw_transactions.copy()
    clean_transactions["InvoiceDate"] = pd.to_datetime(clean_transactions["InvoiceDate"])
    clean_transactions["line_revenue_gross"] = (
        clean_transactions["Quantity"] * clean_transactions["UnitPrice"]
    )
    clean_transactions["is_cancelled_invoice"] = clean_transactions["InvoiceNo"].astype(str).str.startswith("C")
    clean_transactions["is_refund_or_return"] = (
        (clean_transactions["Quantity"] < 0) | clean_transactions["is_cancelled_invoice"]
    )
    clean_transactions["is_positive_purchase"] = (
        (clean_transactions["Quantity"] > 0)
        & (clean_transactions["UnitPrice"] > 0)
        & ~clean_transactions["is_cancelled_invoice"]
    )
    clean_transactions["is_identified_customer"] = clean_transactions["CustomerID"].notna()
    clean_transactions["exclusion_reason"] = np.select(
        [
            clean_transactions["is_cancelled_invoice"],
            clean_transactions["Quantity"] < 0,
            clean_transactions["UnitPrice"] <= 0,
            clean_transactions["CustomerID"].isna(),
        ],
        [
            "cancelled_invoice",
            "negative_quantity",
            "non_positive_unit_price",
            "missing_customer_id",
        ],
        default="valid_order_line",
    )
    clean_transactions["is_valid_order_line"] = (
        clean_transactions["is_positive_purchase"] & clean_transactions["is_identified_customer"]
    )
    clean_transactions["analytical_revenue"] = np.where(
        clean_transactions["is_valid_order_line"],
        clean_transactions["line_revenue_gross"],
        0.0,
    )

    audit_summary = build_audit_summary(clean_transactions)
    return prepare_for_parquet(clean_transactions), audit_summary


def build_audit_summary(clean_transactions: pd.DataFrame) -> pd.DataFrame:
    """Create finance and customer-level audit metrics from clean transactions."""

    total_rows = len(clean_transactions)
    duplicate_rows = int(clean_transactions.duplicated().sum())
    missing_customer_pct = clean_transactions["CustomerID"].isna().mean() * 100
    gross_purchase_revenue = clean_transactions.loc[
        clean_transactions["is_positive_purchase"], "line_revenue_gross"
    ].sum()
    cancelled_refund_revenue = clean_transactions.loc[
        clean_transactions["is_refund_or_return"], "line_revenue_gross"
    ].sum()
    net_transactional_revenue = gross_purchase_revenue + cancelled_refund_revenue
    analytical_purchase_revenue = gross_purchase_revenue
    identifiable_customer_revenue = clean_transactions.loc[
        clean_transactions["is_valid_order_line"], "line_revenue_gross"
    ].sum()
    identifiable_revenue_pct = identifiable_customer_revenue / analytical_purchase_revenue * 100
    valid_customers = clean_transactions.loc[
        clean_transactions["is_valid_order_line"], "CustomerID"
    ].nunique()
    valid_orders = clean_transactions.loc[
        clean_transactions["is_valid_order_line"], "InvoiceNo"
    ].nunique()

    return pd.DataFrame(
        {
            "metric": [
                "total_rows",
                "duplicate_rows",
                "missing_customer_pct",
                "gross_purchase_revenue",
                "cancelled_refund_revenue",
                "net_transactional_revenue",
                "analytical_purchase_revenue",
                "identifiable_customer_revenue",
                "identifiable_revenue_pct",
                "valid_customers",
                "valid_orders",
            ],
            "value": [
                total_rows,
                duplicate_rows,
                missing_customer_pct,
                gross_purchase_revenue,
                cancelled_refund_revenue,
                net_transactional_revenue,
                analytical_purchase_revenue,
                identifiable_customer_revenue,
                identifiable_revenue_pct,
                valid_customers,
                valid_orders,
            ],
        }
    )


def prepare_for_parquet(clean_transactions: pd.DataFrame) -> pd.DataFrame:
    """Cast mixed object columns before stable parquet serialization."""

    prepared = clean_transactions.copy()
    prepared["InvoiceNo"] = prepared["InvoiceNo"].astype(str)
    prepared["StockCode"] = prepared["StockCode"].astype(str)
    prepared["Description"] = prepared["Description"].astype("string")
    prepared["Country"] = prepared["Country"].astype("string")
    prepared["exclusion_reason"] = prepared["exclusion_reason"].astype("string")
    prepared["CustomerID"] = prepared["CustomerID"].astype("Int64")
    return prepared


def write_clean_outputs(clean_transactions: pd.DataFrame, audit_summary: pd.DataFrame, processed_dir: str | Path) -> None:
    """Persist cleaned transaction and audit outputs."""

    output_dir = Path(processed_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_transactions.to_parquet(output_dir / "clean_transactions.parquet", index=False)
    audit_summary.to_csv(output_dir / "data_audit_summary.csv", index=False)

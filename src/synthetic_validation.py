from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from src.cleaning import build_clean_transactions, write_clean_outputs
from src.churn_prediction import ChurnModelConfig, build_lapse_snapshot_features, build_order_features
from src.customer_metrics import build_customer_metric_outputs, write_customer_metric_outputs
from src.validation import validate_pipeline_outputs


def build_synthetic_transactions() -> pd.DataFrame:
    """Create a small deterministic fixture covering repeat, lapse, invalid, and anonymous rows."""

    return pd.DataFrame(
        {
            "InvoiceNo": [
                "100",
                "101",
                "102",
                "200",
                "201",
                "300",
                "301",
                "302",
                "C400",
                "500",
            ],
            "StockCode": ["A", "A", "A", "B", "B", "C", "C", "C", "D", "E"],
            "Description": ["Alpha", "Alpha", "Alpha", "Beta", "Beta", "Gamma", "Gamma", "Gamma", "Delta", "Echo"],
            "Quantity": [1, 2, 1, 1, 1, 1, 1, 2, -1, 1],
            "InvoiceDate": [
                "2011-01-01",
                "2011-02-01",
                "2011-06-01",
                "2011-01-15",
                "2011-03-15",
                "2011-01-20",
                "2011-04-20",
                "2011-08-20",
                "2011-02-01",
                "2011-05-01",
            ],
            "UnitPrice": [10.0, 12.0, 15.0, 20.0, 22.0, 8.0, 9.0, 10.0, 5.0, 99.0],
            "CustomerID": [1, 1, 1, 2, 2, 3, 3, 3, 4, None],
            "Country": ["United Kingdom"] * 10,
        }
    )


def run_synthetic_validation(output_dir: str | Path | None = None) -> dict[str, float]:
    """Run a CI-safe end-to-end validation over a synthetic transaction fixture."""

    raw = build_synthetic_transactions()
    clean, audit = build_clean_transactions(raw)
    metric_outputs = build_customer_metric_outputs(clean)

    if output_dir is None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            return _write_and_validate(clean, audit, metric_outputs, Path(tmp_dir))
    return _write_and_validate(clean, audit, metric_outputs, Path(output_dir))


def _write_and_validate(
    clean: pd.DataFrame,
    audit: pd.DataFrame,
    metric_outputs: dict[str, pd.DataFrame],
    output_dir: Path,
) -> dict[str, float]:
    write_clean_outputs(clean, audit, output_dir)
    write_customer_metric_outputs(metric_outputs, output_dir)
    validate_pipeline_outputs(output_dir)

    orders = build_order_features(clean)
    snapshots = build_lapse_snapshot_features(
        orders,
        ChurnModelConfig(target_window_days=90, min_history_months=2),
    )
    if snapshots.empty:
        raise ValueError("Synthetic churn snapshot validation produced no rows.")
    if snapshots["lapsed_next_90_days"].nunique() < 2:
        raise ValueError("Synthetic churn target should contain both lapsed and retained examples.")

    customers = metric_outputs["customer_metrics"]
    result = {
        "clean_rows": float(len(clean)),
        "valid_order_lines": float(clean["is_valid_order_line"].sum()),
        "customers": float(len(customers)),
        "customer_revenue": float(customers["revenue"].sum()),
        "snapshot_rows": float(len(snapshots)),
        "snapshot_target_rate": float(snapshots["lapsed_next_90_days"].mean()),
    }
    if result["customers"] != 3:
        raise ValueError(f"Expected 3 valid synthetic customers, got {result['customers']}")
    if result["valid_order_lines"] != 8:
        raise ValueError(f"Expected 8 valid synthetic order lines, got {result['valid_order_lines']}")
    return result


def main() -> None:
    result = run_synthetic_validation()
    print("Synthetic validation passed.")
    for metric, value in result.items():
        print(f"{metric}: {value}")


if __name__ == "__main__":
    main()

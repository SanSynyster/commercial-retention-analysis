from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.cleaning import build_clean_transactions, write_clean_outputs
from src.config import PROJECT_ROOT
from src.customer_metrics import build_customer_metric_outputs, write_customer_metric_outputs
from src.data_loading import load_raw_transactions
from src.validation import (
    validate_customer_metrics,
    validate_expected_columns,
    validate_output_files,
    validate_pipeline_outputs,
    validate_revenue_reconciliation,
    validate_v2_contains_v1,
)


def sample_raw_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "InvoiceNo": ["100", "100", "101", "C102", "103", "104"],
            "StockCode": ["A", "B", "A", "A", "C", "D"],
            "Description": ["Alpha", "Beta", "Alpha", "Alpha", "Gamma", "Delta"],
            "Quantity": [2, 1, 1, -1, 1, 3],
            "InvoiceDate": [
                "2011-01-01",
                "2011-01-01",
                "2011-02-01",
                "2011-02-15",
                "2011-03-01",
                "2011-04-01",
            ],
            "UnitPrice": [10.0, 5.0, 10.0, 10.0, 0.0, 2.0],
            "CustomerID": [1, 1, 1, 1, 2, None],
            "Country": ["United Kingdom"] * 6,
        }
    )


class PipelineTests(unittest.TestCase):
    def test_cleaning_flags_and_revenue_reconcile(self) -> None:
        clean, audit = build_clean_transactions(sample_raw_transactions())

        self.assertEqual(len(clean), 6)
        self.assertEqual(int(clean["is_valid_order_line"].sum()), 3)
        self.assertEqual(float(audit.set_index("metric").loc["gross_purchase_revenue", "value"]), 41.0)
        self.assertEqual(float(audit.set_index("metric").loc["net_transactional_revenue", "value"]), 31.0)

    def test_customer_metric_outputs_and_validation(self) -> None:
        clean, audit = build_clean_transactions(sample_raw_transactions())
        outputs = build_customer_metric_outputs(clean)

        customers = outputs["customer_metrics"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(int(customers.loc[0, "total_orders"]), 2)
        self.assertAlmostEqual(float(customers.loc[0, "revenue"]), 35.0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            write_clean_outputs(clean, audit, output_dir)
            write_customer_metric_outputs(outputs, output_dir)
            validate_output_files(output_dir)
            validate_revenue_reconciliation(output_dir)
            validate_customer_metrics(output_dir)
            validate_pipeline_outputs(output_dir)

    def test_raw_loader_maps_v2_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw_path = Path(tmp_dir) / "raw.csv"
            pd.DataFrame(
                {
                    "Invoice": ["100"],
                    "StockCode": ["A"],
                    "Description": ["Alpha"],
                    "Quantity": [1],
                    "InvoiceDate": ["2011-01-01"],
                    "Price": [10.0],
                    "Customer ID": [1],
                    "Country": ["United Kingdom"],
                }
            ).to_csv(raw_path, index=False)

            loaded = load_raw_transactions(raw_path)
            self.assertIn("InvoiceNo", loaded.columns)
            self.assertIn("UnitPrice", loaded.columns)
            self.assertIn("CustomerID", loaded.columns)

    def test_expected_column_validation_fails_on_missing_column(self) -> None:
        with self.assertRaises(ValueError):
            validate_expected_columns(pd.DataFrame({"a": [1]}), {"a", "b"}, "test_frame")

    def test_v2_contains_v1_when_raw_files_are_available(self) -> None:
        raw_v1 = PROJECT_ROOT / "data" / "raw" / "Online Retail.xlsx"
        raw_v2 = PROJECT_ROOT / "data" / "raw" / "online_retail_II.csv"
        if not raw_v1.exists() or not raw_v2.exists():
            self.skipTest("Raw V1/V2 files are not available locally.")

        result = validate_v2_contains_v1(raw_v1, raw_v2)
        self.assertEqual(result["matched_pct"], 1.0)


if __name__ == "__main__":
    unittest.main()

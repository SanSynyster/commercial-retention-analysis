from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.cleaning import build_clean_transactions, write_clean_outputs
from src.churn_prediction import (
    ChurnModelConfig,
    build_lapse_snapshot_features,
    build_order_features,
)
from src.config import PROJECT_ROOT
from src.customer_metrics import build_customer_metric_outputs, write_customer_metric_outputs
from src.data_loading import load_raw_transactions
from src.docs_validation import extract_local_links, validate_markdown_links
from src.spark_pipeline import build_spark_metric_outputs, get_spark_session
from src.spark_pipeline import qualified_table_name
from src.synthetic_validation import run_synthetic_validation
from src.validation import (
    validate_lapse_risk_outputs,
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


def sample_churn_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "InvoiceNo": ["100", "101", "102", "200", "201", "300", "301", "302"],
            "StockCode": ["A"] * 8,
            "Description": ["Alpha"] * 8,
            "Quantity": [1] * 8,
            "InvoiceDate": [
                "2011-01-01",
                "2011-02-01",
                "2011-06-01",
                "2011-01-15",
                "2011-03-15",
                "2011-01-20",
                "2011-04-20",
                "2011-08-20",
            ],
            "UnitPrice": [10.0, 12.0, 15.0, 20.0, 22.0, 8.0, 9.0, 10.0],
            "CustomerID": [1, 1, 1, 2, 2, 3, 3, 3],
            "Country": ["United Kingdom"] * 8,
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

    def test_lapse_snapshots_use_only_pre_snapshot_history(self) -> None:
        clean, _ = build_clean_transactions(sample_churn_transactions())
        orders = build_order_features(clean)
        snapshots = build_lapse_snapshot_features(
            orders,
            ChurnModelConfig(target_window_days=90, min_history_months=2),
        )

        snapshot = snapshots[
            (snapshots["customer_id"] == 2)
            & (snapshots["snapshot_date"] == pd.Timestamp("2011-03-01"))
        ].iloc[0]

        self.assertEqual(int(snapshot["total_orders"]), 1)
        self.assertAlmostEqual(float(snapshot["revenue"]), 20.0)
        self.assertEqual(int(snapshot["lapsed_next_90_days"]), 0)

    def test_lapse_snapshot_marks_no_future_purchase_as_lapsed(self) -> None:
        clean, _ = build_clean_transactions(sample_churn_transactions())
        orders = build_order_features(clean)
        snapshots = build_lapse_snapshot_features(
            orders,
            ChurnModelConfig(target_window_days=90, min_history_months=2),
        )

        snapshot = snapshots[
            (snapshots["customer_id"] == 2)
            & (snapshots["snapshot_date"] == pd.Timestamp("2011-04-01"))
        ].iloc[0]

        self.assertEqual(int(snapshot["total_orders"]), 2)
        self.assertEqual(int(snapshot["lapsed_next_90_days"]), 1)

    def test_lapse_risk_output_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            pd.DataFrame(
                {
                    "model": ["Test Model"],
                    "train_rows": [10],
                    "test_rows": [5],
                    "split_snapshot": ["2011-06-01"],
                    "test_target_rate": [0.4],
                    "roc_auc": [0.7],
                    "pr_auc": [0.6],
                    "precision_top_10pct": [1.0],
                    "precision_top_20pct": [0.8],
                    "brier_score": [0.2],
                }
            ).to_csv(output_dir / "lapse_risk_model_metrics.csv", index=False)
            pd.DataFrame(
                {
                    "customer_id": [1],
                    "snapshot_date": ["2011-06-01"],
                    "lapse_risk_score": [0.7],
                    "risk_band": ["High risk"],
                    "lapsed_next_90_days": [1],
                    "recency_days": [45],
                    "total_orders": [2],
                    "revenue": [100.0],
                    "is_high_value": [1],
                    "data_split": ["test"],
                }
            ).to_csv(output_dir / "lapse_risk_scores.csv", index=False)
            pd.DataFrame(
                {
                    "risk_decile": ["Top 10%"],
                    "customers": [1],
                    "observed_lapse_rate": [1.0],
                    "avg_risk_score": [0.7],
                    "high_value_customers": [1],
                    "lift_vs_test_average": [1.0],
                }
            ).to_csv(output_dir / "lapse_risk_lift.csv", index=False)
            pd.DataFrame(
                {"feature": ["recency_days"], "importance": [0.1], "importance_std": [0.01]}
            ).to_csv(output_dir / "lapse_risk_feature_importance.csv", index=False)

            validate_lapse_risk_outputs(output_dir)

    def test_spark_customer_metrics_match_sample_pipeline(self) -> None:
        try:
            spark = get_spark_session("commercial-retention-test")
        except ImportError:
            self.skipTest("PySpark is not installed.")
        except Exception as exc:
            if "JAVA_GATEWAY_EXITED" in str(exc) or "Java Runtime" in str(exc) or "Java runtime" in str(exc):
                self.skipTest("A Java runtime is required to start local Spark.")
            raise

        clean, _ = build_clean_transactions(sample_raw_transactions())
        pandas_outputs = build_customer_metric_outputs(clean)
        with tempfile.TemporaryDirectory() as tmp_dir:
            clean_path = Path(tmp_dir) / "clean_transactions.parquet"
            clean.to_parquet(clean_path, index=False)
            try:
                spark_outputs = build_spark_metric_outputs(spark, clean_path)
                spark_customers = spark_outputs["customer_metrics"].toPandas().sort_values("customer_id")
            finally:
                spark.stop()

        pandas_customers = pandas_outputs["customer_metrics"].sort_values("customer_id").reset_index(drop=True)
        spark_customers = spark_customers.reset_index(drop=True)
        self.assertEqual(len(spark_customers), len(pandas_customers))
        self.assertAlmostEqual(float(spark_customers["revenue"].sum()), float(pandas_customers["revenue"].sum()))
        self.assertEqual(
            int(spark_customers["is_repeat_customer"].sum()),
            int(pandas_customers["is_repeat_customer"].sum()),
        )

    def test_databricks_table_name_builder(self) -> None:
        self.assertEqual(
            qualified_table_name("main", "commercial_retention_gold", "gold_customer_metrics"),
            "main.commercial_retention_gold.gold_customer_metrics",
        )
        self.assertEqual(
            qualified_table_name(None, "commercial_retention_gold", "gold_customer_metrics"),
            "commercial_retention_gold.gold_customer_metrics",
        )

    def test_databricks_bundle_files_exist(self) -> None:
        bundle_path = PROJECT_ROOT / "databricks" / "databricks.yml"
        jobs_path = PROJECT_ROOT / "databricks" / "resources" / "jobs.yml"
        notebook_path = PROJECT_ROOT / "databricks" / "notebooks" / "run_gold_pipeline.py"

        self.assertTrue(bundle_path.exists())
        self.assertTrue(jobs_path.exists())
        self.assertTrue(notebook_path.exists())

        jobs_config = jobs_path.read_text()
        self.assertIn("commercial_retention_spark_gold_build", jobs_config)
        self.assertIn("build_gold_retention_marts", jobs_config)

    def test_markdown_link_extraction_ignores_remote_links(self) -> None:
        links = extract_local_links(
            "[Local](docs/index.md) [Anchor](#intro) [Remote](https://example.com) ![Image](img.png)"
        )
        self.assertEqual(links, ["docs/index.md"])

    def test_repository_markdown_links_are_valid(self) -> None:
        failures = validate_markdown_links(PROJECT_ROOT)
        self.assertEqual(failures, [])

    def test_synthetic_end_to_end_validation(self) -> None:
        result = run_synthetic_validation()
        self.assertEqual(result["customers"], 3.0)
        self.assertEqual(result["valid_order_lines"], 8.0)
        self.assertGreater(result["snapshot_rows"], 0)


if __name__ == "__main__":
    unittest.main()

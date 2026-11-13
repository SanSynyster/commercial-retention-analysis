import unittest
import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from src import monthly_purchase_advanced_benchmark as p3
from src import monthly_purchase_boosting_extension as extension


class BoostingExtensionTests(unittest.TestCase):
    def test_predeclared_grids_have_three_deterministic_cpu_configs(self):
        self.assertEqual(len(extension.XGB_GRID), 3)
        self.assertEqual(len(extension.LGB_GRID), 3)
        for family, grid in (("XGBoost", extension.XGB_GRID), ("LightGBM", extension.LGB_GRID)):
            for config in grid:
                first = extension._model(family, config).named_steps["model"]
                second = extension._model(family, config).named_steps["model"]
                self.assertEqual(first.get_params(), second.get_params())
                self.assertEqual(first.get_params()["n_jobs"], 1)
                self.assertEqual(first.get_params()["random_state"], extension.SEED)
                self.assertIsNone(first.get_params().get("early_stopping_rounds"))
                self.assertEqual(first.get_params().get("subsample_freq", 1), 1)

    def test_development_selection_uses_only_four_fold_ap_records(self):
        records = [
            {"family": "XGBoost", "config_index": i, "fold": fold,
             "average_precision": ap}
            for i, values in enumerate(([.50, .51, .52, .53], [.55, .54, .54, .53], [.4, .4, .4, .4]))
            for fold, ap in zip(("2011-03", "2011-04", "2011-05", "2011-06"), values)
        ]
        selected = extension.select_by_development_ap(records, "XGBoost", 3)
        self.assertEqual(selected["config_index"], 1)
        self.assertAlmostEqual(selected["mean_fold_average_precision"], .54)
        with self.assertRaises(ValueError):
            extension.select_by_development_ap(records[:-1], "XGBoost", 3)
        contaminated = records + [{"family": "XGBoost", "config_index": 0,
                                   "fold": "2011-07", "average_precision": 0.99}]
        with self.assertRaises(ValueError):
            extension.select_by_development_ap(contaminated, "XGBoost", 3)

    def test_extension_fold_protocol_matches_existing_temporal_fold_contract(self):
        rows = []
        for month, start in [("2011-01", "2011-01-01"), ("2011-02", "2011-02-01"),
                             ("2011-03", "2011-03-01"), ("2011-04", "2011-04-01"),
                             ("2011-05", "2011-05-01"), ("2011-06", "2011-06-01")]:
            for customer, label in (("1", 0), ("2", 1)):
                rows.append({"evaluation_partition": "train", "snapshot_month": month,
                             "decision_time": pd.Timestamp(start),
                             "outcome_window_end_exclusive": pd.Timestamp(start) + pd.Timedelta(days=30),
                             "outcome_window_mature": True, "outcome_coverage_status": "complete",
                             "outcome_label": label, "customer_id": customer})
        folds = p3.make_folds(pd.DataFrame(rows))
        self.assertEqual([fold["month"] for fold in folds], ["2011-03", "2011-04", "2011-05", "2011-06"])
        for fold in folds:
            self.assertTrue((fold["train"]["outcome_window_end_exclusive"] < fold["boundary"]).all())

    def test_weighted_cluster_ranking_bootstrap_point_matches_unweighted(self):
        frame = pd.DataFrame({"customer_id": ["a", "b", "c", "d"],
                              "outcome_label": [0, 1, 0, 1]})
        scores = {"XGBoost": np.array([.1, .8, .4, .7]),
                  "Random Forest": np.array([.2, .7, .3, .6])}
        result = extension._pairwise_cluster_bootstrap(
            frame, scores, [("XGBoost", "Random Forest")], reps=20, seed=9)
        a = p3._metrics(frame.outcome_label.to_numpy(), scores["XGBoost"], probability=False)
        b = p3._metrics(frame.outcome_label.to_numpy(), scores["Random Forest"], probability=False)
        comparison = result["comparisons"]["XGBoost - Random Forest"]
        self.assertAlmostEqual(comparison["roc_auc"]["point_difference"], a["roc_auc"] - b["roc_auc"])
        self.assertAlmostEqual(comparison["average_precision"]["point_difference"],
                               a["average_precision"] - b["average_precision"])

    def test_saved_aggregate_manifest_and_report_metrics_are_consistent(self):
        root = Path(__file__).resolve().parents[1]
        output = root.parent / "source_data/uci_online_retail_ii/p3_003_outputs"
        aggregate_path = output / "p3_003_aggregate_results.json"
        manifest_path = output / "p3_003_manifest.json"
        report_path = root / "docs/research/COMMERCIAL_DS_P3_003_XGBOOST_LIGHTGBM_BENCHMARK.md"
        if not all(path.is_file() for path in (aggregate_path, manifest_path, report_path)):
            self.skipTest("External P3-003 artifacts or report are unavailable.")
        aggregate = json.loads(aggregate_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        report = report_path.read_text()
        digest = hashlib.sha256(aggregate_path.read_bytes()).hexdigest()
        self.assertEqual(manifest["aggregate_sha256"], digest)
        self.assertFalse(aggregate["selection"]["holdout_used_for_selection"])
        self.assertEqual(manifest["holdout_used_for_selection"], False)
        for scope, models in (("development_pooled_oof", aggregate["development"]["pooled_oof"]["models"]),
                              ("exploratory_published_holdout", aggregate["exploratory_published_holdout"]["pooled"]["models"])):
            for name, metrics in models.items():
                self.assertIn(f"| {name} | {metrics['roc_auc']:.4f} | {metrics['average_precision']:.4f} |",
                              report, msg=f"Report differs from {scope}/{name} aggregate metrics")
        for family in ("XGBoost", "LightGBM"):
            selected = aggregate["selection"]["selected"][family]
            self.assertIn(f"{family} configuration {selected['config_index']} (mean-fold AP {selected['mean_fold_average_precision']:.4f})",
                          report)
        for pair, metrics in aggregate["development"]["ranking_bootstrap_vs_random_forest"]["comparisons"].items():
            ap = metrics["average_precision"]
            rendered = (f"| {pair} | {metrics['roc_auc']['point_difference']:+.4f} "
                        f"[{metrics['roc_auc']['ci95'][0]:+.4f}, {metrics['roc_auc']['ci95'][1]:+.4f}] | "
                        f"{ap['point_difference']:+.4f} [{ap['ci95'][0]:+.4f}, {ap['ci95'][1]:+.4f}] |")
            self.assertIn(rendered, report)


if __name__ == "__main__":
    unittest.main()

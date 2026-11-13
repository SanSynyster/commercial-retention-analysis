import numpy as np
import pandas as pd
import unittest
from pathlib import Path
import json
from sklearn.metrics import roc_auc_score, average_precision_score

from src.monthly_purchase_advanced_benchmark import (
    make_folds, _crm, paired_cluster_bootstrap, _estimator,
    _weighted_ranking_metrics, _grouped_weighted_ranking_metrics,
    p3_calibration_diagnostic,
)


class AdvancedBenchmarkTests(unittest.TestCase):
    def test_folds_enforce_label_maturity_gap_and_known_validation_labels(self):
        rows = []
        for month, start in [("2011-01", "2011-01-01"), ("2011-02", "2011-02-01"),
                             ("2011-03", "2011-03-01"), ("2011-04", "2011-04-01"),
                             ("2011-05", "2011-05-01"), ("2011-06", "2011-06-01")]:
            for customer, label in [("1", 0), ("2", 1)]:
                rows.append({"evaluation_partition": "train", "snapshot_month": month,
                             "decision_time": pd.Timestamp(start),
                             "outcome_window_end_exclusive": pd.Timestamp(start) + pd.Timedelta(days=30),
                             "outcome_window_mature": True, "outcome_coverage_status": "complete",
                             "outcome_label": label, "customer_id": customer})
        folds = make_folds(pd.DataFrame(rows))
        self.assertEqual([f["month"] for f in folds], ["2011-03", "2011-04", "2011-05", "2011-06"])
        self.assertEqual(len(folds[0]["train"]), 2)  # February's March 3 maturity is after March 1.
        self.assertLess(folds[0]["train"]["outcome_window_end_exclusive"].max(), folds[0]["boundary"])


    def test_crm_capacity_is_recomputed_per_month(self):
        frame = pd.DataFrame({"snapshot_month": ["a"] * 4 + ["b"] * 4,
                              "customer_id": ["d", "c", "b", "a"] * 2,
                              "outcome_label": [0, 1, 0, 1] * 2})
        result = _crm(frame, np.ones(8))
        self.assertEqual(result["5"]["selected"], 2)
        self.assertEqual(result["10"]["selected"], 2)
        self.assertEqual(result["20"]["selected"], 2)
        self.assertEqual(result["5"]["true_positive"], 2)

    def test_paired_cluster_bootstrap_reproducible_and_cluster_weighted(self):
        frame = pd.DataFrame({"snapshot_month": ["a"] * 4 + ["b"] * 4,
                              "customer_id": ["1", "2", "3", "4"] * 2,
                              "outcome_label": [0, 1, 0, 1] * 2})
        scores = {"Logistic C": np.array([.1, .9, .2, .8] * 2),
                  "Frequency": np.array([1, 2, 1, 2] * 2),
                  "Random Forest": np.array([.2, .8, .3, .7] * 2),
                  "HistGradientBoosting": np.array([.3, .7, .2, .8] * 2)}
        first = paired_cluster_bootstrap(frame, scores, reps=20, seed=7)
        second = paired_cluster_bootstrap(frame, scores, reps=20, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["method"], "paired customer-trajectory percentile bootstrap; 20 reps")

    def test_histgradientboosting_disables_automatic_early_stopping(self):
        model = _estimator("HistGradientBoosting", {
            "learning_rate": 0.05, "max_leaf_nodes": 7, "max_iter": 10,
            "min_samples_leaf": 5, "l2_regularization": 1.0, "early_stopping": False,
        }, 11)
        self.assertFalse(model.named_steps["model"].early_stopping)

    def test_unit_customer_weights_reproduce_unweighted_ranking_metrics(self):
        y = np.array([0, 1, 0, 1, 1, 0])
        score = np.array([.1, .8, .4, .8, .6, .8])  # mixed-label score ties exercise tie aggregation.
        actual = _weighted_ranking_metrics(y, score, np.ones(len(y)))
        self.assertAlmostEqual(actual["roc_auc"], roc_auc_score(y, score))
        self.assertAlmostEqual(actual["average_precision"], average_precision_score(y, score))
        _, inverse = np.unique(score, return_inverse=True)
        groups = int(inverse.max()) + 1
        desc = groups - 1 - inverse
        grouped = _grouped_weighted_ranking_metrics(y, np.ones(len(y)), desc, groups)
        self.assertAlmostEqual(grouped["roc_auc"], actual["roc_auc"])
        self.assertAlmostEqual(grouped["average_precision"], actual["average_precision"])

    def test_p3_calibration_diagnostic_separates_nonidentifiability_and_estimation(self):
        constant = p3_calibration_diagnostic(np.array([0, 1, 0, 1]), np.full(4, .5))
        self.assertEqual(constant["status"], "not_identifiable_constant_scores")
        p = np.linspace(.05, .95, 100)
        y = np.tile(np.array([0, 1]), 50)
        result = p3_calibration_diagnostic(y, p)
        self.assertIn(result["status"], {"estimated", "estimated_stationary_with_optimizer_tolerance_warning"})
        self.assertIsNotNone(result["intercept"])
        self.assertIsNotNone(result["slope"])
        self.assertLessEqual(result["gradient_inf_norm"], result["gradient_tolerance"])
        separated_y = (p > .57).astype(int)
        failed = p3_calibration_diagnostic(separated_y, p)
        self.assertTrue(failed["status"].startswith("failed_"))
        self.assertIsNone(failed["intercept"])

    def test_final_report_holdout_metrics_match_saved_aggregate_when_available(self):
        root = Path(__file__).resolve().parents[1]
        aggregate = root.parent / "source_data/uci_online_retail_ii/p3_002_outputs/p3_002_aggregate_results.json"
        report = root / "docs/research/COMMERCIAL_DS_P3_002_ADVANCED_ML_BENCHMARK.md"
        if not aggregate.is_file() or not report.is_file():
            self.skipTest("Final external P3-002 aggregate is not present in this environment.")
        data = json.loads(aggregate.read_text())
        content = report.read_text()
        for model in data["exploratory_published_holdout"]["models"].values():
            for key in ("roc_auc", "average_precision", "brier_score"):
                if model[key] is not None:
                    self.assertIn(f"{model[key]:.4f}", content)
        for model in data["exploratory_published_holdout"]["models"].values():
            calibration = model["calibration"]
            if calibration.get("intercept") is not None and calibration.get("slope") is not None:
                self.assertIn(f"{calibration['intercept']:.3f} / {calibration['slope']:.3f}", content)
        self.assertIn("**`early_stopping=False`**", content)
        self.assertEqual(data["runtime"]["estimator_fit_counts"]["total_estimator_fit_calls"], 30)

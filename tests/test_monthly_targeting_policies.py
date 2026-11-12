from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import monthly_targeting_policies as policies


def _synthetic_holdout() -> pd.DataFrame:
    rows = []
    months = ["2011-07", "2011-08", "2011-09", "2011-10", "2011-11"]
    for month_index, month in enumerate(months):
        n = 12 if month == "2011-11" else 2
        for i in range(n):
            label = int(i % 2 == 0)
            if month == "2011-11" and i < 3:
                label = 0
            rows.append({
                "customer_id": f"cust-{i:02d}",
                "decision_time": pd.Timestamp(f"{month}-01"),
                "snapshot_month": month,
                "outcome_label": label,
                "probability_C_full_11": float(n - i),
                "probability_B_rfm": float(n - i),
                "qualifying_purchase_dates_365d": float(n - i),
                "outcome_window_mature": True,
                "evaluation_partition": "test",
            })
    return pd.DataFrame(rows)


class MonthlyTargetingPolicyTests(unittest.TestCase):
    def test_capacity_rounding_uses_ceiling(self):
        self.assertEqual(policies.capacity_count(4314, 0.05), 216)
        self.assertEqual(policies.capacity_count(4314, 0.10), 432)
        self.assertEqual(policies.capacity_count(4314, 0.20), 863)
        self.assertEqual(policies.capacity_count(0, 0.10), 0)

    def test_customer_key_tie_break_is_deterministic(self):
        frame = pd.DataFrame({
            "customer_id": ["c", "a", "b"],
            "score": [1.0, 1.0, 1.0],
        })
        selected = policies.select_ranked(frame, "score", 0.34)
        self.assertEqual(selected.customer_id.tolist(), ["a", "b"])
        repeated = policies.select_ranked(frame.sample(frac=1, random_state=7), "score", 0.34)
        self.assertEqual(repeated.customer_id.tolist(), ["a", "b"])

    def test_monthly_customer_selection_is_unique_and_exact_capacity(self):
        frame = _synthetic_holdout().query("snapshot_month == '2011-07'")
        selected = policies.select_ranked(frame, "probability_C_full_11", 0.05)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected.customer_id.nunique(), 1)
        duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            policies.select_ranked(duplicate, "probability_C_full_11", 0.05)

    def test_precision_capture_and_lift_accounting(self):
        result = policies._selected_metrics(n=10, positives=4, selected_n=2, selected_positive=1)
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["purchase_capture_recall"], 0.25)
        self.assertEqual(result["lift"], 1.25)

    def test_random_policy_uses_analytic_expectation(self):
        result = policies._random_expected(n=10, positives=4, selected_n=2)
        self.assertEqual(result["selected_positive_outcomes"], 0.8)
        self.assertEqual(result["precision"], 0.4)
        self.assertEqual(result["purchase_capture_recall"], 0.2)
        self.assertEqual(result["lift"], 1.0)

    def test_weighted_selection_preserves_bootstrap_multiplicity(self):
        y = np.asarray([1.0, 0.0, 1.0])
        weights = np.asarray([2.0, 1.0, 3.0])
        order = np.asarray([0, 1, 2])
        positive, selected_weights = policies._weighted_selection_positive(y, weights, order, 3)
        self.assertEqual(selected_weights.sum(), 3)
        self.assertEqual(positive, 2)

    def test_pooled_precision_is_snapshot_weighted_not_month_average(self):
        data = _synthetic_holdout()
        summary, _, _ = policies._selection_metrics_and_overlap(data)
        pooled = summary["pooled_snapshot_weighted"]["20pct"]["model_c"]["precision_snapshot_weighted"]
        monthly_values = [
            summary[m]["capacities"]["20pct"]["selected_per_policy"]["model_c"]["precision"]
            for m in policies.MONTHS
        ]
        self.assertAlmostEqual(pooled, 4 / 7)
        self.assertNotAlmostEqual(pooled, float(np.mean(monthly_values)))

    def test_customer_cluster_bootstrap_is_paired_and_reproducible(self):
        data = _synthetic_holdout()
        first = policies.paired_customer_cluster_bootstrap(data, n_resamples=40, seed=91)
        second = policies.paired_customer_cluster_bootstrap(data, n_resamples=40, seed=91)
        self.assertEqual(first, second)
        self.assertEqual(first["valid_resamples"] + first["omitted_resamples"], 40)
        self.assertIn("model_c_minus_frequency", first["difference_intervals"]["10pct"])
        self.assertIn("sample customer trajectories", first["method"])


if __name__ == "__main__":
    unittest.main()

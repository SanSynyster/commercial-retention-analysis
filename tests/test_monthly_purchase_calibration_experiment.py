from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import monthly_purchase_calibration_experiment as cal


class _ReversedClassEstimator:
    classes_ = np.asarray([1, 0])

    def predict_proba(self, features):
        return np.tile([0.83, 0.17], (len(features), 1))


def _timeline() -> pd.DataFrame:
    rows = []
    for month, decision, end in (
        ("2011-03", "2011-03-01", "2011-03-31"),
        ("2011-04", "2011-04-01", "2011-05-01"),
        ("2011-05", "2011-05-01", "2011-05-31"),
    ):
        for i, y in enumerate((0, 1, 0, 1)):
            rows.append({"customer_id": f"c{i}", "snapshot_month": month,
                         "decision_time": pd.Timestamp(decision),
                         "outcome_window_end_exclusive": pd.Timestamp(end),
                         "outcome_window_mature": True, "outcome_coverage_status": "complete",
                         "outcome_label": y})
    return pd.DataFrame(rows)


class MonthlyPurchaseCalibrationExperimentTests(unittest.TestCase):
    def test_calibration_pool_is_strictly_chronological_and_mature(self):
        frame = _timeline()
        pool = cal.calibration_pool(frame, pd.Timestamp("2011-05-01"))
        self.assertEqual(set(pool.snapshot_month), {"2011-03"})
        self.assertTrue((pool.outcome_window_end_exclusive < pd.Timestamp("2011-05-01")).all())
        self.assertFalse((pool.snapshot_month == "2011-04").any())

    def test_unknown_incomplete_and_immature_rows_never_enter_calibration(self):
        frame = _timeline()
        frame.loc[0, "outcome_window_mature"] = False
        frame.loc[1, "outcome_coverage_status"] = "interrupted_coverage"
        frame.loc[2, "outcome_label"] = pd.NA
        pool = cal.calibration_pool(frame, pd.Timestamp("2011-05-01"))
        self.assertEqual(len(pool), 1)
        self.assertTrue(pool.outcome_window_mature.all())
        self.assertTrue(pool.outcome_coverage_status.eq("complete").all())
        self.assertFalse(pool.outcome_label.isna().any())

    def test_evaluation_month_rows_are_excluded_from_earlier_pool(self):
        frame = _timeline()
        pool = cal.calibration_pool(frame, pd.Timestamp("2011-05-01"))
        self.assertNotIn("2011-05", set(pool.snapshot_month))
        self.assertTrue((pool.decision_time < pd.Timestamp("2011-05-01")).all())

    def test_positive_probability_is_selected_by_class_label(self):
        got = cal.positive_class_probability(_ReversedClassEstimator(), pd.DataFrame({"x": [1, 2]}))
        np.testing.assert_array_equal(got, [0.83, 0.83])

    def test_intercept_only_and_slope_recalibration(self):
        y = np.asarray([0, 1, 0, 1, 0, 1] * 10)
        p = np.asarray([0.1, 0.2, 0.3, 0.4, 0.6, 0.8] * 10)
        offset = cal.fit_calibrator("intercept_only", y, p)
        adjusted = cal.apply_calibrator(offset, p)
        self.assertAlmostEqual(float(adjusted.mean()), float(y.mean()), places=8)
        slope = cal.fit_calibrator("intercept_slope", y, p)
        self.assertTrue(np.isfinite(cal.apply_calibrator(slope, p)).all())
        self.assertLess(cal.probability_metrics(y, adjusted)["brier"], 0.25)

    def test_isotonic_requires_sample_size_and_preserves_monotonicity(self):
        with self.assertRaises(ValueError):
            cal.fit_calibrator("isotonic", np.asarray([0, 1]), np.asarray([0.2, 0.8]))
        y = np.tile([0, 1], 600)
        p = np.linspace(0.01, 0.99, len(y))
        fitted = cal.fit_calibrator("isotonic", y, p)
        adjusted = cal.apply_calibrator(fitted, p)
        self.assertTrue((np.diff(adjusted) >= -1e-12).all())

    def test_metrics_are_reproducible_and_correct(self):
        y = np.asarray([0, 1, 0, 1])
        p = np.asarray([0.1, 0.8, 0.4, 0.7])
        first = cal.probability_metrics(y, p)
        second = cal.probability_metrics(y, p)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["brier"], float(np.mean((p-y)**2)))

    def test_customer_cluster_bootstrap_is_paired_and_deterministic(self):
        frame = pd.DataFrame({"customer_id": ["a", "a", "b", "c", "d", "d"],
                              "outcome_label": [0, 1, 0, 1, 0, 1]})
        predictions = {"uncalibrated": np.asarray([.1, .4, .2, .6, .3, .7]),
                       "intercept_only": np.asarray([.12, .45, .24, .64, .35, .74])}
        a = cal.paired_cluster_loss_bootstrap(frame, predictions, reps=40, seed=9)
        b = cal.paired_cluster_loss_bootstrap(frame, predictions, reps=40, seed=9)
        self.assertEqual(a, b)
        self.assertEqual(a["comparisons"]["intercept_only"]["brier"]["valid_resamples"], 40)

    def test_crm_bootstrap_preserves_pairing_and_monotone_rankings(self):
        frame = pd.DataFrame({"customer_id": ["a", "a", "b", "c", "d", "d"],
                              "snapshot_month": ["m1", "m2", "m1", "m1", "m2", "m2"],
                              "outcome_label": [0, 1, 0, 1, 0, 1]})
        p = np.asarray([.1, .4, .2, .6, .3, .7])
        adjusted = cal.apply_calibrator({"kind": "intercept_only", "intercept": .5}, p)
        got = cal.paired_cluster_crm_bootstrap(frame, {"uncalibrated": p, "offset": adjusted}, reps=30, seed=6)
        got_again = cal.paired_cluster_crm_bootstrap(frame, {"uncalibrated": p, "offset": adjusted}, reps=30, seed=6)
        self.assertEqual(got, got_again)
        for metric in got["comparisons"]["offset - uncalibrated"].values():
            self.assertAlmostEqual(metric["point_difference"], 0.0)
            np.testing.assert_allclose(metric["ci95"], [0, 0], atol=1e-12)

    def test_monthly_capacity_uses_deterministic_customer_tie_break(self):
        frame = pd.DataFrame({"customer_id": ["c", "a", "b", "d"], "snapshot_month": ["m"]*4,
                              "outcome_label": [0, 1, 1, 0], "score": [.5]*4})
        # The 25% monthly capacity selects one row; tied scores break by ID.
        top = __import__("monthly_targeting_policies").select_ranked(frame, "score", .25)
        self.assertEqual(top.customer_id.tolist(), ["a"])


if __name__ == "__main__":
    unittest.main()

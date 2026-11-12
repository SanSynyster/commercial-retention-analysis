from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import monthly_purchase_calibration as calibration


def _timeline() -> pd.DataFrame:
    rows = []
    months = [
        ("2011-07", "2011-07-01", "2011-07-31"),
        ("2011-08", "2011-08-01", "2011-08-31"),
        ("2011-09", "2011-09-01", "2011-10-01"),
        ("2011-10", "2011-10-01", "2011-10-31"),
        ("2011-11", "2011-11-01", "2011-12-01"),
    ]
    for month, decision, maturity in months:
        for i, label in enumerate((0, 1, 0, 1)):
            rows.append({
                "customer_id": f"c{i}",
                "snapshot_month": month,
                "decision_time": pd.Timestamp(decision),
                "outcome_window_end_exclusive": pd.Timestamp(maturity),
                "outcome_window_mature": True,
                "outcome_coverage_status": "complete",
                "evaluation_partition": "test",
                "outcome_label": label,
                "probability_C_full_11": (0.15, 0.7, 0.25, 0.8)[i],
                "probability_B_rfm": (0.2, 0.65, 0.3, 0.75)[i],
            })
    return pd.DataFrame(rows)


class MonthlyPurchaseCalibrationTests(unittest.TestCase):
    def test_maturity_boundary_requires_strictly_earlier_label(self):
        frame = _timeline()
        pool = calibration.historically_available_rows(frame, pd.Timestamp("2011-10-01"))
        self.assertEqual(set(pool.snapshot_month), {"2011-07", "2011-08"})
        self.assertTrue((pool.outcome_window_end_exclusive < pd.Timestamp("2011-10-01")).all())
        # September ends exactly at the October decision and is unavailable then.
        self.assertFalse((pool.snapshot_month == "2011-09").any())

    def test_incomplete_or_unknown_history_is_excluded(self):
        frame = _timeline()
        frame.loc[0, "outcome_window_mature"] = False
        frame.loc[1, "outcome_coverage_status"] = "interrupted_coverage"
        frame.loc[2, "outcome_label"] = pd.NA
        pool = calibration.historically_available_rows(frame, pd.Timestamp("2011-09-01"))
        self.assertEqual(len(pool), 5)
        self.assertFalse(pool.outcome_label.isna().any())
        self.assertTrue(pool.outcome_window_mature.all())

    def test_sequential_pool_expansion_and_strict_timing(self):
        frame = _timeline()
        adjusted, records = calibration.sequential_calibration(frame)
        self.assertEqual([r["calibration_snapshots"] for r in records], [8, 8, 16])
        self.assertEqual([r["calibration_positives"] for r in records], [4, 4, 8])
        self.assertEqual(records[1]["latest_maturity_timestamp"], "2011-08-31 00:00:00")
        self.assertEqual(records[2]["latest_maturity_timestamp"], "2011-10-31 00:00:00")
        self.assertTrue(adjusted.loc[adjusted.snapshot_month.isin(calibration.TARGET_MONTHS), "probability_C_sequential_adjusted"].notna().all())

    def test_intercept_fit_matches_calibration_pool_prevalence(self):
        y = np.asarray([0, 0, 0, 1, 1, 1])
        p = np.asarray([0.15, 0.2, 0.35, 0.3, 0.55, 0.7])
        delta = calibration.fit_intercept_adjustment(y, p)
        adjusted = calibration.apply_intercept_adjustment(p, delta)
        self.assertAlmostEqual(float(adjusted.mean()), float(y.mean()), places=10)
        self.assertTrue(np.isfinite(delta))

    def test_adjustment_is_bounded_and_preserves_ordering(self):
        p = np.asarray([0.02, 0.25, 0.75, 0.98])
        adjusted = calibration.apply_intercept_adjustment(p, 0.4)
        self.assertTrue(((adjusted > 0) & (adjusted < 1)).all())
        np.testing.assert_array_equal(np.argsort(p), np.argsort(adjusted))
        with self.assertRaises(ValueError):
            calibration.apply_intercept_adjustment([0.2, 1.1], 0.1)

    def test_sequential_adjustment_is_deterministic(self):
        frame = _timeline()
        first, records_first = calibration.sequential_calibration(frame)
        second, records_second = calibration.sequential_calibration(frame)
        np.testing.assert_array_equal(first.probability_C_sequential_adjusted, second.probability_C_sequential_adjusted)
        self.assertEqual(records_first, records_second)

    def test_customer_bootstrap_preserves_cluster_multiplicity_deterministically(self):
        frame = _timeline()
        first = calibration.customer_cluster_bootstrap_brier_difference(frame, n_resamples=30, seed=42)
        second = calibration.customer_cluster_bootstrap_brier_difference(frame, n_resamples=30, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(first["valid_resamples"] + first["omitted_resamples"], 30)


if __name__ == "__main__":
    unittest.main()

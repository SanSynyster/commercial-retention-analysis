from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

from src.day21_baseline import (
    MODEL_B_FEATURES,
    MODEL_C_FEATURES,
    _metric_summary,
    calibration_diagnostic,
    percentile_bootstrap_auc,
    select_approved_partitions,
    standardize_train_test,
)


def row(partition, label, decision, deadline, gross):
    return {
        "evaluation_partition": partition,
        "outcome_label": label,
        "complete_horizon_observed": partition in {"train", "test", "pre_cutoff_label_not_available"},
        "training_label_available_at_cutoff": partition == "train",
        "day21_decision_timestamp": pd.Timestamp(decision),
        "day111_outcome_deadline": pd.Timestamp(deadline),
        "first_day_qualifying_gross": gross,
        "first_day_item_quantity": 2,
        "first_day_product_diversity": 1,
        "customer_id": "synthetic-only",
        "future_debug_field": "must not enter model features",
    }


class Day21BaselineTests(unittest.TestCase):
    def test_feature_allowlists_exclude_metadata_and_future_fields(self):
        self.assertEqual(MODEL_B_FEATURES, ("first_day_qualifying_gross",))
        self.assertEqual(MODEL_C_FEATURES, (
            "first_day_qualifying_gross", "first_day_item_quantity", "first_day_product_diversity"
        ))
        frame = pd.DataFrame([{
            "first_day_qualifying_gross": 3.0,
            "first_day_item_quantity": 4,
            "first_day_product_diversity": 2,
            "outcome_label": 1,
            "day21_decision_timestamp": pd.Timestamp("2011-07-01"),
            "future_debug_field": 999999,
        }])
        varied = frame.assign(first_day_qualifying_gross=7, first_day_item_quantity=8, first_day_product_diversity=3)
        x_train, _, _ = standardize_train_test(pd.concat([frame, varied]), frame, MODEL_C_FEATURES)
        self.assertEqual(x_train.shape[1], 3)

    def test_scaling_uses_training_statistics_only(self):
        train = pd.DataFrame({
            "first_day_qualifying_gross": [0.0, 3.0],
            "first_day_item_quantity": [1.0, 3.0],
            "first_day_product_diversity": [1.0, 3.0],
        })
        test = pd.DataFrame({
            "first_day_qualifying_gross": [999.0],
            "first_day_item_quantity": [999.0],
            "first_day_product_diversity": [999.0],
        })
        _, x_test, stats = standardize_train_test(train, test, MODEL_C_FEATURES)
        expected_mean = np.log1p([0.0, 3.0]).mean()
        self.assertAlmostEqual(stats["first_day_qualifying_gross"]["log1p_mean"], expected_mean)
        expected = (np.log1p(999.0) - expected_mean) / np.log1p([0.0, 3.0]).std(ddof=0)
        self.assertAlmostEqual(x_test[0, 0], expected)

    def test_partition_selection_excludes_unavailable_and_unknown_labels(self):
        cohort = pd.DataFrame([
            row("train", 1, "2011-01-01", "2011-04-01", 3),
            row("train", 0, "2011-02-01", "2011-05-01", 4),
            row("pre_cutoff_label_not_available", 1, "2011-04-01", "2011-07-30", 8),
            row("test", 0, "2011-07-01", "2011-10-01", 2),
            row("test_immature", pd.NA, "2011-09-01", "2011-12-01", 900),
        ])
        train, test = select_approved_partitions(cohort, validate_protocol_counts=False)
        self.assertEqual(train["outcome_label"].tolist(), [1, 0])
        self.assertEqual(test["outcome_label"].tolist(), [0])
        self.assertNotIn("pre_cutoff_label_not_available", set(train.evaluation_partition))
        self.assertNotIn("test_immature", set(test.evaluation_partition))

    def test_future_label_changes_do_not_change_selected_training_rows(self):
        cohort = pd.DataFrame([
            row("train", 1, "2011-01-01", "2011-04-01", 3),
            row("pre_cutoff_label_not_available", 1, "2011-04-01", "2011-07-30", 8),
            row("test", 0, "2011-07-01", "2011-10-01", 2),
            row("test_immature", pd.NA, "2011-09-01", "2011-12-01", 900),
        ])
        train_a, _ = select_approved_partitions(cohort, validate_protocol_counts=False)
        changed = cohort.copy()
        changed.loc[1, "outcome_label"] = 0
        changed.loc[3, "outcome_label"] = 1
        train_b, _ = select_approved_partitions(changed, validate_protocol_counts=False)
        pd.testing.assert_frame_equal(train_a, train_b)

    def test_auc_and_bootstrap_are_correct_and_reproducible(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.1, 0.4, 0.35, 0.8])
        self.assertAlmostEqual(_metric_summary(y, p)["roc_auc"], 0.75)
        a = percentile_bootstrap_auc(y, p, n_resamples=200, seed=41)
        b = percentile_bootstrap_auc(y, p, n_resamples=200, seed=41)
        self.assertEqual(a, b)
        self.assertEqual(a["requested_resamples"], a["valid_resamples"] + a["omitted_single_class_resamples"])
        self.assertGreater(a["valid_resamples"], 0)

    def test_precision_warning_at_stationary_well_conditioned_optimum_is_accepted(self):
        logits = np.array([-2.0, -1.0, 1.0, 2.0])
        y = np.array([0, 1, 0, 1])
        probability = expit(logits)
        slope = brentq(lambda value: 2 * expit(value) + 4 * (expit(2 * value) - 1), 0, 10)
        stationary_parameters = np.array([0.0, slope])

        def precision_loss_after_stationarity(fun, x0, **kwargs):
            return SimpleNamespace(
                success=False,
                x=stationary_parameters,
                message="Desired error not necessarily achieved due to precision loss",
            )

        with patch("src.day21_baseline.minimize", side_effect=precision_loss_after_stationarity):
            result = calibration_diagnostic(y, probability)
        self.assertAlmostEqual(result["intercept"], 0.0, places=7)
        self.assertAlmostEqual(result["slope"], slope, places=7)
        self.assertEqual(result["status"], "stationary_optimum_after_optimizer_warning")

    def test_calibration_still_rejects_nonidentifiable_and_nonstationary_fits(self):
        y = np.array([0, 1, 0, 1])
        constant = calibration_diagnostic(y, np.full(4, 0.4))
        self.assertIsNone(constant["slope"])
        self.assertEqual(constant["status"], "slope_not_identifiable_constant_predictions")
        probability = expit(np.array([-2.0, -1.0, 1.0, 2.0]))
        with patch("src.day21_baseline.minimize", return_value=SimpleNamespace(
            success=False, x=np.array([20.0, 20.0]), message="precision loss"
        )):
            unstable = calibration_diagnostic(y, probability)
        self.assertIsNone(unstable["slope"])
        self.assertEqual(unstable["status"], "not_estimable_or_unstable")


if __name__ == "__main__":
    unittest.main()

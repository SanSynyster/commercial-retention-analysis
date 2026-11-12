from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import monthly_purchase_baselines as baselines


EXPECTED_FEATURES = (
    "days_since_last_qualifying_purchase",
    "qualifying_purchase_occasions_365d",
    "qualifying_purchase_dates_365d",
    "qualifying_gross_merchandise_365d",
    "average_qualifying_basket_value_365d",
    "average_qualifying_basket_quantity_365d",
    "average_basket_product_diversity_365d",
    "qualifying_unique_product_count_365d",
    "median_interpurchase_interval_days_365d",
    "qualifying_purchase_occasions_90d",
    "qualifying_gross_merchandise_90d",
)


def _synthetic_training(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(8021)
    values = {}
    for feature in EXPECTED_FEATURES:
        values[feature] = rng.lognormal(mean=2.0, sigma=0.7, size=n)
    values["days_since_last_qualifying_purchase"] = rng.uniform(0.1, 365, size=n)
    values["qualifying_purchase_occasions_365d"] = rng.integers(1, 12, size=n)
    values["qualifying_purchase_dates_365d"] = rng.integers(1, 10, size=n)
    values["qualifying_gross_merchandise_365d"] = rng.lognormal(5, 1, size=n)
    values["median_interpurchase_interval_days_365d"] = rng.choice([np.nan, 4.0, 30.0, 120.0], size=n)
    frame = pd.DataFrame(values, columns=EXPECTED_FEATURES)
    signal = frame["qualifying_gross_merchandise_365d"] + 50 * frame["qualifying_purchase_occasions_365d"]
    frame[baselines.LABEL_COLUMN] = (signal > signal.median()).astype(int)
    frame[baselines.CUSTOMER_COLUMN] = [f"customer-{i // 2}" for i in range(n)]
    frame[baselines.MONTH_COLUMN] = "2011-01"
    return frame


class MonthlyPurchaseBaselineTests(unittest.TestCase):
    def test_feature_order_matches_frozen_protocol(self):
        self.assertEqual(tuple(baselines.FEATURE_COLUMNS), EXPECTED_FEATURES)
        self.assertEqual(baselines.RFM_FEATURES, (
            "days_since_last_qualifying_purchase",
            "qualifying_purchase_occasions_365d",
            "qualifying_gross_merchandise_365d",
        ))
        with self.assertRaises(ValueError):
            baselines._numeric_matrix(pd.DataFrame(columns=list(reversed(EXPECTED_FEATURES))), EXPECTED_FEATURES)

    def test_preprocessing_uses_training_statistics_only(self):
        train = _synthetic_training(40).loc[:, list(EXPECTED_FEATURES)]
        prep, x_train = baselines.fit_preprocessor(train, EXPECTED_FEATURES)
        original = (prep.log_medians.copy(), prep.means.copy(), prep.scales.copy())
        test = train.iloc[:5].copy()
        test.loc[:, "qualifying_gross_merchandise_365d"] = 1e12
        test.loc[0, "median_interpurchase_interval_days_365d"] = np.nan
        x_test = prep.transform(test)
        self.assertEqual(x_train.shape, (40, len(EXPECTED_FEATURES)))
        self.assertEqual(x_test.shape, (5, len(EXPECTED_FEATURES)))
        np.testing.assert_array_equal(prep.log_medians, original[0])
        np.testing.assert_array_equal(prep.means, original[1])
        np.testing.assert_array_equal(prep.scales, original[2])
        self.assertTrue(np.isfinite(x_test).all())
        self.assertAlmostEqual(float(x_train.mean(axis=0)[0]), 0.0, places=10)

    def test_model_fitting_is_deterministic_and_training_only(self):
        training = _synthetic_training()
        prevalence1, models1, train_predictions1 = baselines.fit_models(training)
        prevalence2, models2, train_predictions2 = baselines.fit_models(training)
        self.assertEqual(prevalence1, prevalence2)
        for name in ("B_rfm", "C_full_11"):
            np.testing.assert_array_equal(models1[name].estimator.coef_, models2[name].estimator.coef_)
            np.testing.assert_array_equal(models1[name].estimator.intercept_, models2[name].estimator.intercept_)
            np.testing.assert_array_equal(train_predictions1[name], train_predictions2[name])
        test = training.iloc[:8].copy()
        p1 = baselines.predict_models(prevalence1, models1, test)
        altered_labels = test.copy()
        altered_labels[baselines.LABEL_COLUMN] = 1 - altered_labels[baselines.LABEL_COLUMN]
        p2 = baselines.predict_models(prevalence1, models1, altered_labels)
        for name in p1:
            np.testing.assert_array_equal(p1[name], p2[name])

    def test_cluster_bootstrap_multiplicity_matches_expanded_customer_rows(self):
        y = np.asarray([0, 1, 0, 1, 0, 1])
        score = np.asarray([0.1, 0.9, 0.2, 0.8, 0.4, 0.7])
        codes = np.asarray([0, 0, 1, 2, 2, 3])
        draws = np.asarray([0, 0, 1, 2])
        weighted = baselines._weighted_auc_for_cluster_draw(y, score, codes, draws, n_clusters=4)
        expanded = np.asarray([0, 1, 0, 1, 2, 3, 4])
        self.assertAlmostEqual(weighted, roc_auc_score(y[expanded], score[expanded]))

    def test_single_class_bootstrap_resamples_are_omitted_without_redraw(self):
        y = np.asarray([0, 0, 1, 1])
        p = np.asarray([0.1, 0.2, 0.8, 0.9])
        clusters = np.asarray(["a", "a", "b", "b"])
        self.assertIsNone(baselines._weighted_auc_for_cluster_draw(
            y, p, np.asarray([0, 0, 1, 1]), np.asarray([0, 0]), n_clusters=2
        ))
        result = baselines.customer_cluster_bootstrap_auc(y, p, clusters, n_resamples=100, seed=4)
        self.assertGreater(result["omitted_single_class_resamples"], 0)
        self.assertEqual(result["valid_resamples"] + result["omitted_single_class_resamples"], 100)
        self.assertEqual(result, baselines.customer_cluster_bootstrap_auc(y, p, clusters, n_resamples=100, seed=4))

    def test_metrics_and_calibration_bands_match_known_values(self):
        y = np.asarray([0, 0, 1, 1])
        p = np.asarray([0.1, 0.4, 0.35, 0.8])
        metrics = baselines._basic_metrics(y, p)
        self.assertAlmostEqual(metrics["roc_auc"], 0.75)
        self.assertAlmostEqual(metrics["average_precision"], 5 / 6)
        self.assertAlmostEqual(metrics["brier_score"], np.mean((y - p) ** 2))
        bands = baselines._calibration_bands(y, p)
        self.assertEqual(sum(row["n"] for row in bands), len(y))
        self.assertEqual(bands[1]["n"], 1)
        self.assertEqual(bands[3]["n"], 1)
        self.assertEqual(bands[4]["n"], 1)
        self.assertEqual(bands[8]["n"], 1)


if __name__ == "__main__":
    unittest.main()

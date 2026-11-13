import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from src.monthly_customer_snapshots import FEATURE_COLUMNS
from src.monthly_purchase_advanced_benchmark import tree_pipeline
from src.monthly_purchase_shap_analysis import (
    deterministic_sample_positions, explain_positive_probability, importance_summary,
    select_positive_class, training_background, transformed_feature_frame,
)


class ShapAnalysisTests(unittest.TestCase):
    @staticmethod
    def data(n=48):
        rows = {name: np.arange(n, dtype=float) + j + 1 for j, name in enumerate(FEATURE_COLUMNS)}
        rows["median_interpurchase_interval_days_365d"] = np.arange(n, dtype=float)
        rows["median_interpurchase_interval_days_365d"][:3] = np.nan
        rows["customer_id"] = [f"private-{i}" for i in range(n)]
        rows["outcome_label"] = (np.arange(n) % 2).astype(int)
        return pd.DataFrame(rows)

    def test_positive_class_output_is_selected_by_class_label(self):
        explanation = SimpleNamespace(
            values=np.array([[[.1, -.2], [.3, -.4]], [[.5, -.6], [.7, -.8]]]),
            base_values=np.array([[.25, .75], [.2, .8]]),
        )
        values, base = select_positive_class(explanation, np.array([1, 0]))
        np.testing.assert_array_equal(values, np.array([[.1, .3], [.5, .7]]))
        np.testing.assert_array_equal(base, np.array([.25, .2]))

    def test_probability_shap_additivity_and_positive_class_alignment(self):
        frame = self.data()
        pipeline = tree_pipeline(RandomForestClassifier(n_estimators=20, max_depth=5,
            min_samples_leaf=2, max_features="sqrt", class_weight=None,
            random_state=23, n_jobs=1))
        pipeline.fit(frame.loc[:, list(FEATURE_COLUMNS)], frame.outcome_label.to_numpy())
        background = training_background(pipeline, frame.iloc[:32], seed=4, size=12)
        explained = transformed_feature_frame(pipeline, frame.iloc[32:40])
        values, base, probability, error = explain_positive_probability(
            pipeline.named_steps["model"], background, explained)
        self.assertLessEqual(error, 1e-5)
        np.testing.assert_allclose(base + values.sum(axis=1), probability, atol=1e-5, rtol=0)
        np.testing.assert_allclose(probability, pipeline.predict_proba(
            frame.iloc[32:40].loc[:, list(FEATURE_COLUMNS)])[:, 1], atol=1e-12)

    def test_transformed_features_preserve_pipeline_values_and_order(self):
        frame = self.data()
        pipeline = tree_pipeline(RandomForestClassifier(n_estimators=5, random_state=1, n_jobs=1))
        pipeline.fit(frame.iloc[:32].loc[:, list(FEATURE_COLUMNS)], frame.outcome_label.iloc[:32])
        actual = transformed_feature_frame(pipeline, frame.iloc[32:36])
        expected = pipeline[:-1].transform(frame.iloc[32:36].loc[:, list(FEATURE_COLUMNS)])
        self.assertEqual(tuple(actual.columns), tuple(FEATURE_COLUMNS))
        np.testing.assert_allclose(actual.to_numpy(), expected)
        self.assertTrue(np.isfinite(actual.to_numpy()).all())

    def test_background_uses_only_training_rows_and_is_deterministic(self):
        frame = self.data()
        train, validation = frame.iloc[:32], frame.iloc[32:].copy()
        validation.loc[:, list(FEATURE_COLUMNS)] = 1e9
        pipeline = tree_pipeline(RandomForestClassifier(n_estimators=5, random_state=1, n_jobs=1))
        pipeline.fit(train.loc[:, list(FEATURE_COLUMNS)], train.outcome_label)
        first = training_background(pipeline, train, seed=77, size=10)
        second = training_background(pipeline, train, seed=77, size=10)
        pd.testing.assert_frame_equal(first, second)
        expected_positions = deterministic_sample_positions(len(train), 10, 77)
        expected = transformed_feature_frame(pipeline, train.iloc[expected_positions])
        pd.testing.assert_frame_equal(first, expected)
        self.assertLess(first.max().max(), transformed_feature_frame(pipeline, validation).min().min())

    def test_deterministic_sampling_is_reproducible_and_source_ordered(self):
        first = deterministic_sample_positions(100, 20, 9)
        second = deterministic_sample_positions(100, 20, 9)
        np.testing.assert_array_equal(first, second)
        self.assertTrue(np.all(np.diff(first) > 0))
        np.testing.assert_array_equal(deterministic_sample_positions(4, 10, 2), np.arange(4))

    def test_aggregate_importance_is_probability_scale_and_sorted(self):
        values = np.array([[.2, -.1], [-.4, .2], [.1, .3]])
        summary = importance_summary(values, ("feature_a", "feature_b"))
        self.assertEqual(summary[0]["feature"], "feature_a")
        self.assertAlmostEqual(summary[0]["mean_abs_shap_probability"], (0.2 + 0.4 + 0.1) / 3)
        self.assertAlmostEqual(summary[0]["mean_signed_shap_probability"], -0.1 / 3)

    def test_saved_report_and_aggregate_consistency_if_run_artifacts_exist(self):
        root = Path(__file__).resolve().parents[1]
        output = root.parent / "source_data/uci_online_retail_ii/p3_004_outputs"
        aggregate_path = output / "p3_004_aggregate_results.json"
        manifest_path = output / "p3_004_manifest.json"
        report_path = root / "docs/research/COMMERCIAL_DS_P3_004_SHAP_EXPLAINABILITY.md"
        if not all(p.exists() for p in (aggregate_path, manifest_path, report_path)):
            self.skipTest("P3-004 aggregate output is not present yet.")
        aggregate = json.loads(aggregate_path.read_text())
        report = report_path.read_text()
        manifest = json.loads(manifest_path.read_text())
        import hashlib
        digest = hashlib.sha256(aggregate_path.read_bytes()).hexdigest()
        self.assertEqual(manifest["aggregate_sha256"], digest)
        self.assertEqual(aggregate["explanation"]["version"], "0.51.0")
        for row in aggregate["development"]["overall_importance"][:5]:
            self.assertIn(row["feature"], report)
            self.assertIn(f"{row['mean_abs_shap_probability']:.5f}", report)
        self.assertNotIn("customer_id", aggregate["private_individual_explanations"])
        self.assertTrue(aggregate["private_individual_explanations"]["contains_customer_ids"])


if __name__ == "__main__":
    unittest.main()

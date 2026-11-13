from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import hillstrom_locked_test_evaluation as locked


class LockedTestEvaluationTests(unittest.TestCase):
    def test_frozen_split_indices_and_binary_arm_mapping(self):
        split = pd.DataFrame({"row_index": range(9),
            "split": ["train", "development", "test"] * 3})
        np.testing.assert_array_equal(locked.frozen_test_row_indices(split), [2, 5, 8])
        data = pd.DataFrame({"segment": ["Mens E-Mail", "Womens E-Mail", "No E-Mail", "Mens E-Mail"],
            "visit": [1, 1, 0, 0]})
        pair = locked.map_contrast(data, "Mens E-Mail", "No E-Mail")
        self.assertEqual(pair.segment.tolist(), ["Mens E-Mail", "No E-Mail", "Mens E-Mail"])
        self.assertEqual(pair.treatment.tolist(), [1, 0, 1])
        self.assertNotIn("Womens E-Mail", pair.segment.tolist())

    def test_primary_risk_difference_newcombe_interval_and_exact_test(self):
        frame = pd.DataFrame({"treatment": [1, 1, 1, 1, 0, 0, 0, 0],
                              "visit": [1, 1, 0, 0, 1, 0, 0, 0]})
        result = locked.binary_risk_difference(frame)
        self.assertEqual((result["n_treated"], result["events_treated"]), (4, 2))
        self.assertEqual((result["n_control"], result["events_control"]), (4, 1))
        self.assertAlmostEqual(result["risk_difference"], .25)
        self.assertAlmostEqual(result["standard_error"], np.sqrt(.5 * .5 / 4 + .25 * .75 / 4))
        self.assertLess(result["ci95_low"], result["risk_difference"])
        self.assertGreater(result["ci95_high"], result["risk_difference"])
        self.assertEqual(result["exact_two_sided_randomization_p"],
                         locked.exact_binary_randomization_pvalue(2, 4, 1, 4))

    def test_newcombe_and_exact_randomization_are_deterministic(self):
        args = (12, 40, 7, 40)
        self.assertEqual(locked.newcombe_risk_difference_interval(*args),
                         locked.newcombe_risk_difference_interval(*args))
        self.assertEqual(locked.exact_binary_randomization_pvalue(*args),
                         locked.exact_binary_randomization_pvalue(*args))

    def test_holm_step_down_adjustment(self):
        got = locked.holm_adjust({"a": .01, "b": .04, "c": .03, "d": .20})
        self.assertAlmostEqual(got["a"], .04)
        self.assertAlmostEqual(got["b"], .09)
        self.assertAlmostEqual(got["c"], .09)
        self.assertAlmostEqual(got["d"], .20)

    def test_expected_random_policy_value_scales_primary_estimate_and_interval(self):
        got = locked.expected_random_policy_value(.05, .02, .08, .20)
        self.assertEqual(got["increment_per_1000"], 10.0)
        self.assertEqual(got["ci95_low_per_1000"], 4.0)
        self.assertEqual(got["ci95_high_per_1000"], 16.0)
        self.assertEqual(got["treat_none_increment_per_1000"], 0.0)

    def test_contrast_propensity_uses_realized_pairwise_arm_share(self):
        frame = pd.DataFrame({"segment": ["Mens E-Mail"] * 3 + ["No E-Mail"] * 2
                                         + ["Womens E-Mail"],
                              "visit": [1, 0, 1, 0, 0, 1]})
        pair = locked.map_contrast(frame, "Mens E-Mail", "No E-Mail")
        self.assertAlmostEqual(pair.treatment.mean(), 3 / 5)
        self.assertEqual(len(pair), 5)

    def test_paired_policy_bootstrap_preserves_row_pairing(self):
        candidate = np.array([2.0, 3.0, 7.0, 9.0])
        reference = np.array([1.0, 2.0, 6.0, 8.0])
        result = locked.paired_policy_value_bootstrap(candidate, reference,
            reps=50, seed=123)
        self.assertAlmostEqual(result["difference"], 1.0)
        self.assertAlmostEqual(result["ci95_low"], 1.0)
        self.assertAlmostEqual(result["ci95_high"], 1.0)

    def test_spend_bootstrap_and_randomization_test_are_reproducible(self):
        frame = pd.DataFrame({"treatment": [1] * 5 + [0] * 5,
            "spend": [0, 2, 0, 4, 1, 0, 1, 0, 2, 0]})
        boot1 = locked.stratified_bootstrap_mean_difference(frame, "spend", 200, 6)
        boot2 = locked.stratified_bootstrap_mean_difference(frame, "spend", 200, 6)
        self.assertEqual(boot1, boot2)
        perm1 = locked.randomization_test_mean_difference(frame, "spend", 500, 7)
        perm2 = locked.randomization_test_mean_difference(frame, "spend", 500, 7)
        self.assertEqual(perm1, perm2)
        self.assertGreaterEqual(perm1["p_value"], 1 / 501)

    def test_test_evaluation_does_no_model_fitting_or_selection(self):
        frame = pd.DataFrame({"segment": ["Mens E-Mail", "Womens E-Mail", "No E-Mail"] * 6,
            "visit": [1, 0, 0, 0, 1, 0] * 3,
            "conversion": [0] * 18, "spend": [0.0] * 18})
        self.assertEqual(len(locked.map_contrast(frame, *locked.PRIMARY_CONTRAST)), 12)
        result = locked.evaluate_test(frame, {"test_outcomes_accessed": True},
                                      spend_bootstrap_reps=50,
                                      spend_permutation_reps=50)
        self.assertEqual(result["metadata"]["model_fit_calls"], 0)
        self.assertFalse(result["metadata"]["model_selection_performed"])
        self.assertFalse(result["metadata"]["candidate_diagnostics_run"])
        self.assertEqual(result["secondary_holm_family_size"], 8)


if __name__ == "__main__":
    unittest.main()

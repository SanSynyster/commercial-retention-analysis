from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import hillstrom_uplift_models as uplift


def model_frame(n=80):
    rng = np.random.default_rng(12)
    return pd.DataFrame({
        "recency": rng.integers(1, 13, n), "history_segment": rng.choice(["low", "high"], n),
        "history": rng.uniform(0, 500, n), "mens": rng.integers(0, 2, n),
        "womens": rng.integers(0, 2, n), "zip_code": rng.choice(["Urban", "Rural"], n),
        "newbie": rng.integers(0, 2, n), "channel": rng.choice(["Web", "Phone"], n),
    })


class HillstromUpliftTests(unittest.TestCase):
    def test_model_selection_order_matches_frozen_protocol_and_excludes_behavior_baseline(self):
        self.assertEqual(uplift.SELECTION_ORDER[:5], (
            "constant_ate", "t_logistic", "s_logistic", "x_logistic", "dr_logistic"))
        self.assertEqual(uplift.SELECTION_ORDER[-1], "dr_hgb")
        self.assertEqual(uplift.SUPPLEMENTARY_ORDER, ("t_xgboost_optional",))
        self.assertNotIn("t_xgboost_optional", uplift.SELECTION_ORDER)
        self.assertNotIn("history_recency", uplift.SELECTION_ORDER)
        self.assertIn("history_recency", uplift.CANDIDATE_ORDER)

    def test_expected_random_dr_increment_is_budget_times_dr_ate(self):
        y = np.array([1, 0, 1, 0, 0, 1]); a = np.array([1, 0, 0, 1, 0, 1])
        mu0 = np.array([.1, .2, .15, .1, .25, .2])
        mu1 = np.array([.3, .35, .4, .25, .3, .45])
        q = .2
        expected = q * uplift.dr_ate_increment(y, a, .5, mu0, mu1)
        self.assertAlmostEqual(uplift.expected_random_dr_increment(y, a, .5, mu0, mu1, q), expected)

    def test_expected_random_reference_is_recomputed_inside_each_bootstrap(self):
        y = np.array([1, 0, 1, 0, 0, 1, 0, 1]); a = np.array([1, 0, 0, 1, 0, 1, 1, 0])
        mu0 = np.array([.1, .2, .15, .1, .25, .2, .12, .18])
        mu1 = np.array([.3, .35, .4, .25, .3, .45, .24, .31])
        scores = np.array([.5, .4, .8, .2, .1, .9, .7, .3]); tie = np.arange(8)
        q = .25; reps = 20; seed = 71
        actual = uplift.paired_expected_random_bootstrap(scores, tie, y, a, .5,
            mu0, mu1, budget=q, reps=reps, seed=seed)
        rng = np.random.default_rng(seed); delta = []; fixed_delta = []
        fixed_random_ref = q * uplift.dr_ate_increment(y, a, .5, mu0, mu1)
        for _ in range(reps):
            idx = rng.integers(0, len(y), size=len(y))
            policy = uplift._candidate_policy(scores[idx], tie[idx], q)
            candidate = uplift.policy_values(y[idx], a[idx], policy, .5,
                mu0[idx], mu1[idx])["dr_increment_vs_none"]
            random_ref = uplift.expected_random_dr_increment(y[idx], a[idx], .5,
                mu0[idx], mu1[idx], q)
            delta.append((candidate - random_ref) * 1000)
            fixed_delta.append((candidate - fixed_random_ref) * 1000)
        np.testing.assert_allclose([actual["ci95_low"], actual["ci95_high"]],
            np.quantile(delta, [.025, .975]))
        self.assertIn("recomputed within each", actual["reference"])
        self.assertFalse(np.allclose(np.quantile(delta, [.025, .975]),
            np.quantile(fixed_delta, [.025, .975])))

    def test_formal_selection_excludes_xgboost_and_keeps_constant_when_tied(self):
        n = 40; rng = np.random.default_rng(4)
        y = rng.binomial(1, .15, n); a = np.tile([0, 1], n // 2)
        mu0 = np.full(n, .1); mu1 = np.full(n, .2); tie = rng.random(n)
        scores = {name: np.zeros(n) for name in uplift.SELECTION_ORDER}
        scores.update({name: rng.normal(size=n) for name in uplift.SUPPLEMENTARY_ORDER})
        selected, comparisons = uplift.select_formal_policy(scores, tie, y, a, .5,
            mu0, mu1, reps=20)
        self.assertEqual(selected, "constant_ate")
        self.assertEqual([x["candidate"] for x in comparisons],
                         list(uplift.SELECTION_ORDER[1:]))
        self.assertNotIn("t_xgboost_optional", [x["candidate"] for x in comparisons])

    def test_expected_reference_does_not_mutate_saved_prediction_rows(self):
        rng = np.random.default_rng(82); n = 60
        frame = pd.DataFrame({"visit": rng.binomial(1, .15, n),
                              "treatment": np.tile([0, 1], n // 2)})
        scores = {name: rng.normal(size=n) for name in uplift.CANDIDATE_ORDER}
        tie = rng.random(n); mu0 = np.full(n, .1); mu1 = np.full(n, .2)
        before = frame.copy(deep=True)
        uplift._expected_random_summary(frame, scores, tie, .5, mu0, mu1, reps=4)
        pd.testing.assert_frame_equal(frame, before)

    def test_primary_binary_mapping_excludes_womens_arm(self):
        frame = pd.DataFrame({"segment": ["Mens E-Mail", "No E-Mail", "Womens E-Mail"]})
        mapped = uplift.map_binary_treatment(frame)
        self.assertEqual(mapped.segment.tolist(), ["Mens E-Mail", "No E-Mail"])
        self.assertEqual(mapped[uplift.TREATMENT].tolist(), [1, 0])

    def test_loader_uses_frozen_split_and_never_parses_test_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data_path = root / "data.csv"; split_path = root / "split.csv"
            rows = []
            split = []
            arms = ["Mens E-Mail", "No E-Mail", "Womens E-Mail"]
            for i in range(30):
                arm = arms[i % 3]
                part = "test" if i >= 24 else ("development" if i >= 15 else "train")
                split.append({"row_index": i, "split": part})
                rows.append({"recency": 1 + i % 12, "history_segment": "low",
                    "history": float(i), "mens": i % 2, "womens": (i + 1) % 2,
                    "newbie": i % 2, "zip_code": "Urban", "channel": "Web",
                    "segment": arm, "visit": "DO_NOT_PARSE" if part == "test" else i % 2,
                    "conversion": 0, "spend": 0.0})
            pd.DataFrame(rows).to_csv(data_path, index=False)
            pd.DataFrame(split).to_csv(split_path, index=False)
            train, dev, metadata = uplift.load_train_development(data_path, split_path, check_hashes=False)
            self.assertEqual(set(train.split), {"train"})
            self.assertEqual(set(dev.split), {"development"})
            self.assertNotIn("test", set(pd.concat([train, dev]).split))
            self.assertFalse(metadata["test_outcomes_accessed"])
            self.assertEqual(metadata["test_rows_parsed"], 0)
            self.assertEqual(set(train[uplift.TREATMENT]), {0, 1})

    def test_counterfactual_probabilities_use_probability_scale_and_do_not_mutate(self):
        class FakeModel:
            classes_ = np.array([0, 1])
            named_steps = {"model": type("Estimator", (), {"classes_": classes_})()}
            def predict_proba(self, frame):
                p = .2 + .3 * frame[uplift.TREATMENT].to_numpy()
                return np.column_stack([1 - p, p])
        x = model_frame(5); original = x.copy(deep=True)
        mu0, mu1 = uplift.counterfactual_probabilities(FakeModel(), x)
        np.testing.assert_allclose(mu0, .2)
        np.testing.assert_allclose(mu1, .5)
        np.testing.assert_allclose(mu1 - mu0, .3)
        pd.testing.assert_frame_equal(x, original)

    def test_x_learner_sign_and_randomisation_weight(self):
        tau_treated = np.array([.4, -.2]); tau_control = np.array([.2, -.1])
        actual = uplift.x_learner_combine(tau_treated, tau_control, propensity=.7)
        np.testing.assert_allclose(actual, .7 * tau_control + .3 * tau_treated)
        self.assertAlmostEqual(actual[0], .26)
        self.assertLess(actual[1], 0.0)

    def test_dr_pseudo_outcome_matches_formula_and_sign(self):
        y = np.array([1, 0, 1, 0]); a = np.array([1, 0, 0, 1])
        mu0 = np.full(4, .2); mu1 = np.full(4, .4); e = .5
        psi = uplift.dr_pseudo_outcome(y, a, mu0, mu1, e)
        expected = (mu1 - mu0) + a / e * (y - mu1) - (1 - a) / (1 - e) * (y - mu0)
        np.testing.assert_allclose(psi, expected)
        self.assertEqual(psi.shape, y.shape)
        self.assertGreater(psi.max(), 1.0)  # DR pseudo-outcomes are not probability-clipped.

    def test_crossfit_nuisance_rows_are_out_of_fold(self):
        x = model_frame(300); rng = np.random.default_rng(22)
        a = np.tile([0, 1], 150)
        y = rng.binomial(1, .1 + .08 * a)
        m0, m1, psi, folds = uplift.crossfit_dr_scores(x, a, y, "logistic", n_splits=5, seed=9)
        self.assertEqual(len(folds), 5)
        self.assertTrue(np.isfinite(m0).all() and np.isfinite(m1).all() and np.isfinite(psi).all())
        validation_sets = [set(range(len(y))) - set(fit) for fit in folds]
        for fit, valid in zip(folds, validation_sets):
            self.assertTrue(set(fit).isdisjoint(valid))
            self.assertTrue(len(valid) > 0)
        self.assertEqual(sum(len(v) for v in validation_sets), len(y))

    def test_ipw_and_doubly_robust_policy_values(self):
        y = np.array([1, 0]); a = np.array([1, 0]); policy = np.array([1, 0])
        mu0 = np.array([.2, .2]); mu1 = np.array([.8, .8])
        value = uplift.policy_values(y, a, policy, .5, mu0, mu1)
        self.assertAlmostEqual(value["ipw_value"], 1.0)
        self.assertAlmostEqual(value["ipw_increment_vs_none"], 1.0)
        self.assertAlmostEqual(value["dr_value"], .5)
        self.assertAlmostEqual(value["dr_increment_vs_none"], .5)

    def test_budget_enforcement_negative_scores_and_ties_are_deterministic(self):
        scores = np.array([-.4, -.2, -.2, -.8, -.1])
        tie = np.array([4, 2, 1, 3, 0])
        selected = uplift.select_top_budget(scores, tie, .4)
        self.assertEqual(int(selected.sum()), 2)
        self.assertEqual(np.flatnonzero(selected).tolist(), [2, 4])
        np.testing.assert_array_equal(selected, uplift.select_top_budget(scores, tie, .4))

    def test_complexity_promotion_requires_positive_lower_confidence_bound(self):
        self.assertTrue(uplift.promote_candidate(.001))
        self.assertFalse(uplift.promote_candidate(0.0))
        self.assertFalse(uplift.promote_candidate(-.2))
        self.assertFalse(uplift.promote_candidate(float("nan")))

    def test_qini_uses_weighted_cumulative_incremental_events(self):
        y = np.array([1, 0, 0, 1]); a = np.array([1, 0, 1, 0])
        score = np.array([2., 1., 0., -1.]); tie = np.arange(4)
        curve = uplift.uplift_curve(score, y, a, .5, tie, grid=np.array([0., .5, 1.]))
        self.assertEqual(curve["gain_per_1000"][1], 500.0)
        self.assertEqual(curve["random_reference_per_1000"][1], 0.0)
        self.assertGreater(curve["auuc_per_1000"], 0.0)

    def test_known_heterogeneity_produces_positive_qini_for_oracle_rank(self):
        rng = np.random.default_rng(918)
        n = 8000
        x = rng.binomial(1, .5, n)
        a = rng.binomial(1, .5, n)
        tau = np.where(x == 1, .12, -.02)
        p0 = np.full(n, .12)
        p1 = np.clip(p0 + tau, 0, 1)
        y = rng.binomial(1, np.where(a == 1, p1, p0))
        tie = rng.random(n)
        oracle = uplift.uplift_curve(tau, y, a, .5, tie)
        constant = uplift.uplift_curve(np.full(n, tau.mean()), y, a, .5, tie)
        self.assertGreater(oracle["auuc_per_1000"], constant["auuc_per_1000"])
        self.assertGreater(oracle["uplift_per_1000_population"]["30%"],
                           constant["uplift_per_1000_population"]["30%"])


if __name__ == "__main__":
    unittest.main()

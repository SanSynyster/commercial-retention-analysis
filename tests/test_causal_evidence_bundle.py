from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src import causal_evidence_bundle as cb


class CausalEvidenceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = cb.load_bundle()

    def test_bundle_schema_checksum_fixed_provenance_and_privacy(self) -> None:
        bundle = cb.validate_bundle(self.bundle)
        data = bundle["data"]
        self.assertEqual(set(data["provenance"]["sources"]), {"p3_008a", "p3_008b", "p3_008c", "p3_008d"})
        self.assertEqual(data["provenance"]["sources"]["p3_008b"]["source_file"], "source_data/hillstrom/p3_008b_outputs/hillstrom_uplift_aggregate_private.json")
        self.assertNotIn("p3_008b_repro_outputs", json.dumps(data))
        content = json.dumps(bundle, sort_keys=True).lower()
        for marker in cb.FORBIDDEN_MARKERS:
            self.assertNotIn(marker, content)

    def test_primary_itt_counts_rates_interval_and_p_value(self) -> None:
        data = self.bundle["data"]
        primary = data["primary"]
        self.assertEqual((primary["events_treated"], primary["n_treated"]), (802, 4262))
        self.assertEqual((primary["events_control"], primary["n_control"]), (454, 4261))
        self.assertAlmostEqual(primary["rate_treated"], 802 / 4262, places=12)
        self.assertAlmostEqual(primary["rate_control"], 454 / 4261, places=12)
        self.assertAlmostEqual(primary["risk_difference_pp"], 8.162680718940825, places=12)
        self.assertAlmostEqual(primary["ci95_low_pp"], 6.6670193140194165, places=12)
        self.assertAlmostEqual(primary["ci95_high_pp"], 9.658481609273203, places=12)
        self.assertAlmostEqual(primary["exact_two_sided_randomization_p"], 1.5255029454841662e-26, places=35)
        self.assertEqual(data["evidence"]["primary"], "Confirmatory randomised evidence — locked test")

    def test_secondary_holm_visit_comparisons_and_development_policy_units(self) -> None:
        data = self.bundle["data"]
        secondary = {row["contrast"]: row for row in data["secondary_visits"]}
        self.assertAlmostEqual(secondary["Women's email vs no email"]["risk_difference_pp"], 4.846743882630973, places=10)
        self.assertAlmostEqual(secondary["Women's email vs no email"]["holm_adjusted_p"], 2.731874623955844e-10, places=20)
        self.assertAlmostEqual(secondary["Men's email vs Women's email"]["risk_difference_pp"], 3.315936836309852, places=10)
        self.assertAlmostEqual(secondary["Men's email vs Women's email"]["holm_adjusted_p"], 0.0003592759945486067, places=12)
        self.assertEqual(data["evidence"]["secondary"], "Secondary randomised — Holm-adjusted comparisons")
        dev = data["development"]
        self.assertEqual((dev["eligible_rows"], dev["selected_rows_at_budget"]), (8522, 1705))
        self.assertEqual(dev["budget"], 0.20)
        policies = {row["candidate"]: row for row in dev["comparisons"]}
        self.assertAlmostEqual(policies["dr_hgb"]["delta_visits_per_1000"], 4.928792087720978, places=10)
        self.assertAlmostEqual(policies["dr_hgb"]["ci95_low"], -2.3449672282176306, places=10)
        self.assertAlmostEqual(policies["dr_hgb"]["ci95_high"], 11.265234963100848, places=10)
        self.assertAlmostEqual(policies["x_logistic"]["delta_visits_per_1000"], 2.046279358403173, places=10)
        self.assertAlmostEqual(policies["t_logistic"]["delta_visits_per_1000"], 0.9432036438233662, places=10)
        self.assertAlmostEqual(policies["history_recency"]["delta_visits_per_1000"], 2.490116806172275, places=10)
        self.assertTrue(all(row["ci95_low"] < 0 < row["ci95_high"] for row in policies.values()))
        self.assertEqual(dev["selected_reference"], "constant_ate")
        self.assertIn("per 1,000 pairwise-eligible experiment rows", dev["outcome_unit"])
        self.assertFalse(dev["locked_test_candidate_diagnostics_run"])
        self.assertEqual(dev["locked_test_model_fit_calls"], 0)
        self.assertEqual(policies["t_xgboost_optional"]["formal_promotion_candidate"], False)

    def test_deterministic_rebuild_from_fixed_sources(self) -> None:
        required = [cb.PRIVATE_ROOT / spec["path"] for spec in cb.SOURCES.values()]
        if not all(path.is_file() for path in required):
            self.skipTest("Private P3-008 aggregate sources are unavailable.")
        self.assertEqual(cb.build_bundle(), self.bundle)
        self.assertEqual(cb.build_bundle(), self.bundle)

    def test_missing_and_mismatched_sources_fail_clearly(self) -> None:
        required = [cb.PRIVATE_ROOT / spec["path"] for spec in cb.SOURCES.values()]
        if not all(path.is_file() for path in required):
            self.skipTest("Private P3-008 aggregate sources are unavailable.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(cb.SourceUnavailableError, "Missing required P3-008 P3_008A"):
                cb.build_bundle(root)
            for name, spec in cb.SOURCES.items():
                target = root / spec["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cb.PRIVATE_ROOT / spec["path"], target)
            bad = root / cb.SOURCES["p3_008b"]["path"]
            bad.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(cb.BundleError, "P3-008 P3_008B aggregate SHA-256 mismatch"):
                cb.build_bundle(root)

    def test_rehashed_changed_bundle_is_rejected_by_independent_content_pin(self) -> None:
        changed = copy.deepcopy(self.bundle)
        changed["data"]["primary"]["risk_difference_pp"] += 1
        changed["content_sha256"] = cb._canonical_hash(changed["data"])
        with self.assertRaisesRegex(cb.BundleError, "approved application pin"):
            cb.validate_bundle(changed)


if __name__ == "__main__":
    unittest.main()

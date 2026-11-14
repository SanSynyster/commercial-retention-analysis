from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from src import segmentation_bundle as sb


class SegmentationBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = sb.load_bundle()

    def test_schema_checksum_provenance_and_aggregate_only_content(self) -> None:
        bundle = sb.validate_bundle(self.bundle)
        self.assertEqual(bundle["data"]["provenance"]["report"], sb.REPORT)
        self.assertEqual(bundle["data"]["provenance"]["source_file"], f"source_data/{sb.SOURCE_AGGREGATE}")
        self.assertEqual(bundle["data"]["provenance"]["sha256_raw_file"], sb.EXPECTED_SOURCE_SHA256)
        self.assertEqual(bundle["data"]["provenance"]["sha256_manifest"], sb.EXPECTED_MANIFEST_SHA256)
        payload = json.dumps(bundle, sort_keys=True).lower()
        for marker in ("customer_id", "customer_month_assignments", ".parquet", "/users/"):
            self.assertNotIn(marker, payload)

    def test_rfm_counts_rates_and_evidence_conclusion(self) -> None:
        data = self.bundle["data"]
        profiles = data["rfm"]["reference_profiles"]
        self.assertEqual(sum(row["n"] for row in profiles.values()), 4260)
        self.assertAlmostEqual(sum(row["share"] for row in profiles.values()), 1.0)
        self.assertEqual(profiles["Champions"]["n"], 1023)
        self.assertAlmostEqual(data["outcomes"]["development_apr_jun"]["rfm_segment"]["Champions"]["purchase_rate"], 0.4402035623409669)
        self.assertEqual(sum(row["n"] for row in data["outcomes"]["development_apr_jun"]["rfm_segment"].values()), 12961)
        self.assertEqual(sum(row["n"] for row in data["outcomes"]["development_apr_jun"]["ml_segment"].values()), 12961)
        self.assertEqual(data["evidence"]["rfm"], "Historical description")
        self.assertEqual(data["evidence"]["kmeans"], "Exploratory")
        self.assertIn("does not demonstrate meaningful incremental purchase discrimination beyond RFM", data["comparison"]["incremental_value_conclusion"])
        self.assertNotIn("roc_auc", json.dumps(data))  # Reviewer-only AUC diagnostics are not in the verified aggregate.

    def test_kmeans_and_comparison_values_match_verified_source(self) -> None:
        data = self.bundle["data"]
        self.assertEqual(data["kmeans"]["selection"]["k"], 3)
        self.assertAlmostEqual(data["kmeans"]["quality"]["silhouette_sampled"], 0.3838147377, places=8)
        self.assertAlmostEqual(data["kmeans"]["quality"]["mean_seed_ari"], 0.9928787094, places=8)
        self.assertAlmostEqual(data["kmeans"]["quality"]["customer_bootstrap_ari_mean"], 0.9741361823, places=8)
        self.assertEqual(data["kmeans"]["reference_profiles"]["1"]["n"], 2310)
        self.assertAlmostEqual(data["outcomes"]["development_apr_jun"]["ml_segment"]["2"]["purchase_rate"], 0.3921319797, places=8)
        self.assertAlmostEqual(data["comparison"]["reference_ari"], 0.3570343882, places=8)
        self.assertAlmostEqual(data["comparison"]["reference_nmi"], 0.4926341833, places=8)

    def test_deterministic_rebuild_from_explicit_sources(self) -> None:
        if not all((sb.DEFAULT_SOURCE_ROOT / name).is_file() for name in ("p3_007_aggregate_results.json", "p3_007_manifest.json")):
            self.skipTest("Authorized private P3-007 aggregate source files are unavailable.")
        first = sb.build_bundle()
        second = sb.build_bundle()
        self.assertEqual(first, second)
        self.assertEqual(first, self.bundle)

    def test_missing_and_mismatched_sources_fail_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(sb.SourceUnavailableError, "Missing required P3-007"):
                sb.build_bundle(Path(tmp))
            root = Path(tmp)
            (root / "p3_007_aggregate_results.json").write_text("{}", encoding="utf-8")
            (root / "p3_007_manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(sb.BundleError, "aggregate SHA-256 mismatch"):
                sb.build_bundle(root)

    def test_content_hash_rejects_edit_and_schema_checks_reconcile(self) -> None:
        edited = copy.deepcopy(self.bundle)
        edited["data"]["rfm"]["reference_profiles"]["Champions"]["n"] += 1
        with self.assertRaisesRegex(sb.BundleError, "content hash"):
            sb.validate_bundle(edited)
        malformed = copy.deepcopy(self.bundle)
        malformed["data"]["kmeans"]["reference_profiles"].pop("2")
        malformed["content_sha256"] = sb._canonical_hash(malformed["data"])
        with self.assertRaisesRegex(sb.BundleError, "approved application pin"):
            sb.validate_bundle(malformed)
        with self.assertRaisesRegex(sb.BundleError, "must contain clusters"):
            sb._validate_data(malformed["data"])


if __name__ == "__main__":
    unittest.main()

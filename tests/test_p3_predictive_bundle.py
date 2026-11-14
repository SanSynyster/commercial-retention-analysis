from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src import p3_predictive_bundle as bundle_mod


class PredictiveBundleTests(unittest.TestCase):
    def test_committed_bundle_schema_checksum_and_evidence_labels(self) -> None:
        bundle = bundle_mod.load_bundle()
        self.assertEqual(bundle["evidence"]["analysis_type"], "Historical prediction")
        self.assertEqual(bundle["evidence"]["development"], "Development — used for model selection")
        self.assertEqual(bundle["evidence"]["holdout"], "Previously examined holdout — exploratory")
        self.assertIn("no confirmatory", bundle["evidence"]["causal_status"])
        self.assertEqual(bundle["selection"]["reference_model"], "Random Forest")
        self.assertEqual(set(bundle["models"]), set(bundle_mod.MODEL_NAMES))

    def test_bundle_contains_only_aggregate_safe_relative_provenance(self) -> None:
        path = bundle_mod.DEFAULT_BUNDLE
        raw = path.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", raw)
        self.assertNotIn("customer_id", raw)
        self.assertNotIn("development_predictions_private.parquet", raw)
        self.assertNotIn("individual_shap_explanations.parquet", raw)
        bundle_mod.validate_bundle(json.loads(raw))

    def test_rehashed_bundle_edit_still_fails_reviewed_content_pin(self) -> None:
        bundle = bundle_mod.load_bundle()
        bundle["selection"]["decision"] = "edited"
        bundle["content_sha256"] = bundle_mod._canonical_hash({k: v for k, v in bundle.items() if k != "content_sha256"})
        with self.assertRaisesRegex(bundle_mod.BundleError, "expected committed content pin"):
            bundle_mod.validate_bundle(bundle)

    def test_source_mapping_is_explicit_and_hashes_are_sha256_length(self) -> None:
        self.assertEqual(set(bundle_mod.SOURCES), {"p3_002", "p3_003", "p3_004", "p3_005"})
        bundle = bundle_mod.load_bundle()
        for spec in bundle_mod.SOURCES.values():
            self.assertFalse(any(c in spec["path"] for c in "*?[]"))
            self.assertEqual(len(spec["sha256"]), 64)
            key = next(k for k, v in bundle_mod.SOURCES.items() if v is spec)
            self.assertEqual(bundle["provenance"]["sources"][key]["sha256_raw_file"], spec["sha256"])

    def test_missing_private_source_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(bundle_mod.SourceUnavailableError):
                bundle_mod.build_bundle(Path(temp))

    def test_source_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = bundle_mod.SOURCES["p3_002"]
            aggregate = root / spec["path"]
            manifest = root / spec["manifest"]
            aggregate.parent.mkdir(parents=True)
            aggregate.write_text('{"fake": true}\n', encoding="utf-8")
            manifest.write_text(json.dumps({"aggregate": aggregate.name, "aggregate_sha256": hashlib.sha256(aggregate.read_bytes()).hexdigest()}), encoding="utf-8")
            with self.assertRaisesRegex(bundle_mod.BundleError, "SHA-256 mismatch"):
                bundle_mod._load_source("p3_002", root)

    @unittest.skipUnless(all((bundle_mod.PRIVATE_ROOT / spec["path"]).is_file() and
                             (bundle_mod.PRIVATE_ROOT / spec["manifest"]).is_file()
                             for spec in bundle_mod.SOURCES.values()),
                         "Private P3 aggregate sources are unavailable")
    def test_private_source_rebuild_is_deterministic_and_matches_committed_bundle(self) -> None:
        first = bundle_mod.build_bundle()
        second = bundle_mod.build_bundle()
        first_bytes = json.dumps(first, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
        second_bytes = json.dumps(second, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(first, bundle_mod.load_bundle())

    def test_frequency_has_no_probability_metrics_but_keeps_ranking_metrics(self) -> None:
        frequency = bundle_mod.load_bundle()["models"]["Frequency"]
        self.assertIsNone(frequency["development"]["brier_score"])
        self.assertIsNone(frequency["development"]["log_loss"])
        self.assertIsInstance(frequency["development"]["roc_auc"], float)
        self.assertIsInstance(frequency["development"]["top_decile_precision"], float)


if __name__ == "__main__":
    unittest.main()

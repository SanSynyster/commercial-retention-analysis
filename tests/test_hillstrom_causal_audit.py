from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import hillstrom_causal_audit as audit


class HillstromAuditTests(unittest.TestCase):
    def test_split_is_reproducible_stratified_and_disjoint(self):
        frame = pd.DataFrame({"segment": ["Mens E-Mail"] * 30 + ["Womens E-Mail"] * 30 + ["No E-Mail"] * 30})
        a = audit.make_stratified_split(frame, seed=41)
        b = audit.make_stratified_split(frame, seed=41)
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(a.split.value_counts().to_dict(), {"train": 54, "development": 18, "test": 18})
        for arm in audit.ARMS:
            row_ids = frame.index[frame.segment.eq(arm)]
            counts = a.loc[row_ids].split.value_counts().to_dict()
            self.assertEqual(counts, {"train": 18, "development": 6, "test": 6})
        self.assertEqual(a.row_index.nunique(), len(frame))
        self.assertEqual(set(a.split), {"train", "development", "test"})

    def test_missing_assignment_is_rejected(self):
        with self.assertRaises(ValueError):
            audit.make_stratified_split(pd.DataFrame({"segment": ["Mens E-Mail", None]}))

    def test_standardized_mean_difference_detects_imbalance(self):
        frame = pd.DataFrame({
            "segment": ["Mens E-Mail"] * 4 + ["Womens E-Mail"] * 4 + ["No E-Mail"] * 4,
            "recency": [1, 1, 2, 2, 8, 8, 9, 9, 4, 4, 5, 5],
            "history": [1.0] * 12,
            "mens": [0, 1] * 6,
            "womens": [1, 0] * 6,
            "newbie": [0, 1] * 6,
            "history_segment": ["a", "b"] * 6,
            "zip_code": ["urban", "rural"] * 6,
            "channel": ["web", "phone"] * 6,
        })
        smd = audit.standardized_mean_differences(frame)
        self.assertIn("Mens E-Mail vs No E-Mail", smd)
        self.assertGreater(abs(smd["Mens E-Mail vs Womens E-Mail"]["recency"]), 1.0)

    def test_audit_writes_private_aggregate_and_rejects_invalid_outcome_relation(self):
        rows = []
        for arm in audit.ARMS:
            for i in range(20):
                conversion = int(i == 0)
                rows.append({
                    "recency": 1 + i % 12, "history_segment": "1) $0 - $100",
                    "history": float(i), "mens": i % 2, "womens": (i + 1) % 2,
                    "zip_code": "Urban", "newbie": i % 2, "channel": "Web",
                    "segment": arm, "visit": int(conversion or i == 1),
                    "conversion": conversion, "spend": float(conversion * 10),
                })
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.csv"
            pd.DataFrame(rows).to_csv(source, index=False)
            result = audit.audit_dataset(source, root / "outputs", seed=7)
            self.assertEqual(result["dataset"]["rows"], 60)
            self.assertEqual(result["split"]["allocation_by_arm"]["train"],
                             {"Mens E-Mail": 12, "Womens E-Mail": 12, "No E-Mail": 12})
            invalid = pd.DataFrame(rows)
            invalid.loc[1, "spend"] = 1.0
            invalid.to_csv(source, index=False)
            with self.assertRaises(ValueError):
                audit.audit_dataset(source, root / "invalid_outputs", seed=7)


if __name__ == "__main__":
    unittest.main()

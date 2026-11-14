from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE_APP = ROOT / "tests/causal_evidence_page_app.py"


class CausalEvidencePageTests(unittest.TestCase):
    def test_page_primary_secondary_and_development_interactions(self) -> None:
        app = AppTest.from_file(str(PAGE_APP), default_timeout=60).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "Causal Evidence & Experimentation")
        self.assertTrue(any("separate randomized email experiment" in x.value for x in app.caption))
        self.assertTrue(any("Confirmatory randomised evidence — locked test" in x.value for x in app.success))
        self.assertTrue(any("+8.1627 percentage points" in x.value for x in app.metric if x.label == "Risk difference"))
        self.assertTrue(any("1.53e-26" in x.value for x in app.caption))
        app.selectbox(key="causal_secondary_contrast").set_value("Men's email vs Women's email").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertTrue(any("0.000359" in x.value for x in app.metric if x.label == "Holm-adjusted p-value"))
        self.assertTrue(any("Men's email: 802/4,262" in x.value and "Women's email: 663/4,277" in x.value for x in app.caption))
        self.assertTrue(any("Difference is first arm minus second arm" in x.value for x in app.caption))
        page_source = (ROOT / "app/views/causal_evidence.py").read_text()
        self.assertIn("First-arm visit rate", page_source)
        self.assertIn("Second-arm visit rate", page_source)
        self.assertTrue(any("per 1,000 eligible experiment rows" in x.value for x in app.caption))
        self.assertTrue(any("8,523 Men's/no-email locked-test eligible experiment rows" in x.value for x in app.caption))
        self.assertTrue(any("per 1,000 locked-test eligible experiment rows" in x.value for x in app.caption))
        app.selectbox(key="causal_dev_family").set_value("HistGradientBoosting").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        frame = next(x.value for x in app.dataframe if hasattr(x.value, "columns") and "delta_visits_per_1000" in x.value.columns)
        self.assertEqual(frame["label"].tolist(), ["HGB T-learner", "HGB S-learner", "HGB X-learner", "HGB DR-learner"])
        dr = frame.loc[frame["label"] == "HGB DR-learner"].iloc[0]
        self.assertAlmostEqual(float(dr["delta_visits_per_1000"]), 4.928792087720978)
        self.assertLess(float(dr["ci95_low"]), 0)
        self.assertGreater(float(dr["ci95_high"]), 0)


if __name__ == "__main__":
    unittest.main()

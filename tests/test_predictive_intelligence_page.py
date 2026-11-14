from __future__ import annotations

import unittest
from pathlib import Path
import sys

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE_APP = ROOT / "tests/predictive_intelligence_page_app.py"
for path in (ROOT / "app", ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from views.predictive_intelligence import _format_paired_ranking_table


class PredictiveIntelligencePageTests(unittest.TestCase):
    def test_paired_ranking_table_formats_signed_values(self) -> None:
        table = pd.DataFrame([
            {"Difference": 0.25, "95% lower": -0.125, "95% upper": 0.375},
            {"Difference": 0.0, "95% lower": 0.0, "95% upper": 0.0},
        ])
        rendered = _format_paired_ranking_table(table).to_html()
        for value in ("+0.2500", "-0.1250", "+0.3750", "+0.0000"):
            self.assertIn(value, rendered)
        self.assertNotIn("+.4f", rendered)

    def test_predictive_page_renders_interactive_views_with_scientific_labels(self) -> None:
        app = AppTest.from_file(str(PAGE_APP), default_timeout=60).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "Predictive Intelligence")
        self.assertIn("Historical prediction", " ".join(x.value for x in app.caption))
        self.assertTrue(any("17,221 snapshots" in x.value and "12,961 snapshots" in x.value for x in app.caption))
        self.assertTrue(any(x.label == "Chart metric" for x in app.selectbox))
        self.assertTrue(any(x.label == "SHAP population" for x in app.selectbox))
        self.assertTrue(any(x.label == "Calibration evaluation" for x in app.radio))
        app.selectbox(key="p3_shap_period").set_value("Exploratory holdout months").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertTrue(any("approximately 200 explanation observations per month" in x.value and "one model fitted on January–June" in x.value for x in app.caption))
        self.assertTrue(any("Purchase dates (365 days)" in x.label for x in app.metric))
        app.radio(key="p3_predictive_period").set_value("Previously examined holdout — exploratory").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertTrue(any("Random Forest" in str(x.value) for x in app.dataframe))
        app.radio(key="p3_cal_period").set_value("Previously examined holdout — July to November").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertIn("previously examined", " ".join(x.value for x in app.caption).lower())


if __name__ == "__main__":
    unittest.main()

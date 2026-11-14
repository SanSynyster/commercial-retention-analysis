from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGE_APP = ROOT / "tests/segmentation_intelligence_page_app.py"


class SegmentationIntelligencePageTests(unittest.TestCase):
    def test_page_renders_verified_rfm_and_exploratory_cluster_evidence(self) -> None:
        app = AppTest.from_file(str(PAGE_APP), default_timeout=60).run()
        self.assertFalse(app.exception, [error.value for error in app.exception])
        self.assertEqual(app.title[0].value, "Segmentation Intelligence")
        self.assertTrue(any(x.proto.page == "targeting-explorer" for x in app.page_link))
        self.assertIn("Historical description", " ".join(x.value for x in app.caption))
        self.assertTrue(any("4,260" in x.value and "March 2011" in x.value for x in app.caption))
        self.assertTrue(any("March defines the 4,260-customer reference cohort" in x.value and "re-derived at each month's snapshot" in x.value for x in app.caption))
        self.assertTrue(any("meaningful incremental purchase discrimination beyond RFM" in x.value for x in app.info))
        self.assertTrue(any("reviewer-derived April–June AUC diagnostics" in x.value and "absent from the exact verified aggregate" in x.value for x in app.caption))
        cutpoints = next(x.value for x in app.dataframe if hasattr(x.value, "columns") and "Dimension" in x.value.columns)
        self.assertEqual(cutpoints["Dimension"].tolist(), [
            "Recency in days, ascending cutpoint; lower values earn higher R score",
            "Qualifying purchase occasions in prior 365 days",
            "Qualifying gross merchandise in prior 365 days",
        ])
        rfm_frame = next(x.value for x in app.dataframe if hasattr(x.value, "columns") and "Customers" in x.value.columns)
        champions = rfm_frame.loc[rfm_frame["Segment"] == "Champions"].iloc[0]
        self.assertEqual(int(champions["Customers"]), 1023)
        self.assertAlmostEqual(float(champions["Purchase rate"]), 0.4402035623409669)
        app.selectbox(key="p3c_rfm_segment").set_value("Hibernating").run()
        self.assertFalse(app.exception, [error.value for error in app.exception])
        app.selectbox(key="p3c_kmeans_cluster").set_value("Cluster 2").run()
        self.assertFalse(app.exception, [error.value for error in app.exception])
        app.selectbox(key="p3c_transition_period").set_value("Through exploratory replay").run()
        self.assertFalse(app.exception, [error.value for error in app.exception])
        transition = next(x.value for x in app.dataframe if hasattr(x.value, "columns") and "Transition" in x.value.columns)
        self.assertIn("K-Means ARI", transition.columns)
        self.assertIn("RFM ARI", transition.columns)
        self.assertIn("10 → 11", transition["Transition"].tolist())


if __name__ == "__main__":
    unittest.main()

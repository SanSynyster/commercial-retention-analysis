from __future__ import annotations

from datetime import datetime
import unittest

import pandas as pd

from docs.recovery.COMMERCIAL_DS_003_PURCHASE_OCCASIONS import _build_purchase_occasions_for_test
from src.day21_cohort import (
    apply_approved_temporal_split,
    build_day21_cohort,
    cohort_accounting,
    temporal_split_summary,
)


def fixture(lines: list[tuple[str, str, datetime, int, str]]) -> tuple[pd.DataFrame, list[dict]]:
    """Rows are (customer, invoice, timestamp, quantity, stock code)."""
    frame = pd.DataFrame([
        {
            "source_row_number": i,
            "InvoiceNo": invoice,
            "StockCode": stock,
            "Description": "Item",
            "Quantity": qty,
            "InvoiceDate": ts,
            "UnitPrice": 2.5,
            "CustomerID": int(customer),
            "Country": "United Kingdom",
            "category": "merchandise",
        }
        for i, (customer, invoice, ts, qty, stock) in enumerate(lines)
    ])
    occasions, _ = _build_purchase_occasions_for_test(frame)
    return frame, occasions


def cohort_for(
    lines: list[tuple[str, str, datetime, int, str]],
    *,
    end: datetime = datetime(2011, 12, 9, 12, 50),
    source_start: datetime = datetime(2009, 12, 1, 7, 45),
) -> pd.DataFrame:
    frame, occasions = fixture(lines)
    return build_day21_cohort(
        frame, occasions, observation_end=end, source_start_timestamp=source_start
    )


class Day21CohortTests(unittest.TestCase):
    def test_earliest_line_timestamp_selected_within_invoice(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10, 30), 1, "A"),
            ("1", "100001", datetime(2010, 1, 1, 10, 0), 2, "B"),
        ])
        self.assertEqual(cohort.loc[0, "first_qualifying_purchase_timestamp"], pd.Timestamp("2010-01-01 10:00"))
        self.assertEqual(cohort.loc[0, "first_day_occasion_count"], 1)
        self.assertEqual(cohort.loc[0, "first_day_item_quantity"], 3)
        self.assertEqual(cohort.loc[0, "first_day_product_diversity"], 2)

    def test_same_calendar_day_second_invoice_is_not_repeat(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 1, 1, 11), 1, "B"),
        ])
        self.assertTrue(cohort.loc[0, "eligible"])
        self.assertTrue(pd.isna(cohort.loc[0, "second_qualifying_purchase_timestamp"]))

    def test_simultaneous_same_day_occasions_are_not_artificially_ordered(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 1, 1, 10), 1, "B"),
        ])
        self.assertTrue(cohort.loc[0, "eligible"])
        self.assertEqual(cohort.loc[0, "first_day_occasion_count"], 2)
        self.assertTrue(pd.isna(cohort.loc[0, "second_qualifying_purchase_timestamp"]))

    def test_second_at_decision_is_ineligible(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 1, 22, 10), 1, "B"),
        ])
        self.assertFalse(cohort.loc[0, "eligible"])
        self.assertEqual(cohort.loc[0, "exclusion_reason"], "second_purchase_by_day21")

    def test_second_immediately_after_decision_is_positive(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 1, 22, 10, 0, 0, 1), 1, "B"),
        ])
        self.assertTrue(cohort.loc[0, "eligible"])
        self.assertEqual(cohort.loc[0, "outcome_label"], 1)
        self.assertTrue(cohort.loc[0, "complete_horizon_observed"])

    def test_second_exactly_at_day111_is_positive(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 4, 22, 10), 1, "B"),
        ])
        self.assertEqual(cohort.loc[0, "day111_outcome_deadline"], pd.Timestamp("2010-04-22 10"))
        self.assertEqual(cohort.loc[0, "outcome_label"], 1)

    def test_second_after_day111_is_mature_negative(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 4, 22, 10, 0, 0, 1), 1, "B"),
        ])
        self.assertEqual(cohort.loc[0, "outcome_label"], 0)
        self.assertEqual(cohort.loc[0, "outcome_status"], "negative_mature")

    def test_no_event_complete_is_negative_and_incomplete_is_unknown(self):
        lines = [("1", "100001", datetime(2010, 1, 1, 10), 1, "A")]
        mature = cohort_for(lines)
        incomplete = cohort_for(lines, end=datetime(2010, 3, 1, 10))
        self.assertEqual(mature.loc[0, "outcome_label"], 0)
        self.assertTrue(pd.isna(incomplete.loc[0, "outcome_label"]))
        self.assertEqual(incomplete.loc[0, "outcome_status"], "unknown_incomplete_followup")

    def test_observed_positive_with_incomplete_horizon_is_separate(self):
        lines = [
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 2, 5, 10), 1, "B"),
        ]
        cohort = cohort_for(lines, end=datetime(2010, 2, 10, 10))
        self.assertEqual(cohort.loc[0, "outcome_label"], 1)
        self.assertFalse(cohort.loc[0, "complete_horizon_observed"])
        self.assertEqual(cohort.loc[0, "outcome_status"], "positive_incomplete_followup")

    def test_missing_timestamp_fails_closed(self):
        frame, occasions = fixture([("1", "100001", datetime(2010, 1, 1, 10), 1, "A")])
        frame.loc[0, "InvoiceDate"] = pd.NaT
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            build_day21_cohort(frame, occasions)

    def test_invalid_timestamp_fails_closed(self):
        frame, occasions = fixture([("1", "100001", datetime(2010, 1, 1, 10), 1, "A")])
        frame["InvoiceDate"] = frame["InvoiceDate"].astype(object)
        frame.loc[0, "InvoiceDate"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            build_day21_cohort(frame, occasions)

    def test_contradictory_invoice_calendar_date_fails_closed(self):
        frame, occasions = fixture([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100001", datetime(2010, 1, 1, 10, 5), 1, "B"),
        ])
        frame.loc[1, "InvoiceDate"] = datetime(2010, 1, 2, 10)
        with self.assertRaisesRegex(ValueError, "contradictory calendar dates"):
            build_day21_cohort(frame, occasions)

    def test_day21_after_source_end_is_not_observed(self):
        cohort = cohort_for(
            [("1", "100001", datetime(2011, 11, 30, 10), 1, "A")],
            end=datetime(2011, 12, 9, 12, 50),
        )
        self.assertFalse(cohort.loc[0, "decision_observed"])
        self.assertFalse(cohort.loc[0, "eligible"])
        self.assertEqual(cohort.loc[0, "exclusion_reason"], "day21_decision_after_observation_end")

    def test_features_do_not_use_post_decision_transactions(self):
        base = [("1", "100001", datetime(2010, 1, 1, 10), 1, "A")]
        future = base + [("1", "100002", datetime(2010, 3, 1, 10), 99, "FUTURE")]
        a = cohort_for(base).iloc[0]
        b = cohort_for(future).iloc[0]
        for feature in (
            "first_day_qualifying_gross", "first_day_item_quantity",
            "first_day_product_diversity", "first_day_occasion_count",
            "first_purchase_weekday",
        ):
            self.assertEqual(a[feature], b[feature])
        self.assertNotIn("first_purchase_month", b.index)

    def test_cohort_accounting_reconciles(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("1", "100002", datetime(2010, 1, 22, 10), 1, "B"),
            ("2", "200001", datetime(2010, 1, 1, 10), 1, "A"),
        ])
        counts = cohort_accounting(cohort)
        self.assertEqual(counts["identifiable_customers"], 2)
        self.assertEqual(counts["repeated_by_day21"], 1)
        self.assertEqual(counts["eligible"], 1)
        self.assertEqual(counts["mature_positive"] + counts["mature_negative"] + counts["unknown_immature"], 1)

    def test_temporal_split_boundaries_and_asof_label_availability(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("2", "200001", datetime(2010, 10, 1, 10), 1, "A"),
            ("3", "300001", datetime(2011, 1, 1, 10), 1, "A"),
        ])
        summary = temporal_split_summary(cohort, [{
            "name": "fixture", "train_end": "2010-07-01", "validation_end": "2011-01-01", "test_end": "2012-01-01"
        }])
        self.assertEqual(summary.loc[0, "train_eligible"], 1)
        self.assertEqual(summary.loc[0, "validation_eligible"], 1)
        self.assertEqual(summary.loc[0, "test_eligible"], 1)
        self.assertEqual(summary.loc[0, "train_labels_available_by_validation_start"], 1)
        with self.assertRaises(ValueError):
            temporal_split_summary(cohort, [{
                "name": "bad", "train_end": "2011-01-01", "validation_end": "2010-07-01", "test_end": "2012-01-01"
            }])

    def test_12_month_acquisition_boundary_and_explicit_exclusion(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 12, 1, 7, 44, 59), 1, "A"),
            ("2", "200001", datetime(2010, 12, 1, 7, 45), 1, "A"),
        ])
        earlier = cohort[cohort["customer_id"] == "1"].iloc[0]
        at_boundary = cohort[cohort["customer_id"] == "2"].iloc[0]
        self.assertFalse(earlier["acquisition_eligible"])
        self.assertEqual(earlier["acquisition_exclusion_reason"], "insufficient_12_month_qualifying_history")
        self.assertTrue(at_boundary["acquisition_eligible"])
        self.assertEqual(at_boundary["acquisition_lookback_months"], 12)

    def test_asof_split_excludes_labels_that_mature_after_cutoff(self):
        cohort = cohort_for([
            ("1", "100001", datetime(2010, 1, 1, 10), 1, "A"),
            ("2", "200001", datetime(2010, 4, 1, 10), 1, "A"),
            ("3", "300001", datetime(2010, 7, 1, 10), 1, "A"),
        ], source_start=datetime(2009, 1, 1, 0))
        split = apply_approved_temporal_split(cohort, cutoff=pd.Timestamp("2010-07-01"))
        by_customer = split.set_index("customer_id")
        self.assertEqual(by_customer.loc["1", "evaluation_partition"], "train")
        self.assertEqual(by_customer.loc["2", "evaluation_partition"], "pre_cutoff_label_not_available")
        self.assertEqual(by_customer.loc["3", "evaluation_partition"], "test")
        self.assertTrue(by_customer.loc["1", "training_label_available_at_cutoff"])
        self.assertFalse(by_customer.loc["2", "training_label_available_at_cutoff"])
        train = split[split["evaluation_partition"] == "train"]
        self.assertTrue((train["day111_outcome_deadline"] <= pd.Timestamp("2010-07-01")).all())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "recovery"))
sys.path.insert(0, str(ROOT / "src"))

from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import _build_purchase_occasions_for_test
from monthly_customer_snapshots import (
    FEATURE_COLUMNS,
    _window_is_covered,
    build_monthly_customer_snapshots,
    generate_monthly_anchors,
    snapshot_accounting,
)


def _source(rows: list[tuple[str, str, str, int, str, str]]) -> tuple[pd.DataFrame, list[dict]]:
    frame = pd.DataFrame(
        [
            {
                "source_row_number": i,
                "CustomerID": 10001,
                "InvoiceNo": invoice,
                "StockCode": sku,
                "Quantity": quantity,
                "UnitPrice": float(price),
                "InvoiceDate": pd.Timestamp(timestamp),
                "category": _unused or "merchandise",
            }
            for i, (invoice, timestamp, sku, quantity, price, _unused) in enumerate(rows)
        ]
    )
    occasions, _ = _build_purchase_occasions_for_test(frame)
    return frame, occasions


def _row(invoice: str, timestamp: str, sku: str = "A", quantity: int = 1, price: str = "10.00", category: str = "merchandise"):
    return (invoice, timestamp, sku, quantity, price, category)


def _build(rows, end="2011-02-15 00:00:00", coverage=None):
    frame, occasions = _source(rows)
    return build_monthly_customer_snapshots(
        frame,
        occasions,
        observation_start_timestamp=pd.Timestamp(frame.InvoiceDate.min()),
        observation_end_timestamp=pd.Timestamp(frame.InvoiceDate.max()),
        coverage_intervals=coverage,
        train_cutoff=pd.Timestamp("2011-02-01"),
    )


def _jan_snapshot(rows, end="2011-02-15 00:00:00", coverage=None):
    # Non-merchandise sentinels establish covered source bounds without adding
    # canonical qualifying purchases.
    rows = [_row("900", "2010-01-01 00:00:00", category="non_merchandise"), *rows]
    if end > "2011-01-01":
        rows.append(_row("901", end, category="non_merchandise"))
    frame, occasions = _source(rows)
    return build_monthly_customer_snapshots(
        frame,
        occasions,
        observation_start_timestamp=pd.Timestamp(frame.InvoiceDate.min()),
        observation_end_timestamp=pd.Timestamp(frame.InvoiceDate.max()),
        coverage_intervals=coverage,
        train_cutoff=pd.Timestamp("2011-02-01"),
    )


class TestMonthlyCustomerSnapshots(unittest.TestCase):
    def test_monthly_anchors_require_full_history_and_use_month_start(self):
        anchors = generate_monthly_anchors(pd.Timestamp("2010-01-01"), pd.Timestamp("2011-02-15"), lookback_days=365)
        assert anchors[0] == pd.Timestamp("2011-01-01")
        assert anchors[-1] == pd.Timestamp("2011-02-01")


    def test_decision_timestamp_is_exclusive_for_features_and_inclusive_for_outcomes(self):
        rows = [_row("100", "2010-12-31 23:59:00"), _row("101", "2011-01-01 00:00:00")]
        snapshots, _ = _jan_snapshot(rows)
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.qualifying_purchase_occasions_365d == 1
        assert jan.outcome_label == 1
        assert jan.outcome_window_mature


    def test_exact_30_day_deadline_is_excluded_from_outcome(self):
        rows = [_row("100", "2010-12-31 23:59:00"), _row("101", "2011-01-31 00:00:00")]
        snapshots, _ = _jan_snapshot(rows)
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.outcome_label == 0
        assert jan.outcome_status == "negative_mature"
        assert pd.isna(jan.median_interpurchase_interval_days_365d)


    def test_mature_no_purchase_is_negative_and_incomplete_no_purchase_is_unknown(self):
        rows = [_row("100", "2010-12-31 23:59:00")]
        mature, _ = _jan_snapshot(rows)
        jan = mature.loc[mature.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.outcome_label == 0
        assert jan.outcome_status == "negative_mature"

        # The transaction maximum also determines observed bounds, so the coverage
        # intervals express that the 30-day horizon is only partially observed.
        coverage = [(pd.Timestamp("2010-01-01"), pd.Timestamp("2011-01-10"))]
        partial, _ = _jan_snapshot(rows, coverage=coverage)
        jan = partial.loc[partial.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert pd.isna(jan.outcome_label)
        assert jan.outcome_status == "unknown_incomplete_followup"


    def test_observed_positive_before_incomplete_horizon_is_retained(self):
        rows = [_row("100", "2010-12-31 23:59:00"), _row("101", "2011-01-05 12:00:00")]
        coverage = [(pd.Timestamp("2010-01-01"), pd.Timestamp("2011-01-10"))]
        snapshots, _ = _jan_snapshot(rows, coverage=coverage)
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.outcome_label == 1
        assert not jan.outcome_window_mature
        assert jan.observed_positive_in_incomplete_window


    def test_observation_gap_prevents_mature_negative(self):
        intervals = [
            (pd.Timestamp("2010-01-01"), pd.Timestamp("2011-01-10")),
            (pd.Timestamp("2011-01-12"), pd.Timestamp("2011-02-15 00:00:00")),
        ]
        assert not _window_is_covered(pd.Timestamp("2011-01-01"), pd.Timestamp("2011-01-31"), intervals)
        rows = [_row("100", "2010-12-31 23:59:00")]
        snapshots, _ = _jan_snapshot(rows, coverage=intervals)
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.outcome_status == "unknown_incomplete_followup"
        assert pd.isna(jan.outcome_label)


    def test_customer_month_uniqueness_and_repeated_customer_across_partitions(self):
        rows = [
            _row("100", "2010-12-31 23:59:00"),
            _row("101", "2011-01-15 12:00:00"),
            _row("102", "2011-02-10 12:00:00"),
        ]
        snapshots, metadata = _jan_snapshot(rows, end="2011-04-01 00:00:00")
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        feb = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-02-01"))].iloc[0]
        assert jan.evaluation_partition == "train"
        assert feb.evaluation_partition == "test"
        assert snapshots.duplicated(["customer_id", "decision_time"]).sum() == 0
        assert snapshot_accounting(snapshots, {"train_cutoff": metadata["train_cutoff"], "anchor_summary": metadata["anchor_summary"], "occasion_summary": metadata["occasion_summary"]})["training_test_unique_customer_overlap"] == 1


    def test_training_label_must_be_available_by_cutoff(self):
        rows = [_row("900", "2010-01-01 00:00:00", category="non_merchandise"),
                _row("100", "2010-12-31 23:59:00"),
                _row("901", "2011-02-15 00:00:00", category="non_merchandise")]
        frame, occasions = _source(rows)
        coverage = [(pd.Timestamp("2010-01-01"), pd.Timestamp("2011-03-01"))]
        snapshots, _ = build_monthly_customer_snapshots(
            frame,
            occasions,
            observation_start_timestamp=pd.Timestamp("2010-01-01"),
            observation_end_timestamp=pd.Timestamp(frame.InvoiceDate.max()),
            coverage_intervals=coverage,
            train_cutoff=pd.Timestamp("2011-01-15"),
        )
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.evaluation_partition == "pre_cutoff_label_not_available"
        assert not jan.training_label_available_at_cutoff


    def test_multiple_line_timestamps_in_invoice_use_earliest_occasion_time(self):
        rows = [
            _row("900", "2010-01-01 00:00:00", category="non_merchandise"),
            _row("100", "2010-12-31 10:00:00", "A"),
            _row("100", "2010-12-31 09:00:00", "B", 2, "5.00"),
            _row("901", "2011-02-15 00:00:00", category="non_merchandise"),
        ]
        frame, occasions = _source(rows)
        snapshots, _ = build_monthly_customer_snapshots(
            frame,
            occasions,
            observation_start_timestamp=pd.Timestamp(frame.InvoiceDate.min()),
            observation_end_timestamp=pd.Timestamp(frame.InvoiceDate.max()),
        )
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        assert jan.last_qualifying_purchase_timestamp_before_decision == pd.Timestamp("2010-12-31 09:00:00")
        assert jan.qualifying_purchase_occasions_365d == 1

    def test_fixed_365_day_feature_window_includes_lower_and_excludes_outside_events(self):
        rows = [
            _row("100", "2009-12-31 23:59:59.999999", "OLD", 10, "100.00"),
            _row("101", "2010-01-01 00:00:00", "LOW", 2, "10.00"),
            _row("102", "2010-12-31 23:59:59.999999", "REC", 1, "10.00"),
            _row("103", "2011-01-01 00:00:00", "FUT", 3, "10.00"),
        ]
        snapshots, _ = _jan_snapshot(rows)
        jan = snapshots.loc[snapshots.decision_time.eq(pd.Timestamp("2011-01-01"))].iloc[0]
        self.assertEqual(jan.qualifying_purchase_occasions_365d, 2)
        self.assertEqual(jan.qualifying_purchase_dates_365d, 2)
        self.assertAlmostEqual(jan.qualifying_gross_merchandise_365d, 30.0)
        self.assertAlmostEqual(jan.average_qualifying_basket_value_365d, 15.0)
        self.assertAlmostEqual(jan.average_qualifying_basket_quantity_365d, 1.5)
        self.assertEqual(jan.qualifying_unique_product_count_365d, 2)
        self.assertEqual(jan.median_interpurchase_interval_days_365d, 364.0)
        self.assertGreater(jan.days_since_last_qualifying_purchase, 0.0)
        self.assertLess(jan.days_since_last_qualifying_purchase, 1 / 86400)
        # The purchase exactly at T is an outcome, not a feature.
        self.assertEqual(jan.outcome_label, 1)
        self.assertTrue(jan.outcome_window_mature)

    def test_snapshot_month_is_metadata_not_a_predictor(self):
        self.assertNotIn("snapshot_month", FEATURE_COLUMNS)
        self.assertFalse(any(name.startswith("observed_") for name in FEATURE_COLUMNS))
        self.assertNotIn("days_since_first_observed_qualifying_purchase", FEATURE_COLUMNS)
        self.assertEqual(len(FEATURE_COLUMNS), len(set(FEATURE_COLUMNS)))

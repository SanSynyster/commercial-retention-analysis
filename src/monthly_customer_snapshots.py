"""Build established-customer monthly snapshots with fixed 30-day outcomes.

The module uses the frozen corrected-V2 transaction and purchase-occasion API.
Customer-level Parquet output must be written outside the Git repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_DIR = REPO_ROOT / "docs" / "recovery"
sys.path.insert(0, str(RECOVERY_DIR))

import COMMERCIAL_DS_002_ANALYSIS as source_audit  # noqa: E402
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (  # noqa: E402
    DATA_END_TIMESTAMP,
    load_validated_purchase_input,
    build_purchase_occasions,
)


ACTIVE_LOOKBACK_DAYS = 365
RECENT_LOOKBACK_DAYS = 90
OUTCOME_HORIZON_DAYS = 30
APPROVED_TRAIN_CUTOFF = pd.Timestamp("2011-07-01 00:00:00")
SNAPSHOT_VERSION = "monthly-customer-snapshots-v1"
FEATURE_COLUMNS = (
    "days_since_last_qualifying_purchase",
    "qualifying_purchase_occasions_365d",
    "qualifying_purchase_dates_365d",
    "qualifying_gross_merchandise_365d",
    "average_qualifying_basket_value_365d",
    "average_qualifying_basket_quantity_365d",
    "average_basket_product_diversity_365d",
    "qualifying_unique_product_count_365d",
    "median_interpurchase_interval_days_365d",
    "qualifying_purchase_occasions_90d",
    "qualifying_gross_merchandise_90d",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: Any, field: str) -> pd.Timestamp:
    if not isinstance(value, (datetime, pd.Timestamp)):
        raise TypeError(f"{field} must be a typed timezone-naive timestamp.")
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is not None:
        raise ValueError(f"{field} must be a valid timezone-naive timestamp.")
    return stamp


def _coverage_intervals(
    source_start: pd.Timestamp,
    source_end: pd.Timestamp,
    intervals: Iterable[tuple[datetime | pd.Timestamp, datetime | pd.Timestamp]] | None,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Normalize half-open observation intervals and merge overlaps."""
    end_exclusive = source_end + pd.Timedelta(nanoseconds=1)
    raw = intervals if intervals is not None else [(source_start, end_exclusive)]
    normalized: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for start, end in raw:
        left = max(_timestamp(start, "coverage interval start"), source_start)
        right = min(_timestamp(end, "coverage interval end"), end_exclusive)
        if right <= left:
            raise ValueError("Coverage intervals must have positive duration within source bounds.")
        normalized.append((left, right))
    if not normalized:
        raise ValueError("At least one observation coverage interval is required.")
    merged: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for left, right in sorted(normalized):
        if not merged or left > merged[-1][1]:
            merged.append((left, right))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
    return merged


def _window_is_covered(
    start: pd.Timestamp,
    end_exclusive: pd.Timestamp,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> bool:
    if end_exclusive <= start:
        raise ValueError("Coverage window must have positive duration.")
    cursor = start
    for left, right in intervals:
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end_exclusive:
            return True
    return False


def generate_monthly_anchors(
    observation_start: datetime | pd.Timestamp,
    observation_end: datetime | pd.Timestamp,
    *,
    lookback_days: int = ACTIVE_LOOKBACK_DAYS,
) -> list[pd.Timestamp]:
    """Return observed month-start decision points with complete 365-day history."""
    start = _timestamp(observation_start, "observation start")
    end = _timestamp(observation_end, "observation end")
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or lookback_days <= 0:
        raise ValueError("lookback_days must be a positive integer.")
    candidates = pd.date_range(start=start.to_period("M").start_time, end=end.to_period("M").start_time, freq="MS")
    return [
        anchor
        for anchor in candidates
        if start <= anchor <= end
        and anchor - pd.Timedelta(days=lookback_days) >= start
    ]


def _canonical_events(
    classified_transactions: pd.DataFrame,
    canonical_occasions: list[dict[str, Any]],
    *,
    observation_start: pd.Timestamp,
    observation_end: pd.Timestamp,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    required = {
        "source_row_number", "CustomerID", "InvoiceNo", "StockCode",
        "Quantity", "UnitPrice", "InvoiceDate", "category",
    }
    missing = required - set(classified_transactions.columns)
    if missing:
        raise ValueError(f"Classified source frame missing columns: {sorted(missing)}")
    if not canonical_occasions:
        raise ValueError("Canonical purchase-occasion input is empty.")

    dates = pd.to_datetime(classified_transactions["InvoiceDate"], errors="coerce")
    if dates.isna().any() or getattr(dates.dt, "tz", None) is not None:
        raise ValueError("Transaction timestamps must be valid timezone-naive values.")
    if dates.min() != observation_start or dates.max() != observation_end:
        raise ValueError("Configured observation bounds do not match source timestamps.")

    occasions_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    source_ids: set[int] = set()
    for item in canonical_occasions:
        key = (str(item["customer_id"]), str(item["invoice_id"]))
        if key in occasions_by_key:
            raise ValueError("Duplicate canonical customer × invoice occasion.")
        ids = [int(value) for value in item["source_row_numbers"]]
        if len(ids) != len(set(ids)) or source_ids.intersection(ids):
            raise ValueError("Canonical source-row lineage is duplicated.")
        source_ids.update(ids)
        occasions_by_key[key] = item

    lines = classified_transactions.loc[classified_transactions["source_row_number"].isin(source_ids)].copy()
    if len(lines) != len(source_ids):
        raise ValueError("Canonical source-row lineage does not match classified source rows.")
    lines["_timestamp"] = dates.loc[lines.index]
    lines["_customer_key"] = lines["CustomerID"].map(lambda value: str(int(value)) if pd.notna(value) else None)
    lines["_invoice_key"] = lines["InvoiceNo"].astype(str)

    events_by_customer: dict[str, list[dict[str, Any]]] = {}
    event_count = 0
    for (customer, invoice), rows in lines.groupby(["_customer_key", "_invoice_key"], sort=False):
        key = (str(customer), str(invoice))
        canonical = occasions_by_key.get(key)
        if canonical is None:
            raise ValueError("Qualifying source occasion is absent from canonical records.")
        timestamps = rows["_timestamp"]
        if timestamps.dt.date.nunique() != 1:
            raise ValueError("Canonical qualifying invoice has contradictory calendar dates.")
        if timestamps.min().date().isoformat() != canonical["transaction_date"]:
            raise ValueError("Canonical occasion date disagrees with its source lines.")
        if len(rows) != int(canonical["eligible_line_count"]):
            raise ValueError("Canonical occasion line count disagrees with source lines.")
        if set(rows["source_row_number"].astype(int)) != set(map(int, canonical["source_row_numbers"])):
            raise ValueError("Canonical occasion lineage disagrees with source lines.")
        if not rows["category"].eq("merchandise").all():
            raise ValueError("A non-merchandise row entered canonical purchase lineage.")
        event = {
            "customer_id": str(customer),
            "invoice_id": str(invoice),
            "occasion_timestamp": pd.Timestamp(timestamps.min()),
            "purchase_date": pd.Timestamp(timestamps.min()).normalize(),
            "gross": Decimal(str(canonical["qualifying_gross_merchandise"])),
            "quantity": float(rows["Quantity"].sum()),
            "product_codes": frozenset(rows["StockCode"].astype(str)),
        }
        if not observation_start <= event["occasion_timestamp"] <= observation_end:
            raise ValueError("Canonical occasion timestamp is outside source observation bounds.")
        events_by_customer.setdefault(str(customer), []).append(event)
        event_count += 1
    if event_count != len(occasions_by_key):
        raise ValueError("Canonical occasions and source invoice groups do not reconcile.")
    for events in events_by_customer.values():
        events.sort(key=lambda event: (event["occasion_timestamp"], event["invoice_id"]))
    return events_by_customer, {
        "identifiable_customers": len(events_by_customer),
        "qualifying_purchase_occasions": event_count,
        "qualifying_source_rows": len(source_ids),
    }


def _gross_sum(events: list[dict[str, Any]]) -> float:
    return float(sum((event["gross"] for event in events), Decimal(0)))


def _features_for_history(
    history: list[dict[str, Any]],
    *,
    decision_time: pd.Timestamp,
    feature_window_start: pd.Timestamp,
) -> dict[str, Any]:
    window_history = [
        event for event in history
        if feature_window_start <= event["occasion_timestamp"] < decision_time
    ]
    if not window_history:
        raise ValueError("An eligible snapshot must have a qualifying occasion in its 365-day feature window.")
    recent_90_start = decision_time - pd.Timedelta(days=RECENT_LOOKBACK_DAYS)
    recent_90 = [event for event in window_history if event["occasion_timestamp"] >= recent_90_start]
    dates = sorted({event["purchase_date"] for event in window_history})
    interval_days = [(right - left).days for left, right in zip(dates, dates[1:])]
    all_products = set().union(*(event["product_codes"] for event in window_history))
    window_gross = _gross_sum(window_history)
    return {
        "days_since_last_qualifying_purchase": (decision_time - window_history[-1]["occasion_timestamp"]).total_seconds() / 86400.0,
        "qualifying_purchase_occasions_365d": len(window_history),
        "qualifying_purchase_dates_365d": len(dates),
        "qualifying_gross_merchandise_365d": window_gross,
        "average_qualifying_basket_value_365d": window_gross / len(window_history),
        "average_qualifying_basket_quantity_365d": sum(event["quantity"] for event in window_history) / len(window_history),
        "average_basket_product_diversity_365d": sum(len(event["product_codes"]) for event in window_history) / len(window_history),
        "qualifying_unique_product_count_365d": len(all_products),
        "median_interpurchase_interval_days_365d": float(pd.Series(interval_days).median()) if interval_days else pd.NA,
        "qualifying_purchase_occasions_90d": len(recent_90),
        "qualifying_gross_merchandise_90d": _gross_sum(recent_90),
    }


def build_monthly_customer_snapshots(
    classified_transactions: pd.DataFrame,
    canonical_occasions: list[dict[str, Any]],
    *,
    observation_start_timestamp: datetime | pd.Timestamp | None = None,
    observation_end_timestamp: datetime | pd.Timestamp | None = None,
    coverage_intervals: Iterable[tuple[datetime | pd.Timestamp, datetime | pd.Timestamp]] | None = None,
    train_cutoff: datetime | pd.Timestamp = APPROVED_TRAIN_CUTOFF,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Construct one row per eligible customer-month with 30-day labels.

    Coverage intervals, when supplied, are half-open `[start, end)` spans.
    The default is the verified continuous corrected-source interval, inclusive
    of its final timestamp via a one-nanosecond exclusive upper boundary.
    """
    if "InvoiceDate" not in classified_transactions.columns or classified_transactions.empty:
        raise ValueError("A non-empty classified transaction frame is required.")
    all_timestamps = pd.to_datetime(classified_transactions["InvoiceDate"], errors="coerce")
    if all_timestamps.isna().any() or getattr(all_timestamps.dt, "tz", None) is not None:
        raise ValueError("Source timestamps must be valid timezone-naive values.")
    source_start = _timestamp(
        all_timestamps.min() if observation_start_timestamp is None else observation_start_timestamp,
        "observation start",
    )
    source_end = _timestamp(
        all_timestamps.max() if observation_end_timestamp is None else observation_end_timestamp,
        "observation end",
    )
    cutoff = _timestamp(train_cutoff, "training cutoff")
    if source_end < source_start or all_timestamps.min() != source_start or all_timestamps.max() != source_end:
        raise ValueError("Observation bounds must match the transaction timestamp extrema.")
    intervals = _coverage_intervals(source_start, source_end, coverage_intervals)
    events_by_customer, occasion_summary = _canonical_events(
        classified_transactions, canonical_occasions,
        observation_start=source_start, observation_end=source_end,
    )
    anchors = pd.date_range(source_start.to_period("M").start_time, source_end.to_period("M").start_time, freq="MS")
    rows: list[dict[str, Any]] = []
    anchor_summary: list[dict[str, Any]] = []
    for decision_time in anchors:
        if decision_time < source_start or decision_time > source_end:
            anchor_summary.append({"snapshot_month": decision_time.strftime("%Y-%m"), "anchor_observed": False,
                                   "history_window_complete": False, "candidate_known_customers": 0,
                                   "eligible_snapshots": 0, "excluded_no_recent_365d_purchase": 0,
                                   "incomplete_history_coverage_excluded": 0})
            continue
        history_start = decision_time - pd.Timedelta(days=ACTIVE_LOOKBACK_DAYS)
        known_histories = {
            customer: [event for event in events if event["occasion_timestamp"] < decision_time]
            for customer, events in events_by_customer.items()
        }
        known_histories = {customer: history for customer, history in known_histories.items() if history}
        history_complete = _window_is_covered(history_start, decision_time, intervals)
        if not history_complete:
            anchor_summary.append({"snapshot_month": decision_time.strftime("%Y-%m"), "anchor_observed": True,
                                   "history_window_complete": False, "candidate_known_customers": len(known_histories),
                                   "eligible_snapshots": 0, "excluded_no_recent_365d_purchase": 0,
                                   "incomplete_history_coverage_excluded": len(known_histories)})
            continue
        eligible_histories = {
            customer: history for customer, history in known_histories.items()
            if any(event["occasion_timestamp"] >= history_start for event in history)
        }
        outcome_end = decision_time + pd.Timedelta(days=OUTCOME_HORIZON_DAYS)
        outcome_complete = _window_is_covered(decision_time, outcome_end, intervals)
        for customer, history in eligible_histories.items():
            future_purchases = [
                event for event in events_by_customer[customer]
                if decision_time <= event["occasion_timestamp"] < outcome_end
            ]
            observed_positive = bool(future_purchases)
            if observed_positive:
                label: Any = 1
                status = "positive_mature" if outcome_complete else "positive_incomplete_followup"
            elif outcome_complete:
                label = 0
                status = "negative_mature"
            else:
                label = pd.NA
                status = "unknown_incomplete_followup"
            partition = "not_evaluated_immature"
            if decision_time < cutoff:
                if outcome_complete and outcome_end <= cutoff:
                    partition = "train"
                else:
                    partition = "pre_cutoff_label_not_available"
            elif outcome_complete:
                partition = "test"

            row = {
                "customer_id": customer,
                "snapshot_month": decision_time.strftime("%Y-%m"),
                "decision_time": decision_time,
                "feature_window_start": history_start,
                "feature_window_end_exclusive": decision_time,
                "first_observed_qualifying_purchase_timestamp": history[0]["occasion_timestamp"],
                "last_qualifying_purchase_timestamp_before_decision": history[-1]["occasion_timestamp"],
                "historical_feature_coverage_complete": True,
                "active_in_trailing_365d": True,
                "outcome_window_end_exclusive": outcome_end,
                "outcome_window_mature": outcome_complete,
                "observed_positive_in_incomplete_window": observed_positive and not outcome_complete,
                "outcome_label": label,
                "outcome_status": status,
                "outcome_coverage_status": (
                    "complete" if outcome_complete else
                    "interrupted_coverage" if outcome_end <= intervals[-1][1] else "right_censored_at_source_end"
                ),
                "evaluation_partition": partition,
                "training_label_available_at_cutoff": partition == "train",
            }
            row.update(_features_for_history(history, decision_time=decision_time, feature_window_start=history_start))
            rows.append(row)

        anchor_summary.append({
            "snapshot_month": decision_time.strftime("%Y-%m"),
            "anchor_observed": True,
            "history_window_complete": True,
            "candidate_known_customers": len(known_histories),
            "eligible_snapshots": len(eligible_histories),
            "excluded_no_recent_365d_purchase": len(known_histories) - len(eligible_histories),
            "incomplete_history_coverage_excluded": 0,
            "outcome_window_mature": outcome_complete,
            "train_cutoff": cutoff.isoformat(sep=" "),
        })

    snapshots = pd.DataFrame(rows)
    if snapshots.empty:
        raise ValueError("No eligible customer-month snapshots were constructed.")
    snapshots["outcome_label"] = snapshots["outcome_label"].astype("Int64")
    for col in ("decision_time", "feature_window_start", "feature_window_end_exclusive",
                "first_observed_qualifying_purchase_timestamp", "last_qualifying_purchase_timestamp_before_decision",
                "outcome_window_end_exclusive"):
        snapshots[col] = pd.to_datetime(snapshots[col])
    return snapshots, {
        "source_start_timestamp": source_start.isoformat(sep=" "),
        "source_end_timestamp": source_end.isoformat(sep=" "),
        "coverage_intervals": [{"start_inclusive": left.isoformat(sep=" "), "end_exclusive": right.isoformat(sep=" ")}
                                for left, right in intervals],
        "anchor_summary": anchor_summary,
        "occasion_summary": occasion_summary,
        "train_cutoff": cutoff.isoformat(sep=" "),
    }


def snapshot_accounting(snapshots: pd.DataFrame, metadata: dict[str, Any]) -> dict[str, Any]:
    """Assert snapshot, label and chronological-partition accounting."""
    required = {
        "customer_id", "decision_time", "outcome_label", "outcome_window_mature",
        "outcome_status", "evaluation_partition", "training_label_available_at_cutoff",
        *FEATURE_COLUMNS,
    }
    missing = required - set(snapshots.columns)
    if missing:
        raise ValueError(f"Snapshot frame missing required fields: {sorted(missing)}")
    if snapshots.duplicated(["customer_id", "decision_time"]).any():
        raise AssertionError("Duplicate customer-month snapshot key.")
    if not (snapshots["feature_window_end_exclusive"] == snapshots["decision_time"]).all():
        raise AssertionError("Feature window is not exclusive at the decision timestamp.")
    if not (snapshots["first_observed_qualifying_purchase_timestamp"] < snapshots["decision_time"]).all():
        raise AssertionError("A historical feature includes a purchase at/after decision time.")
    if not snapshots["historical_feature_coverage_complete"].all() or not snapshots["active_in_trailing_365d"].all():
        raise AssertionError("Output contains an ineligible or incompletely covered snapshot.")

    eligible = len(snapshots)
    mature_positive = int((snapshots.outcome_status == "positive_mature").sum())
    mature_negative = int((snapshots.outcome_status == "negative_mature").sum())
    partial_positive = int((snapshots.outcome_status == "positive_incomplete_followup").sum())
    unknown = int((snapshots.outcome_status == "unknown_incomplete_followup").sum())
    if eligible != mature_positive + mature_negative + partial_positive + unknown:
        raise AssertionError("Outcome label accounting does not reconcile.")
    if snapshots.loc[snapshots.outcome_status == "negative_mature", "outcome_label"].isna().any():
        raise AssertionError("Mature negative must have label 0.")
    if snapshots.loc[snapshots.outcome_status == "unknown_incomplete_followup", "outcome_label"].notna().any():
        raise AssertionError("Unknown immature outcomes must remain null.")
    if not snapshots.loc[snapshots.outcome_status == "negative_mature", "outcome_label"].eq(0).all():
        raise AssertionError("Mature negative label is not zero.")
    if not snapshots.loc[snapshots.outcome_status.str.startswith("positive"), "outcome_label"].eq(1).all():
        raise AssertionError("Observed positive label is not one.")

    cutoff = pd.Timestamp(metadata["train_cutoff"])
    train = snapshots[snapshots.evaluation_partition == "train"]
    test = snapshots[snapshots.evaluation_partition == "test"]
    unavailable = snapshots[snapshots.evaluation_partition == "pre_cutoff_label_not_available"]
    immature = snapshots[snapshots.evaluation_partition == "not_evaluated_immature"]
    if not train.empty:
        if not (train.decision_time < cutoff).all() or not (train.outcome_window_end_exclusive <= cutoff).all():
            raise AssertionError("Training contains a future decision or unavailable label.")
        if not train.training_label_available_at_cutoff.all() or train.outcome_label.isna().any():
            raise AssertionError("Training labels are not available at the cutoff.")
        if not train.outcome_window_mature.all():
            raise AssertionError("Training must contain mature labels.")
    if not test.empty:
        if not (test.decision_time >= cutoff).all() or test.outcome_label.isna().any():
            raise AssertionError("Test partition is not chronological or has unknown labels.")
        if not test.outcome_window_mature.all():
            raise AssertionError("Test partition must have mature labels.")
    if not unavailable.empty and (unavailable.decision_time >= cutoff).any():
        raise AssertionError("Post-cutoff row cannot be a pre-cutoff unavailable label.")
    if not immature.empty:
        if immature.outcome_window_mature.any():
            raise AssertionError("Immature partition contains a mature outcome window.")
        unknown_rows = immature.outcome_status == "unknown_incomplete_followup"
        if immature.loc[unknown_rows, "outcome_label"].notna().any():
            raise AssertionError("Unknown immature outcomes must remain unlabeled.")
        partial_positive_rows = immature.outcome_status == "positive_incomplete_followup"
        if not immature.loc[partial_positive_rows, "outcome_label"].eq(1).all():
            raise AssertionError("Observed positives in incomplete windows must retain label 1.")

    train_positive = int(train.outcome_label.eq(1).sum())
    train_negative = int(train.outcome_label.eq(0).sum())
    test_positive = int(test.outcome_label.eq(1).sum())
    test_negative = int(test.outcome_label.eq(0).sum())
    train_customers = set(train.customer_id.astype(str))
    test_customers = set(test.customer_id.astype(str))
    monthly = []
    for month, group in snapshots.groupby("snapshot_month", sort=True):
        monthly.append({
            "snapshot_month": month,
            "eligible_snapshots": len(group),
            "unique_customers": int(group.customer_id.nunique()),
            "mature_positive": int((group.outcome_status == "positive_mature").sum()),
            "mature_negative": int((group.outcome_status == "negative_mature").sum()),
            "positive_incomplete_followup": int((group.outcome_status == "positive_incomplete_followup").sum()),
            "unknown_immature": int((group.outcome_status == "unknown_incomplete_followup").sum()),
            "training_snapshots": int((group.evaluation_partition == "train").sum()),
            "test_snapshots": int((group.evaluation_partition == "test").sum()),
        })
    mature_total = mature_positive + mature_negative
    if mature_total != len(train) + len(test) + int(unavailable.outcome_window_mature.sum()):
        raise AssertionError("Mature labels do not reconcile across train, test and unavailable rows.")
    return {
        "eligible_snapshots": eligible,
        "unique_customers": int(snapshots.customer_id.nunique()),
        "mature_positive": mature_positive,
        "mature_negative": mature_negative,
        "mature_total": mature_total,
        "positive_prevalence_mature": mature_positive / mature_total if mature_total else None,
        "positive_incomplete_followup": partial_positive,
        "unknown_immature": unknown,
        "training_snapshots": len(train),
        "training_unique_customers": len(train_customers),
        "training_positive": train_positive,
        "training_negative": train_negative,
        "training_positive_prevalence": train_positive / len(train) if len(train) else None,
        "test_snapshots": len(test),
        "test_unique_customers": len(test_customers),
        "test_positive": test_positive,
        "test_negative": test_negative,
        "test_positive_prevalence": test_positive / len(test) if len(test) else None,
        "training_test_unique_customer_overlap": len(train_customers & test_customers),
        "pre_cutoff_label_not_available": len(unavailable),
        "pre_cutoff_label_not_available_mature_later": int(unavailable.outcome_window_mature.sum()),
        "immature_not_evaluated": len(immature),
        "monthly_distribution": monthly,
        "anchor_accounting": metadata["anchor_summary"],
        "canonical_occasion_summary": metadata["occasion_summary"],
    }


def build_from_source_paths(
    v1_xlsx_path: Path,
    v2_csv_path: Path,
    *,
    train_cutoff: datetime | pd.Timestamp = APPROVED_TRAIN_CUTOFF,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load verified sources through the canonical production API."""
    source_audit.V1_PATH = Path(v1_xlsx_path)
    source_audit.V2_PATH = Path(v2_csv_path)
    validated = load_validated_purchase_input()
    occasions, summary = build_purchase_occasions(validated)
    frame = validated._frame
    timestamps = pd.to_datetime(frame["InvoiceDate"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Source timestamp is missing or invalid.")
    source_start, source_end = timestamps.min(), timestamps.max()
    snapshots, metadata = build_monthly_customer_snapshots(
        frame,
        occasions,
        observation_start_timestamp=source_start,
        observation_end_timestamp=source_end,
        train_cutoff=train_cutoff,
    )
    metadata["canonical_source_summary"] = summary
    return snapshots, {
        "snapshot_version": SNAPSHOT_VERSION,
        "source_v1_sha256": validated._integrity_report["source_sha256"]["v1"],
        "source_v2_sha256": validated._integrity_report["source_sha256"]["v2"],
        "taxonomy_seed_sha256": validated._integrity_report["seed_sha256"],
        "canonical_source_summary": summary,
        "source_start_timestamp": source_start.isoformat(sep=" "),
        "source_end_timestamp": source_end.isoformat(sep=" "),
        "active_lookback_days": ACTIVE_LOOKBACK_DAYS,
        "acquisition_proxy_applied": False,
        "active_population_rule": "at least one canonical qualifying occasion in the complete [T-365 days, T) window",
        "decision_rule": "month-start 00:00 local source-naive timestamp; features use timestamps strictly before decision_time",
        "outcome_horizon_days": OUTCOME_HORIZON_DAYS,
        "outcome_window": "[decision_time, decision_time + 30 days)",
        "maturity_rule": "full 30-day outcome window must be covered by source observation intervals",
        "feature_columns": list(FEATURE_COLUMNS),
        "timestamp_rule": "earliest valid qualifying line timestamp within customer x invoice occasion",
        "purchase_occasion_rule": "canonical customer x invoice; qualifying merchandise only",
        "same_day_repeat_rule": "distinct qualifying invoice occasions remain separate frequencies; distinct purchase dates are also reported",
        "train_cutoff": metadata["train_cutoff"],
        "anchor_summary": metadata["anchor_summary"],
        "occasion_summary": metadata["occasion_summary"],
        "builder_sha256": _sha256(Path(__file__)),
    }


def _write_outputs(snapshots: pd.DataFrame, manifest: dict[str, Any], output_path: Path) -> None:
    output_path = output_path.expanduser().resolve()
    try:
        output_path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Customer-level snapshot output must be outside the Git repository.")
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite an existing snapshot dataset or manifest.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = snapshot_accounting(snapshots, {
        "train_cutoff": manifest["train_cutoff"],
        "anchor_summary": manifest["anchor_summary"],
        "occasion_summary": manifest["occasion_summary"],
    })
    snapshots.to_parquet(output_path, index=False)
    saved_manifest = {
        **manifest,
        "row_count": len(snapshots),
        "snapshot_accounting": report,
        "output_sha256": _sha256(output_path),
    }
    manifest_path.write_text(json.dumps(saved_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-xlsx", type=Path, required=True, help="Verified V1 workbook used by corrected-V2 validation")
    parser.add_argument("--v2-csv", type=Path, required=True, help="Verified pinned V2 CSV")
    parser.add_argument("--output", type=Path, required=True, help="New local Parquet output outside the repository")
    parser.add_argument("--train-cutoff", default=APPROVED_TRAIN_CUTOFF.isoformat(sep=" "))
    args = parser.parse_args()
    snapshots, manifest = build_from_source_paths(args.v1_xlsx, args.v2_csv, train_cutoff=pd.Timestamp(args.train_cutoff))
    _write_outputs(snapshots, manifest, args.output)
    accounting = snapshot_accounting(snapshots, {
        "train_cutoff": manifest["train_cutoff"],
        "anchor_summary": manifest["anchor_summary"],
        "occasion_summary": manifest["occasion_summary"],
    })
    print(json.dumps({"output": str(args.output.expanduser().resolve()), "snapshot_accounting": accounting}, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build a local, point-in-time Day-21 second-purchase cohort.

The source/taxonomy frame and qualifying occasions must come from the frozen
corrected-V2 production API. Outputs are customer-level and must be written
outside the repository.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_DIR = REPO_ROOT / "docs" / "recovery"
sys.path.insert(0, str(RECOVERY_DIR))

import COMMERCIAL_DS_002_ANALYSIS as source_audit  # noqa: E402
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (  # noqa: E402
    DATA_END_TIMESTAMP,
    OBSERVATION_START,
    build_purchase_occasions,
    load_validated_purchase_input,
)


DAY21_DAYS = 21
OUTCOME_DAYS = 90
ACQUISITION_LOOKBACK_MONTHS = 12
SOURCE_START_TIMESTAMP = pd.Timestamp("2009-12-01 07:45:00")
APPROVED_EVALUATION_CUTOFF = pd.Timestamp("2011-07-01 00:00:00")
COHORT_VERSION = "day21-v2"
FEATURE_COLUMNS = (
    "first_day_qualifying_gross",
    "first_day_item_quantity",
    "first_day_product_diversity",
    "first_day_occasion_count",
    "first_purchase_weekday",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_naive_timestamp(value: Any, *, field: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Invalid {field} in qualifying source rows.") from None
    if pd.isna(stamp):
        raise ValueError(f"Missing {field} in qualifying source rows.")
    if stamp.tzinfo is not None:
        raise ValueError(f"Timezone-aware {field} is unsupported by the source contract.")
    return stamp


def build_day21_cohort(
    classified_transactions: pd.DataFrame,
    canonical_occasions: list[dict[str, Any]],
    *,
    observation_start: date = OBSERVATION_START,
    observation_end: datetime = DATA_END_TIMESTAMP,
    source_start_timestamp: datetime = SOURCE_START_TIMESTAMP.to_pydatetime(),
) -> pd.DataFrame:
    """Build one row per identified canonical customer with labels and features.

    ``canonical_occasions`` must be produced by the corrected-V2 purchase
    occasion API. Occasion timestamps are the earliest qualifying line time
    within each customer × invoice occasion. Repeat events remain strictly
    later-calendar-day events, matching the Phase 1 primary definition.
    """
    required = {
        "source_row_number", "CustomerID", "InvoiceNo", "StockCode",
        "Quantity", "UnitPrice", "InvoiceDate", "category",
    }
    missing = required - set(classified_transactions.columns)
    if missing:
        raise ValueError(f"Classified source frame missing columns: {sorted(missing)}")
    if not canonical_occasions:
        if classified_transactions.empty:
            return pd.DataFrame()
        raise ValueError("Canonical occasion input is empty.")

    frame = classified_transactions.copy()
    frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"], errors="coerce")
    if frame["InvoiceDate"].isna().any():
        raise ValueError("Source contains missing or invalid transaction timestamps.")
    if getattr(frame["InvoiceDate"].dt, "tz", None) is not None:
        raise ValueError("Timezone-aware source timestamps are unsupported.")

    # Occasion lineage is the authoritative qualification mask. It avoids
    # reimplementing line eligibility here and makes mismatch checks explicit.
    occasion_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    expected_source_ids: set[int] = set()
    for occasion in canonical_occasions:
        key = (str(occasion["customer_id"]), str(occasion["invoice_id"]))
        if key in occasion_by_key:
            raise ValueError("Duplicate customer × invoice canonical occasion.")
        ids = [int(value) for value in occasion["source_row_numbers"]]
        if len(ids) != len(set(ids)) or expected_source_ids.intersection(ids):
            raise ValueError("Canonical occasion source-row lineage is duplicated.")
        expected_source_ids.update(ids)
        occasion_by_key[key] = occasion

    eligible_lines = frame[frame["source_row_number"].isin(expected_source_ids)].copy()
    if len(eligible_lines) != len(expected_source_ids):
        raise ValueError("Canonical occasion lineage does not match source rows.")
    if eligible_lines["InvoiceDate"].isna().any():
        raise ValueError("Qualifying source line has an invalid timestamp.")
    eligible_lines["_customer_key"] = eligible_lines["CustomerID"].map(
        lambda value: str(int(value)) if pd.notna(value) else None
    )
    eligible_lines["_invoice_key"] = eligible_lines["InvoiceNo"].astype(str)
    eligible_lines["_source_date"] = eligible_lines["InvoiceDate"].dt.date

    grouped = eligible_lines.groupby(["_customer_key", "_invoice_key"], sort=False)
    invoice_events: list[dict[str, Any]] = []
    for (customer_key, invoice_key), rows in grouped:
        key = (str(customer_key), str(invoice_key))
        canonical = occasion_by_key.get(key)
        if canonical is None:
            raise ValueError("Source occasion key is absent from canonical occasion records.")
        dates = set(rows["_source_date"])
        if len(dates) != 1:
            raise ValueError("Qualifying invoice has contradictory calendar dates.")
        day = next(iter(dates))
        if day < observation_start:
            raise ValueError("Qualifying occasion predates the configured source observation start.")
        if day.isoformat() != canonical["transaction_date"]:
            raise ValueError("Source invoice date disagrees with canonical occasion date.")
        if len(rows) != int(canonical["eligible_line_count"]):
            raise ValueError("Qualifying invoice line count disagrees with canonical occasion.")
        observed_ids = set(rows["source_row_number"].astype(int))
        if observed_ids != set(map(int, canonical["source_row_numbers"])):
            raise ValueError("Qualifying invoice lineage disagrees with canonical occasion.")
        timestamps = rows["InvoiceDate"].map(lambda x: _as_naive_timestamp(x, field="InvoiceDate"))
        invoice_events.append({
            "customer_id": str(customer_key),
            "invoice_id": str(invoice_key),
            "purchase_date": day,
            "occasion_timestamp": min(timestamps),
            "canonical_gross": Decimal(str(canonical["qualifying_gross_merchandise"])),
        })
    if len(invoice_events) != len(occasion_by_key):
        raise ValueError("Canonical occasion records and source invoice groups do not reconcile.")

    events_by_customer: dict[str, list[dict[str, Any]]] = {}
    for event in invoice_events:
        events_by_customer.setdefault(event["customer_id"], []).append(event)

    # Small first-day feature aggregate. Only qualifying source lines on the
    # customer's first qualifying calendar date contribute to these features.
    first_dates = {
        customer: min(event["purchase_date"] for event in events)
        for customer, events in events_by_customer.items()
    }
    first_date_for_line = eligible_lines["_customer_key"].map(first_dates)
    first_day_rows = eligible_lines[eligible_lines["_source_date"].eq(first_date_for_line)]
    feature_rows: dict[str, dict[str, Any]] = {}
    for customer, rows in first_day_rows.groupby("_customer_key", sort=False):
        customer = str(customer)
        first_day_events = [e for e in events_by_customer[customer] if e["purchase_date"] == first_dates[customer]]
        first_ts = min(e["occasion_timestamp"] for e in first_day_events)
        gross = sum(
            (Decimal(str(qty)) * Decimal(str(price)) for qty, price in zip(rows["Quantity"], rows["UnitPrice"])),
            Decimal(0),
        )
        feature_rows[customer] = {
            "first_day_qualifying_gross": float(gross),
            "first_day_item_quantity": int(rows["Quantity"].sum()),
            "first_day_product_diversity": int(rows["StockCode"].astype(str).nunique()),
            "first_day_occasion_count": len(first_day_events),
            "first_purchase_weekday": int(first_ts.dayofweek),
        }

    boundary = pd.Timestamp(observation_end)
    if boundary.tzinfo is not None:
        raise ValueError("Observation end must be a timezone-naive source timestamp.")
    rows_out: list[dict[str, Any]] = []
    for customer in sorted(events_by_customer, key=int):
        events = sorted(events_by_customer[customer], key=lambda e: (e["purchase_date"], e["occasion_timestamp"]))
        first_date = events[0]["purchase_date"]
        first_day = [event for event in events if event["purchase_date"] == first_date]
        t0 = min(event["occasion_timestamp"] for event in first_day)
        decision = t0 + pd.Timedelta(days=DAY21_DAYS)
        deadline = decision + pd.Timedelta(days=OUTCOME_DAYS)
        later_day_events = [event for event in events if event["purchase_date"] > first_date]
        second_date = min((event["purchase_date"] for event in later_day_events), default=None)
        second_day_events = [event for event in later_day_events if event["purchase_date"] == second_date]
        second_ts = min((event["occasion_timestamp"] for event in second_day_events), default=pd.NaT)

        decision_observed = decision <= boundary
        repeated_by_decision = bool(decision_observed and pd.notna(second_ts) and second_ts <= decision)
        eligible = bool(decision_observed and not repeated_by_decision)
        complete = bool(eligible and deadline <= boundary)
        observed_positive = bool(
            eligible and pd.notna(second_ts) and decision < second_ts <= deadline and second_ts <= boundary
        )
        if not eligible:
            label = pd.NA
            if not decision_observed:
                exclusion_reason = "day21_decision_after_observation_end"
                outcome_status = "not_eligible_decision_unobserved"
            else:
                exclusion_reason = "second_purchase_by_day21"
                outcome_status = "not_eligible_already_repeated"
        elif observed_positive:
            label = 1
            exclusion_reason = None
            outcome_status = "positive_mature" if complete else "positive_incomplete_followup"
        elif complete:
            label = 0
            exclusion_reason = None
            outcome_status = "negative_mature"
        else:
            label = pd.NA
            exclusion_reason = None
            outcome_status = "unknown_incomplete_followup"

        rows_out.append({
            "customer_id": customer,
            "first_qualifying_purchase_timestamp": t0,
            "day21_decision_timestamp": decision,
            "day111_outcome_deadline": deadline,
            "decision_observed": decision_observed,
            "eligible": eligible,
            "exclusion_reason": exclusion_reason,
            "second_qualifying_purchase_timestamp": second_ts,
            "outcome_label": label,
            "complete_horizon_observed": complete,
            "observed_positive": observed_positive,
            "outcome_status": outcome_status,
            "observation_coverage_status": (
                "decision_unobserved" if not decision_observed else
                "complete_through_deadline" if complete else "right_censored_at_source_end"
            ),
            "followup_observed_days": max(0.0, min((boundary - decision).total_seconds() / 86400.0, OUTCOME_DAYS))
            if decision_observed else 0.0,
            **feature_rows[customer],
        })

    result = pd.DataFrame(rows_out)
    if not result.empty:
        result["outcome_label"] = result["outcome_label"].astype("Int64")
        result["first_qualifying_purchase_timestamp"] = pd.to_datetime(result["first_qualifying_purchase_timestamp"])
        result["day21_decision_timestamp"] = pd.to_datetime(result["day21_decision_timestamp"])
        result["day111_outcome_deadline"] = pd.to_datetime(result["day111_outcome_deadline"])
        result["second_qualifying_purchase_timestamp"] = pd.to_datetime(result["second_qualifying_purchase_timestamp"])
        source_start = _as_naive_timestamp(source_start_timestamp, field="source start timestamp")
        acquisition_boundary = source_start + pd.DateOffset(months=ACQUISITION_LOOKBACK_MONTHS)
        result["acquisition_lookback_boundary"] = acquisition_boundary
        result["acquisition_lookback_months"] = ACQUISITION_LOOKBACK_MONTHS
        result["acquisition_eligible"] = result["first_qualifying_purchase_timestamp"] >= acquisition_boundary
        result["acquisition_exclusion_reason"] = pd.Series(pd.NA, index=result.index, dtype="string")
        result.loc[~result["acquisition_eligible"], "acquisition_exclusion_reason"] = (
            "insufficient_12_month_qualifying_history"
        )
        result["primary_eligible"] = result["acquisition_eligible"] & result["eligible"]
        result["primary_exclusion_reason"] = result["acquisition_exclusion_reason"]
        needs_day21_reason = result["primary_exclusion_reason"].isna() & ~result["eligible"]
        result.loc[needs_day21_reason, "primary_exclusion_reason"] = result.loc[
            needs_day21_reason, "exclusion_reason"
        ]
    return result


def cohort_accounting(cohort: pd.DataFrame) -> dict[str, int | float]:
    """Return disjoint customer/label accounting and assert reconciliation."""
    if cohort.empty:
        return {"identifiable_customers": 0, "valid_first_timestamps": 0, "invalid_first_timestamps": 0,
                "day21_not_observed": 0, "repeated_by_day21": 0, "eligible": 0,
                "eligible_complete_followup": 0, "mature_positive": 0, "mature_negative": 0,
                "positive_incomplete_followup": 0, "unknown_immature": 0, "mature_prevalence": float("nan"),
                "sufficient_12m_history": 0, "insufficient_12m_history": 0, "primary_eligible": 0}
    valid = int(cohort["first_qualifying_purchase_timestamp"].notna().sum())
    invalid = len(cohort) - valid
    decision_not_observed = int((~cohort["decision_observed"]).sum())
    repeated = int((cohort["decision_observed"] & ~cohort["eligible"]).sum())
    eligible = int(cohort["eligible"].sum())
    mature_positive = int((cohort["eligible"] & cohort["complete_horizon_observed"] & cohort["outcome_label"].eq(1)).sum())
    mature_negative = int((cohort["eligible"] & cohort["complete_horizon_observed"] & cohort["outcome_label"].eq(0)).sum())
    positive_immature = int((cohort["eligible"] & ~cohort["complete_horizon_observed"] & cohort["observed_positive"]).sum())
    unknown_immature = int((cohort["eligible"] & ~cohort["complete_horizon_observed"] & ~cohort["observed_positive"]).sum())
    complete = int((cohort["eligible"] & cohort["complete_horizon_observed"]).sum())
    if len(cohort) != invalid + decision_not_observed + repeated + eligible:
        raise AssertionError("Customer cohort accounting does not reconcile.")
    if eligible != mature_positive + mature_negative + positive_immature + unknown_immature:
        raise AssertionError("Eligible outcome accounting does not reconcile.")
    if complete != mature_positive + mature_negative:
        raise AssertionError("Complete-follow-up accounting does not reconcile.")
    prevalence = mature_positive / complete if complete else float("nan")
    sufficient_history = int(cohort["acquisition_eligible"].sum())
    insufficient_history = int((~cohort["acquisition_eligible"]).sum())
    primary_eligible = int(cohort["primary_eligible"].sum())
    if len(cohort) != sufficient_history + insufficient_history:
        raise AssertionError("Acquisition look-back accounting does not reconcile.")
    return {
        "identifiable_customers": int(len(cohort)),
        "valid_first_timestamps": valid,
        "invalid_first_timestamps": invalid,
        "day21_not_observed": decision_not_observed,
        "repeated_by_day21": repeated,
        "eligible": eligible,
        "eligible_complete_followup": complete,
        "mature_positive": mature_positive,
        "mature_negative": mature_negative,
        "positive_incomplete_followup": positive_immature,
        "unknown_immature": unknown_immature,
        "mature_prevalence": prevalence,
        "sufficient_12m_history": sufficient_history,
        "insufficient_12m_history": insufficient_history,
        "primary_eligible": primary_eligible,
    }


def apply_approved_temporal_split(
    cohort: pd.DataFrame,
    *,
    cutoff: pd.Timestamp = APPROVED_EVALUATION_CUTOFF,
) -> pd.DataFrame:
    """Assign only as-of mature training labels and fully mature later tests."""
    cutoff = _as_naive_timestamp(cutoff, field="evaluation cutoff")
    result = cohort.copy()
    result["evaluation_partition"] = "not_in_primary_population"
    primary = result["primary_eligible"]
    pre_cutoff = primary & (result["day21_decision_timestamp"] < cutoff)
    post_cutoff = primary & (result["day21_decision_timestamp"] >= cutoff)
    train_available = (
        pre_cutoff
        & result["complete_horizon_observed"]
        & (result["day111_outcome_deadline"] <= cutoff)
    )
    result["training_label_available_at_cutoff"] = train_available
    result.loc[pre_cutoff, "evaluation_partition"] = "pre_cutoff_label_not_available"
    result.loc[train_available, "evaluation_partition"] = "train"
    test_mature = post_cutoff & result["complete_horizon_observed"]
    result.loc[post_cutoff, "evaluation_partition"] = "test_immature"
    result.loc[test_mature, "evaluation_partition"] = "test"

    selected = result["evaluation_partition"].isin(["train", "test"])
    if result.loc[selected, "outcome_label"].isna().any() or not result.loc[selected, "complete_horizon_observed"].all():
        raise AssertionError("Evaluation partitions require mature, non-null labels.")
    if not (result.loc[result["evaluation_partition"] == "train", "day111_outcome_deadline"] <= cutoff).all():
        raise AssertionError("A training label was not available by the as-of cutoff.")
    if not result.loc[result["evaluation_partition"] == "train", "training_label_available_at_cutoff"].all():
        raise AssertionError("Training availability flag disagrees with split assignment.")
    if not (result.loc[result["evaluation_partition"] == "test", "day21_decision_timestamp"] >= cutoff).all():
        raise AssertionError("Test decisions are not temporally separated from training.")
    return result


def approved_split_accounting(cohort: pd.DataFrame) -> dict[str, Any]:
    """Return disjoint split dispositions and mature-label reconciliation."""
    counts: dict[str, Any] = {}
    for partition in (
        "train", "pre_cutoff_label_not_available", "test", "test_immature",
        "not_in_primary_population",
    ):
        rows = cohort[cohort["evaluation_partition"] == partition]
        counts[partition] = int(len(rows))
        counts[f"{partition}_positive"] = int(rows["outcome_label"].eq(1).sum())
        counts[f"{partition}_negative"] = int(rows["outcome_label"].eq(0).sum())
    mature = cohort[cohort["primary_eligible"] & cohort["complete_horizon_observed"]]
    counts["primary_mature_total"] = int(len(mature))
    counts["primary_mature_positive"] = int(mature["outcome_label"].eq(1).sum())
    counts["primary_mature_negative"] = int(mature["outcome_label"].eq(0).sum())
    if len(mature) != counts["train"] + counts["pre_cutoff_label_not_available"] + counts["test"]:
        raise AssertionError("Mature primary labels do not reconcile across split dispositions.")
    return counts


def temporal_split_summary(cohort: pd.DataFrame, candidates: list[dict[str, str]]) -> pd.DataFrame:
    """Summarize fixed chronological candidates and as-of label availability."""
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        train_end = pd.Timestamp(candidate["train_end"])
        validation_end = pd.Timestamp(candidate["validation_end"])
        test_end = pd.Timestamp(candidate["test_end"])
        if not train_end < validation_end < test_end:
            raise ValueError("Temporal split boundaries must be strictly increasing.")
        train = cohort[cohort["eligible"] & (cohort["day21_decision_timestamp"] < train_end)]
        validation = cohort[
            cohort["eligible"] & (cohort["day21_decision_timestamp"] >= train_end)
            & (cohort["day21_decision_timestamp"] < validation_end)
        ]
        test = cohort[
            cohort["eligible"] & (cohort["day21_decision_timestamp"] >= validation_end)
            & (cohort["day21_decision_timestamp"] < test_end)
        ]
        train_asof = train[train["day111_outcome_deadline"] <= train_end]
        validation_asof = validation[validation["day111_outcome_deadline"] <= validation_end]

        def counts(part: pd.DataFrame, prefix: str) -> dict[str, Any]:
            mature = part[part["complete_horizon_observed"]]
            pos = int(mature["outcome_label"].eq(1).sum())
            neg = int(mature["outcome_label"].eq(0).sum())
            return {
                f"{prefix}_eligible": int(len(part)),
                f"{prefix}_mature_positive": pos,
                f"{prefix}_mature_negative": neg,
                f"{prefix}_mature_prevalence": pos / (pos + neg) if pos + neg else float("nan"),
            }

        row: dict[str, Any] = {
            "candidate": candidate["name"],
            "train_decisions_before": train_end.isoformat(),
            "validation_decisions_before": validation_end.isoformat(),
            "test_decisions_before": test_end.isoformat(),
            "train_labels_available_by_validation_start": len(train_asof),
            "train_positives_available_by_validation_start": int(train_asof["outcome_label"].eq(1).sum()),
            "train_negatives_available_by_validation_start": int(train_asof["outcome_label"].eq(0).sum()),
            "validation_labels_available_by_test_start": len(validation_asof),
            "validation_positives_available_by_test_start": int(validation_asof["outcome_label"].eq(1).sum()),
            "validation_negatives_available_by_test_start": int(validation_asof["outcome_label"].eq(0).sum()),
        }
        row.update(counts(train, "train"))
        row.update(counts(validation, "validation"))
        row.update(counts(test, "test"))
        rows.append(row)
    return pd.DataFrame(rows)


def build_from_source_paths(v1_path: Path, v2_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load through the canonical API while routing paths to local external data."""
    source_audit.V1_PATH = Path(v1_path)
    source_audit.V2_PATH = Path(v2_path)
    validated = load_validated_purchase_input()
    occasions, summary = build_purchase_occasions(validated)
    cohort = build_day21_cohort(validated._frame, occasions)
    cohort = apply_approved_temporal_split(cohort)
    manifest = {
        "cohort_version": COHORT_VERSION,
        "source_v1_sha256": validated._integrity_report["source_sha256"]["v1"],
        "source_v2_sha256": validated._integrity_report["source_sha256"]["v2"],
        "taxonomy_seed_sha256": validated._integrity_report["seed_sha256"],
        "occasion_summary": summary,
        "observation_start": OBSERVATION_START.isoformat(),
        "source_start_timestamp": SOURCE_START_TIMESTAMP.isoformat(sep=" "),
        "acquisition_lookback_months": ACQUISITION_LOOKBACK_MONTHS,
        "acquisition_lookback_boundary": (
            SOURCE_START_TIMESTAMP + pd.DateOffset(months=ACQUISITION_LOOKBACK_MONTHS)
        ).isoformat(sep=" "),
        "observation_end": DATA_END_TIMESTAMP.isoformat(sep=" "),
        "occasion_timestamp_rule": "earliest qualifying line timestamp within customer x invoice",
        "repeat_rule": "first qualifying occasion on a strictly later calendar date",
        "prediction_anchor_days": DAY21_DAYS,
        "outcome_horizon_days": OUTCOME_DAYS,
        "evaluation_cutoff": APPROVED_EVALUATION_CUTOFF.isoformat(sep=" "),
        "evaluation_split_rule": (
            "train: decision before cutoff and complete label deadline at/before cutoff; "
            "test: decision at/after cutoff and complete outcome horizon observable by source end"
        ),
        "feature_columns": list(FEATURE_COLUMNS),
        "builder_sha256": _sha256(Path(__file__)),
    }
    return cohort, manifest


def _write_outputs(cohort: pd.DataFrame, manifest: dict[str, Any], output_path: Path) -> None:
    output_path = output_path.expanduser().resolve()
    try:
        output_path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Customer-level outputs must be written outside the Git repository.")
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    split_manifest_path = output_path.with_suffix(output_path.suffix + ".split.manifest.json")
    if output_path.exists() or manifest_path.exists() or split_manifest_path.exists():
        raise FileExistsError("Refusing to overwrite an existing cohort or manifest output.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cohort.to_parquet(output_path, index=False)
    manifest = {**manifest, "cohort_accounting": cohort_accounting(cohort), "row_count": int(len(cohort))}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    split_manifest = {
        "cohort_path": str(output_path),
        "cohort_sha256": _sha256(output_path),
        "evaluation_cutoff": APPROVED_EVALUATION_CUTOFF.isoformat(sep=" "),
        "split_rule": "strict as-of mature training labels; post-cutoff mature test decisions",
        "split_accounting": approved_split_accounting(cohort),
        "builder_sha256": _sha256(Path(__file__)),
    }
    split_manifest_path.write_text(json.dumps(split_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-xlsx", type=Path, required=True, help="Verified UCI Online Retail XLSX used for overlap validation")
    parser.add_argument("--v2-csv", type=Path, required=True, help="Verified pinned Online Retail II CSV")
    parser.add_argument("--output", type=Path, required=True, help="New local Parquet output path outside the repository")
    args = parser.parse_args()
    cohort, manifest = build_from_source_paths(args.v1_xlsx, args.v2_csv)
    _write_outputs(cohort, manifest, args.output)
    print(json.dumps({
        "output": str(args.output.expanduser().resolve()),
        "cohort_accounting": cohort_accounting(cohort),
        "split_accounting": approved_split_accounting(cohort),
    }, sort_keys=True))


if __name__ == "__main__":
    main()

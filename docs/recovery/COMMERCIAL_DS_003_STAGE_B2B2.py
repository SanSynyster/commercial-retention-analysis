"""Stratified, descriptive first-observed repeat analysis for corrected V2.

This producer consumes only Stage B2A's validated input and frozen occasion
builder. It emits no customer-level rows and selects no acquisition proxy.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import re

import pandas as pd

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))

from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (
    ACQUISITION_CUTOFF,
    DATA_END_DATE,
    OBSERVATION_START,
    PRIMARY_REPEAT_DAYS,
    build_purchase_occasions,
    invoice_level_repeat,
    load_validated_purchase_input,
)

CONTRACT_VERSION = "commercial-ds-b2b2-observed-repeat-v1"
OUTPUT_JSON = "COMMERCIAL_DS_003_STAGE_B2B2_v1.json"
OUTPUT_SUMMARY = "COMMERCIAL_DS_003_STAGE_B2B2_v1_SUMMARY.md"
POPULATION_ORDER = ("all_observed", "left_censored", "proxy_1", "proxy_2", "proxy_3")
OUTCOME_LEVELS = ("date_level_primary", "invoice_level_sensitivity")
ELIGIBILITY = "Unique identified customer with at least one qualifying corrected-V2 merchandise occasion in the population and first-observed period."
DATE_WINDOW = "d1 < d2 < d1 + 90 calendar days"
INVOICE_WINDOW = "d1 <= later invoice date < d1 + 90 calendar days; distinct invoices ordered by (date, invoice_id)"
POPULATION_LABELS = {
    "all_observed":"All customers with a first-observed qualifying purchase; reconciliation count only.",
    "left_censored":"First observed qualifying purchase before 2010-12-01; prior history before 2009-12-01 is unavailable.",
    "proxy_1":"Diagnostic sensitivity population 1: first qualifying merchandise occasion on or after 2010-12-01.",
    "proxy_2":"Diagnostic sensitivity population 2: proxy 1 excluding any identified activity before 2010-12-01.",
    "proxy_3":"Diagnostic sensitivity population 3: proxy 1 excluding any identified activity dated before the first qualifying occasion date.",
}


def _period_key(day: date, grain: str) -> str:
    if grain == "month":
        return f"{day.year:04d}-{day.month:02d}"
    if grain == "quarter":
        return f"{day.year:04d}-Q{(day.month - 1) // 3 + 1}"
    raise ValueError(f"unsupported period grain: {grain}")


def _periods(grain: str) -> list[str]:
    if grain == "month":
        values=[]
        year, month = OBSERVATION_START.year, OBSERVATION_START.month
        while (year, month) <= (DATA_END_DATE.year, DATA_END_DATE.month):
            values.append(f"{year:04d}-{month:02d}")
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return values
    if grain == "quarter":
        return ["2009-Q4", "2010-Q1", "2010-Q2", "2010-Q3", "2010-Q4",
                "2011-Q1", "2011-Q2", "2011-Q3", "2011-Q4"]
    raise ValueError(f"unsupported period grain: {grain}")


def _period_coverage(grain: str, period: str) -> str:
    if grain == "quarter" and period == "2009-Q4":
        return "data_start_truncated"
    if grain == "quarter" and period == "2010-Q4":
        return "cutoff_split"
    if (grain == "month" and period == "2011-09") or (grain == "quarter" and period == "2011-Q3"):
        return "maturity_truncated"
    if (grain == "month" and period >= "2011-10") or (grain == "quarter" and period == "2011-Q4"):
        return "none_mature"
    return "full"


def _repeat_window_complete(coverage: str) -> str:
    if coverage == "none_mature":
        return "none"
    if coverage == "maturity_truncated":
        return "partial"
    return "complete"


def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054):
    if total <= 0:
        return None, None
    p = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    half = z * ((p * (1 - p) / total + z2 / (4 * total * total)) ** 0.5) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def calculate_customer_outcome(occasions, *, data_end_date=DATA_END_DATE):
    """Build one customer's mature/unknown date and invoice outcomes."""
    if not occasions:
        raise ValueError("customer must have at least one qualifying occasion")
    rows=[]
    customer_ids={str(row["customer_id"]) for row in occasions}
    if len(customer_ids) != 1:
        raise ValueError("calculate_customer_outcome requires one customer")
    invoice_ids=set()
    for row in occasions:
        invoice_id=row["invoice_id"]
        if not isinstance(invoice_id, str) or not re.fullmatch(r"[0-9]{6}", invoice_id):
            raise AssertionError(f"eligible invoice ID violates reviewed fixed-width ordering: {invoice_id!r}")
        if invoice_id in invoice_ids:
            raise AssertionError(f"duplicate customer-invoice occasion: {invoice_id}")
        invoice_ids.add(invoice_id)
        day=date.fromisoformat(row["transaction_date"])
        rows.append((day, invoice_id, tuple(row["source_row_numbers"])))
    rows.sort(key=lambda item:(item[0], item[1], item[2]))
    days=sorted({row[0] for row in rows})
    d1=days[0]
    mature=d1 + timedelta(days=PRIMARY_REPEAT_DAYS) <= data_end_date
    date_repeat = None
    invoice_repeat = None
    first_invoice_day, first_invoice_id, _ = rows[0]
    if mature:
        date_repeat=any(d1 < day < d1 + timedelta(days=PRIMARY_REPEAT_DAYS) for day in days[1:])
        first_timestamp=datetime.combine(first_invoice_day, datetime.min.time())
        invoice_repeat=any(
            invoice_level_repeat(first_timestamp, first_invoice_id,
                datetime.combine(day, datetime.min.time()), invoice_id, PRIMARY_REPEAT_DAYS)
            for day, invoice_id, _ in rows[1:]
        )
        if date_repeat and not invoice_repeat:
            raise AssertionError("date-level repeat must imply invoice-level repeat")
    return {
        "customer_id": next(iter(customer_ids)),
        "first_observed_date": d1,
        "first_observed_month": _period_key(d1, "month"),
        "first_observed_quarter": _period_key(d1, "quarter"),
        "total_qualifying_invoices": len(rows),
        "mature": mature,
        "date_level_repeat": date_repeat,
        "invoice_level_repeat": invoice_repeat,
    }


def calculate_customer_outcomes(occasions, *, data_end_date=DATA_END_DATE):
    by_customer=defaultdict(list)
    for occasion in occasions:
        by_customer[str(occasion["customer_id"])].append(occasion)
    records={customer:calculate_customer_outcome(rows, data_end_date=data_end_date)
             for customer, rows in sorted(by_customer.items())}
    if any(row["date_level_repeat"] and not row["invoice_level_repeat"]
           for row in records.values() if row["mature"]):
        raise AssertionError("date-level repeat implication failed")
    return records


def derive_population_memberships(customer_records, classified_frame):
    """Derive left-censor and all three nested proxy memberships from rows."""
    all_customers=set(customer_records)
    left={cid for cid, record in customer_records.items()
          if record["first_observed_date"] < ACQUISITION_CUTOFF}
    proxy1=all_customers-left
    activity_before_cutoff=set()
    activity_before_first=set()
    for row in classified_frame.itertuples(index=False):
        if pd.isna(row.CustomerID):
            continue
        cid=str(int(row.CustomerID))
        if cid not in all_customers:
            continue
        day=pd.Timestamp(row.InvoiceDate).date()
        if day < ACQUISITION_CUTOFF:
            activity_before_cutoff.add(cid)
        if day < customer_records[cid]["first_observed_date"]:
            activity_before_first.add(cid)
    proxy2=proxy1-activity_before_cutoff
    proxy3=proxy1-activity_before_first
    if left & proxy1 or left | proxy1 != all_customers:
        raise AssertionError("left-censored/proxy-1 partition does not cover all customers")
    if not proxy3 <= proxy2 <= proxy1:
        raise AssertionError("acquisition-proxy populations are not nested")
    return {
        "all_observed":all_customers,
        "left_censored":left,
        "proxy_1":proxy1,
        "proxy_2":proxy2,
        "proxy_3":proxy3,
    }


def _membership_sha256(customer_ids):
    payload="\n".join(sorted(customer_ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _population_definitions(memberships):
    return {population:{"population_label":POPULATION_LABELS[population],
        "customer_count":len(memberships[population]),
        "membership_sha256":_membership_sha256(memberships[population])}
        for population in POPULATION_ORDER}


def _limitations(population):
    flags={"first_observed_not_first_ever", "identified_customers_only",
           "placed_not_net_fulfilled_orders", "last_observation_date_partially_observed",
           "calendar_confounded_population_contrast", "lookback_varies_within_population"}
    if population == "left_censored":
        flags.add("left_censored_population")
    elif population in {"proxy_1", "proxy_2", "proxy_3"}:
        flags.add("diagnostic_sensitivity_not_acquisition_population")
    else:
        flags.add("population_count_is_reconciliation_only")
    return sorted(flags)


def _cell_row(population, members, customer_records, grain, period, outcome_level):
    selected=[customer_records[cid] for cid in sorted(members)
              if customer_records[cid][f"first_observed_{grain}"] == period]
    mature=[row for row in selected if row["mature"]]
    immature_count=len(selected)-len(mature)
    coverage=_period_coverage(grain, period)
    is_reconciliation=population == "all_observed"
    date_num=sum(row["date_level_repeat"] is True for row in mature)
    invoice_num=sum(row["invoice_level_repeat"] is True for row in mature)
    if date_num > invoice_num:
        raise AssertionError(f"date-level numerator exceeds invoice-level numerator in {population}/{period}")
    if is_reconciliation:
        numerator=None
        denominator=None
        share=None
        interval_low=interval_high=None
        date_num_field=invoice_num_field=None
        date_share=invoice_share=None
        date_low=date_high=invoice_low=invoice_high=None
    else:
        denominator=len(mature)
        numerator=(date_num if outcome_level == "date_level_primary" else invoice_num) if denominator else None
        share=(numerator/denominator) if denominator else None
        interval_low, interval_high=_wilson_interval(numerator, denominator)
        date_num_field=date_num if denominator else None
        invoice_num_field=invoice_num if denominator else None
        date_share=(date_num/denominator) if denominator else None
        invoice_share=(invoice_num/denominator) if denominator else None
        date_low,date_high=_wilson_interval(date_num,denominator)
        invoice_low,invoice_high=_wilson_interval(invoice_num,denominator)
    if not selected:
        cell_status="zero_denominator"
    elif is_reconciliation:
        cell_status="reconciliation_only"
    elif not mature:
        cell_status="no_mature_followup"
    elif immature_count:
        cell_status="partial_followup"
    else:
        cell_status="estimable_descriptive"
    lookbacks=[(row["first_observed_date"]-OBSERVATION_START).days for row in selected]
    first_dates=[row["first_observed_date"].isoformat() for row in selected]
    mature_dates=[row["first_observed_date"].isoformat() for row in mature]
    window_complete=_repeat_window_complete(coverage)
    return {
        "contract_version":CONTRACT_VERSION,
        "population_id":population,
        "population_label":POPULATION_LABELS[population],
        "period_grain":grain,
        "first_observed_period":period,
        "outcome_level":outcome_level,
        "anchor_definition":"first_observed_qualifying_purchase_date",
        "window_days":PRIMARY_REPEAT_DAYS,
        # Compatibility field name: stores the complete rule string. Date-level
        # outcomes exclude the anchor date; invoice sensitivity permits a later
        # same-day invoice. The approved 90-day end remains exclusive.
        # Compatibility field name: stores the complete rule string. Date-level
        # outcomes exclude the anchor date; invoice sensitivity permits a later
        # same-day invoice. The approved 90-day end remains exclusive.
        "window_start_inclusive":DATE_WINDOW if outcome_level == "date_level_primary" else INVOICE_WINDOW,
        "window_end_exclusive":"d1 + 90 calendar days",
        "eligibility_definition":ELIGIBILITY,
        "total_customers":len(selected),
        "eligible_customers":len(selected),
        "mature_customers":len(mature),
        "immature_customers":immature_count,
        "maturity_fraction":(len(mature)/len(selected) if selected else None),
        "numerator_repeat_customers":numerator,
        "denominator_mature_eligible_customers":denominator,
        "observed_repeat_share":share,
        "date_level_repeat_numerator":date_num_field,
        "invoice_level_repeat_numerator":invoice_num_field,
        "date_level_observed_repeat_share":date_share,
        "invoice_level_observed_repeat_share":invoice_share,
        "repeat_window_complete":window_complete,
        "has_partial_followup":window_complete == "partial",
        "all_anchors_immature":bool(selected) and len(mature) == 0,
        "lookback_days_min":min(lookbacks) if lookbacks else None,
        "lookback_days_max":max(lookbacks) if lookbacks else None,
        "mature_anchor_date_min":min(mature_dates) if mature_dates else None,
        "mature_anchor_date_max":max(mature_dates) if mature_dates else None,
        "period_coverage":coverage,
        "period_is_partial":coverage != "full",
        "first_observed_date_min":min(first_dates) if first_dates else None,
        "first_observed_date_max":max(first_dates) if first_dates else None,
        "cell_status":cell_status,
        "uncertainty_method":"wilson_95" if share is not None else None,
        "interval_low":interval_low,
        "interval_high":interval_high,
        "date_level_interval_low":date_low,
        "date_level_interval_high":date_high,
        "invoice_level_interval_low":invoice_low,
        "invoice_level_interval_high":invoice_high,
        "limitations":_limitations(population),
        "population_reconciliation_only":is_reconciliation,
    }


def _build_cells(memberships, customer_records):
    rows=[]
    for grain in ("month", "quarter"):
        for population in POPULATION_ORDER:
            for period in _periods(grain):
                for outcome_level in OUTCOME_LEVELS:
                    rows.append(_cell_row(population, memberships[population], customer_records,
                                          grain, period, outcome_level))
    return rows


def _assert_cell_reconciliation(rows, memberships, customer_records):
    for population in POPULATION_ORDER:
        selected=[customer_records[cid] for cid in memberships[population]]
        expected_total=len(selected)
        expected_mature=sum(row["mature"] for row in selected)
        for grain in ("month", "quarter"):
            for level in OUTCOME_LEVELS:
                cells=[row for row in rows if row["population_id"]==population
                       and row["period_grain"]==grain and row["outcome_level"]==level]
                if sum(row["eligible_customers"] for row in cells) != expected_total:
                    raise AssertionError(f"{grain} eligible cells do not reconcile for {population}")
                if sum(row["mature_customers"] for row in cells) != expected_mature:
                    raise AssertionError(f"{grain} maturity cells do not reconcile for {population}")
                for row in cells:
                    if row["mature_customers"]+row["immature_customers"] != row["eligible_customers"]:
                        raise AssertionError(f"mature/immature counts fail for {population}/{row['first_observed_period']}")
                    if row["population_reconciliation_only"]:
                        if any(row[key] is not None for key in (
                            "numerator_repeat_customers", "denominator_mature_eligible_customers",
                            "observed_repeat_share", "interval_low", "interval_high")):
                            raise AssertionError("all_observed must not contain pooled outcome fields")
                    elif row["denominator_mature_eligible_customers"]:
                        if row["numerator_repeat_customers"] > row["denominator_mature_eligible_customers"]:
                            raise AssertionError("repeat numerator exceeds mature denominator")
                        if row["date_level_repeat_numerator"] > row["invoice_level_repeat_numerator"]:
                            raise AssertionError("date-level cell count exceeds invoice-level cell count")


def _assert_reviewed_population_sizes(memberships):
    expected_population_sizes={"all_observed":5852,"left_censored":4239,
                               "proxy_1":1613,"proxy_2":1602,"proxy_3":1601}
    for population, expected in expected_population_sizes.items():
        if len(memberships[population]) != expected:
            raise AssertionError(f"reviewed population count changed for {population}: {len(memberships[population])}")
def _assemble_analysis(validated, occasions):
    customer_records=calculate_customer_outcomes(occasions)
    memberships=derive_population_memberships(customer_records, validated._frame)
    rows=_build_cells(memberships, customer_records)
    _assert_cell_reconciliation(rows, memberships, customer_records)
    _assert_reviewed_population_sizes(memberships)
    from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import _occasion_fingerprints
    occasion_sha,lineage_sha,lineage_rows=_occasion_fingerprints(occasions)
    integrity=validated._integrity_report
    source_reference={
        "source_v1_sha256":integrity["source_sha256"]["v1"],
        "source_v2_sha256":integrity["source_sha256"]["v2"],
        "taxonomy_seed_sha256":integrity["seed_sha256"],
        "stage_a_row_fingerprint_sha256":integrity["row_identity"]["sha256"],
        "occasion_fingerprint_sha256":occasion_sha,
        "occasion_lineage_fingerprint_sha256":lineage_sha,
        "occasion_lineage_rows":lineage_rows,
        "corrected_v2_rows":integrity["corrected_v2_rows"],
    }
    definitions=_population_definitions(memberships)
    return {
        "contract_version":CONTRACT_VERSION,
        "source_reference":source_reference,
        "observation_start":OBSERVATION_START.isoformat(),
        "observation_end_date":DATA_END_DATE.isoformat(),
        "acquisition_proxy_cutoff_inclusive":ACQUISITION_CUTOFF.isoformat(),
        "repeat_window_days":PRIMARY_REPEAT_DAYS,
        "date_level_primary_rule":DATE_WINDOW,
        "invoice_level_sensitivity_rule":INVOICE_WINDOW,
        "populations":definitions,
        "records":rows,
        "analysis_notes":[
            "First observed qualifying purchase is not first-ever purchase or acquisition.",
            "No pooled-period rows are emitted; all_observed records are counts for reconciliation only.",
            "Immature fixed-window outcomes are unknown and their repeat numerators are null.",
            "No partial-follow-up repeat count is emitted.",
            "The three proxy populations are diagnostic sensitivities; no primary is selected.",
            "Left-censored and proxy populations occupy non-overlapping calendar coverage and have unequal look-back; their differences are not established-versus-new effects.",
            "Per-cell Wilson intervals are descriptive and do not support cross-cell testing.",
            "Events are placed qualifying merchandise activity, not net fulfilled orders; unidentified customer lines are excluded.",
            "The historic occasions summary has a frozen invoice-level boundary label; this output states both approved rules explicitly and leaves that frozen output unchanged.",
        ],
    }


def build_analysis(validated_input=None):
    """Build the complete stratified output from one sealed source object."""
    validated=load_validated_purchase_input() if validated_input is None else validated_input
    occasions, _ = build_purchase_occasions(validated)
    return _assemble_analysis(validated, occasions)


def serialize_output(analysis) -> bytes:
    return (json.dumps(analysis, ensure_ascii=False, sort_keys=True, indent=2,
                       separators=(",", ": "), allow_nan=False) + "\n").encode("utf-8")


def _fmt_share(value):
    return "—" if value is None else f"{value:.1%}"


def render_summary(analysis) -> str:
    rows=analysis["records"]
    definitions=analysis["populations"]
    lines=[
        "# B2B-2 Stratified Observed-Repeat Summary",
        "",
        f"Contract: `{analysis['contract_version']}`  ",
        f"Observation: {analysis['observation_start']} through {analysis['observation_end_date']} (last date partial through 12:50)  ",
        f"Cutoff: {analysis['acquisition_proxy_cutoff_inclusive']} inclusive; it is a proxy convention, not an acquisition date.  ",
        f"Date-level primary: `{analysis['date_level_primary_rule']}`. Invoice-level sensitivity: `{analysis['invoice_level_sensitivity_rule']}`.",
        "",
        "## Population definitions and count reconciliation",
        "",
        "| Population | Definition | Customers | Membership SHA-256 |",
        "|---|---|---:|---|",
    ]
    for population in POPULATION_ORDER:
        item=definitions[population]
        lines.append(f"| `{population}` | {item['population_label']} | {item['customer_count']:,} | `{item['membership_sha256']}` |")
    lines += ["", "The left-censored population and proxy 1 are disjoint and partition all observed customers. Proxy 3 ⊆ proxy 2 ⊆ proxy 1. Proxies 1–3 are peer diagnostic sensitivities; none is selected as primary.",
        "", "## Monthly cells", "",
        "Each row shows eligible / mature / immature customers and mature-only repeat numerator / denominator / share. A dash denotes an unavailable fixed-window outcome. No partial-follow-up repeat count is shown.",
        "", "| Month | Population | Eligible / mature / immature | Date-level repeat | Invoice-level sensitivity | Coverage |", "|---|---|---:|---:|---:|---|"]
    for period in _periods("month"):
        for population in POPULATION_ORDER:
            cell=next(row for row in rows if row["population_id"]==population and row["period_grain"]=="month" and row["first_observed_period"]==period and row["outcome_level"]=="date_level_primary")
            partial_note=(f"; mature anchors {cell['mature_anchor_date_min']}–{cell['mature_anchor_date_max']}; Wilson 95% {cell['date_level_interval_low']:.1%}–{cell['date_level_interval_high']:.1%}" if cell["has_partial_followup"] and cell["date_level_repeat_numerator"] is not None else "")
            date_part=(f"{cell['date_level_repeat_numerator']}/{cell['mature_customers']} ({_fmt_share(cell['date_level_observed_repeat_share'])}{partial_note})" if cell["date_level_repeat_numerator"] is not None else "—")
            invoice_part=(f"{cell['invoice_level_repeat_numerator']}/{cell['mature_customers']} ({_fmt_share(cell['invoice_level_observed_repeat_share'])})" if cell["invoice_level_repeat_numerator"] is not None else "—")
            lines.append(f"| {period} | `{population}` | {cell['eligible_customers']} / {cell['mature_customers']} / {cell['immature_customers']} | {date_part} | {invoice_part} | {cell['period_coverage']} |")
    lines += ["", "## Quarterly cells", "", "Quarter values are directly aggregated from customer-level outcomes, never averaged from month shares.", "", "| Quarter | Population | Eligible / mature / immature | Date-level repeat | Invoice-level sensitivity | Coverage |", "|---|---|---:|---:|---:|---|"]
    for period in _periods("quarter"):
        for population in POPULATION_ORDER:
            cell=next(row for row in rows if row["population_id"]==population and row["period_grain"]=="quarter" and row["first_observed_period"]==period and row["outcome_level"]=="date_level_primary")
            partial_note=(f"; mature anchors {cell['mature_anchor_date_min']}–{cell['mature_anchor_date_max']}; Wilson 95% {cell['date_level_interval_low']:.1%}–{cell['date_level_interval_high']:.1%}" if cell["has_partial_followup"] and cell["date_level_repeat_numerator"] is not None else "")
            date_part=(f"{cell['date_level_repeat_numerator']}/{cell['mature_customers']} ({_fmt_share(cell['date_level_observed_repeat_share'])}{partial_note})" if cell["date_level_repeat_numerator"] is not None else "—")
            invoice_part=(f"{cell['invoice_level_repeat_numerator']}/{cell['mature_customers']} ({_fmt_share(cell['invoice_level_observed_repeat_share'])})" if cell["invoice_level_repeat_numerator"] is not None else "—")
            lines.append(f"| {period} | `{population}` | {cell['eligible_customers']} / {cell['mature_customers']} / {cell['immature_customers']} | {date_part} | {invoice_part} | {cell['period_coverage']} |")
    lines += ["", "## Maturity and proxy diagnostics", "",
        "All date-level and invoice-level shares use mature eligible customers only. Immature outcomes are unknown/null. Mature and immature counts sum to eligible customers in every cell. No all-period repeat-rate row or pooled headline is produced.",
        "", "The 2011-09 month is maturity-truncated; only anchors dated 2011-09-01 through 2011-09-10 are mature. Any share shown there is descriptive for that date-restricted mature subset, not the full September first-observed cohort; the table includes its denominator and Wilson 95% interval. 2011-10 and 2011-11 have no mature anchors. December 2011 source coverage ends on December 9 (partial day through 12:50); its 28 proxy customers were first observed within the nine observed calendar days and all are immature.",
        "", "The only Q4 proxy first-observed stratum with mature outcomes is December 2010 (76 eligible); no 2011-Q4 first-observed customer has a mature 90-day outcome. 2009-Q4 contains only December and is data-start truncated. In 2010-Q4, left-censored and proxy cells are separated at the December 1 cutoff.",
        "", "Schema note: `window_start_inclusive` preserves the approved v1 field name, but contains the complete rule string, not a Boolean or boundary value. For date-level primary, `d1 < d2 < d1 + 90` excludes the anchor date; for invoice sensitivity, `d1 <= later invoice date < d1 + 90` permits a later same-day invoice. The 90-day end remains exclusive.",
        "", "## Interpretation limits", "",
        "First observed is not first-ever. Left-censored and proxy populations have disjoint calendar coverage and unequal pre-first-observed look-back; differences cannot be interpreted as established-versus-new customer effects. Month-to-month patterns may mix seasonality with changing unobserved-history composition. These are identified customers in a largely trade/wholesale setting, and events are placed, not net fulfilled, orders. Wilson intervals are per-cell descriptions only and support no cross-cell testing. No acquisition, retention, causal, or consumer-loyalty claim is made.",
        "", "Historical boundary note: the frozen Stage B2A summary labels its invoice-level half-open boundary as the primary boundary. This new output explicitly distinguishes the approved date-level rule from invoice-level sensitivity; the historical function and bytes remain unchanged.",
        "", "## Provenance", "",
        f"- Corrected V2 SHA-256: `{analysis['source_reference']['source_v2_sha256']}`",
        f"- Taxonomy seed SHA-256: `{analysis['source_reference']['taxonomy_seed_sha256']}`",
        f"- Stage A row fingerprint: `{analysis['source_reference']['stage_a_row_fingerprint_sha256']}`",
        f"- Occasion fingerprint: `{analysis['source_reference']['occasion_fingerprint_sha256']}`",
        f"- Occasion lineage fingerprint: `{analysis['source_reference']['occasion_lineage_fingerprint_sha256']}`",
        "- No customer-level records or identifiers are included.", ""]
    return "\n".join(lines)


def write_outputs(analysis, output_dir):
    destination=Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path=destination/OUTPUT_JSON
    summary_path=destination/OUTPUT_SUMMARY
    json_bytes=serialize_output(analysis)
    summary_bytes=render_summary(analysis).encode("utf-8")
    json_path.write_bytes(json_bytes)
    summary_path.write_bytes(summary_bytes)
    return {"json_path":str(json_path),"json_sha256":hashlib.sha256(json_bytes).hexdigest(),
            "summary_path":str(summary_path),"summary_sha256":hashlib.sha256(summary_bytes).hexdigest()}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="/tmp/commercial_ds_b2b2_implementation_002")
    args=parser.parse_args(argv)
    result=write_outputs(build_analysis(), args.output_dir)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

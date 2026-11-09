"""B2B-3 primary monthly date-level repeat outcomes.

Pure synthetic-testable aggregation lives here. Its documented local-source CLI
is fail-closed behind a run-specific owner authorization and one-command opt-in.
It reuses the validated Stage A/O-9 loader and the existing final counts gate.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import sys
import re
import tempfile

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from COMMERCIAL_DS_003_STAGE_B2B2 import derive_population_memberships
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import build_purchase_occasions, load_validated_purchase_input

SCHEMA_ID = "B2B3_PRIMARY_REPEAT_OUTCOMES_V1"
COUNTS_SCHEMA_ID = "B2B3_COUNTS_GATE_SCHEMA_V1"
EXPECTED_FINAL_COUNTS_SHA256 = "20d2eea6a0dffb57430491cf2e3d995b229eefdfae3c4ecd11846024ec29f6d4"
EXPECTED_COUNTS_PRODUCER_SHA256 = "f89c09638a5acf4494627e218e26cc1cdf447f204499fa33fa9fa0242eba12b2"
EXPECTED_FINAL_COUNTS_PATH = REPO_ROOT / ".local/b2b3-gate-output/B2B3-RUN-001-20261108/final.json"
PRIVATE_OUTPUT_ROOT = REPO_ROOT / ".local/b2b3-outcome-output"
AUTH_ENV_VAR = "B2B3_OUTCOME_REAL_DATA_AUTHORIZED"
AUTH_ACTION = "b2b3_primary_outcome_candidate"
AUTH_SCOPE = "B2B3_PRIMARY_REPEAT_OUTCOMES_V1_PRIVATE_CANDIDATE_ONLY"
AUTH_KEYS = {
    "authorization_id", "approved_by", "approved_at_utc", "expires_at_utc", "decision",
    "action", "schema_id", "producer_sha256", "run_id", "counts_gate_sha256",
    "approved_scope", "output_root",
}
B2B2_FINDINGS_PATH = REPO_ROOT.parent / "commercial-ds-release-backups/2026-11-01/COMMERCIAL_DS_B2B_REVIEW_004B_CORRECTED_FINDINGS.md"
B2B2_FINDINGS_SHA256 = "1546b9def54fd99665e73341f3577dbd8acb556f0f2e80769d8e274838c2196e"
SOURCE_START = date(2009, 12, 1)
OBSERVATION_CUTOFF = date(2011, 12, 9)
POPULATIONS = ("left_censored", "proxy_1")
HORIZONS = (30, 60, 90)
COMMON_MATURITY_DAYS = 90
MIN_REPORTABLE_MATURE_N = 30
WILSON_Z_95 = 1.959963984540054
ROUND_DIGITS = 12
MONTHLY_KEYS = {
    "population", "month", "eligible_customer_month_anchor_count",
    "mature_90d_customer_month_anchor_count", "distinct_mature_customer_count",
    "outcome_status",
    "repeat_30_count", "repeat_30_proportion", "repeat_30_wilson_95_low", "repeat_30_wilson_95_high",
    "repeat_60_count", "repeat_60_proportion", "repeat_60_wilson_95_low", "repeat_60_wilson_95_high",
    "repeat_90_count", "repeat_90_proportion", "repeat_90_wilson_95_low", "repeat_90_wilson_95_high",
}
TOP_KEYS = {"metadata", "monthly_results"}
METADATA_KEYS = {
    "schema_id", "analysis_version", "run_id", "execution_mode", "outcome_producer_sha256",
    "counts_gate_path", "counts_gate_sha256", "counts_gate_producer_sha256",
    "authorization_id", "authorization_sha256", "approved_scope", "input_source_pins",
    "source_start", "observation_cutoff", "occasion_contract_id", "anchor_rule_id",
    "outcome_rule_id", "common_maturity_days", "horizons_days", "minimum_reportable_mature_n",
    "wilson_z_95", "wilson_round_digits", "populations", "estimand", "release_status",
    "release_blocker", "uncertainty_note", "population_interpretation", "runtime_context", "outcomes_computed",
}
INPUT_PIN_KEYS = (
    "source_v1_sha256", "source_v2_sha256", "seed_sha256", "inventory_sha256",
    "stage_a_pins_sha256", "occasion_pins_sha256", "bridge_pins_sha256",
    "occasion_output_sha256", "b2b2_json_sha256", "b2b2_summary_sha256",
)
MONTHS = tuple(
    f"{year:04d}-{month:02d}"
    for year, month in ((y, m) for y in range(2009, 2012) for m in range(1, 13))
    if "2009-12" <= f"{year:04d}-{month:02d}" <= "2011-12"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True)
class VerifiedCountsGate:
    payload: dict
    sha256: str
    path: str


def _reject_constant(value: str):
    raise ValueError(f"invalid JSON constant {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse_canonical_json(raw: bytes) -> dict:
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(obj, dict) or _canonical_json(obj) != raw:
        raise ValueError("JSON must be canonical")
    return obj


def _utc_timestamp(value: str) -> datetime:
    if type(value) is not str:
        raise ValueError("authorization timestamp invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("authorization timestamp invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("authorization timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _safe_run_id(run_id: str) -> str:
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("outcome run identifier invalid")
    return run_id


def _load_owner_authorization(path: str | Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("owner authorization file invalid")
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o777 != 0o700:
        raise ValueError("owner authorization directory invalid")
    return _parse_canonical_json(path.read_bytes())


def _validate_owner_authorization(record: dict, *, run_id: str, output_root: Path, now: datetime | None = None) -> bool:
    if not isinstance(record, dict) or set(record) != AUTH_KEYS:
        raise ValueError("owner authorization schema invalid")
    if any(type(record[key]) is not str or not record[key].strip() for key in AUTH_KEYS):
        raise ValueError("owner authorization field invalid")
    if (record["decision"] != "APPROVED" or record["action"] != AUTH_ACTION
            or record["schema_id"] != SCHEMA_ID or record["producer_sha256"] != _sha256(Path(__file__))
            or record["run_id"] != run_id or record["approved_scope"] != AUTH_SCOPE
            or record["output_root"] != str(output_root.resolve())
            or not re.fullmatch(r"[0-9a-f]{64}", record["counts_gate_sha256"])):
        raise ValueError("owner authorization binding mismatch")
    approved = _utc_timestamp(record["approved_at_utc"])
    expires = _utc_timestamp(record["expires_at_utc"])
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if approved > now or expires <= now or expires <= approved:
        raise ValueError("owner authorization expired or not yet valid")
    return True


def load_verified_final_counts_gate(path: str | Path = EXPECTED_FINAL_COUNTS_PATH) -> VerifiedCountsGate:
    """Load the exact owner-finalised counts artifact and return its verified byte hash."""
    path = Path(path)
    try:
        if path.is_symlink() or path.resolve() != EXPECTED_FINAL_COUNTS_PATH.resolve():
            raise ValueError
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != EXPECTED_FINAL_COUNTS_SHA256:
            raise ValueError
        from COMMERCIAL_DS_003_STAGE_B2B3 import load_and_validate
        payload = load_and_validate(path)
        if _sha256(path) != digest:
            raise ValueError
    except Exception:
        raise RuntimeError("approved final counts artifact failed verification") from None
    _validate_counts_gate(payload)
    return VerifiedCountsGate(payload=payload, sha256=digest, path=str(path.resolve()))


def _month_id(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _month_starts() -> tuple[str, ...]:
    return MONTHS


def _validate_counts_gate(gate: dict) -> dict[tuple[str, str], tuple[int, int]]:
    if not isinstance(gate, dict) or set(gate) != {
        "metadata", "calendar_coverage", "primary_monthly_counts",
        "quarter_thresholds", "proxy_feasibility_flags", "integrity",
    }:
        raise ValueError("counts gate schema invalid")
    meta = gate["metadata"]
    if meta.get("schema_id") != COUNTS_SCHEMA_ID or meta.get("outcomes_computed") is not False:
        raise ValueError("counts gate identity invalid")
    if meta.get("producer_sha256") != EXPECTED_COUNTS_PRODUCER_SHA256:
        raise ValueError("counts gate producer does not match reviewed implementation")
    if any(type(meta.get(key)) is not str or not re.fullmatch(r"[0-9a-f]{64}", meta[key]) for key in INPUT_PIN_KEYS):
        raise ValueError("counts gate input provenance invalid")
    if not isinstance(gate["integrity"], list):
        raise ValueError("counts gate integrity list invalid")
    checks = {r.get("check_id"): r.get("passed") for r in gate["integrity"] if isinstance(r, dict)}
    expected_checks = {
        "schema_allowlist", "count_arithmetic", "horizon_common_risk_set", "calendar_span_derivation",
        "b2b2_structural_regression", "independent_reconstruction", "c8_boundary_audit", "privacy_transcript_audit",
    }
    if len(checks) != len(gate["integrity"]) or set(checks) != expected_checks or not all(value is True for value in checks.values()):
        raise ValueError("counts gate is not final and verified")
    rows = gate["primary_monthly_counts"]
    by_key: dict[tuple[str, str, int], dict] = {}
    for row in rows:
        key = (row.get("population"), row.get("month"), row.get("horizon_days"))
        if key in by_key or key[0] not in POPULATIONS or key[1] not in MONTHS or key[2] not in HORIZONS:
            raise ValueError("counts gate primary rows invalid")
        by_key[key] = row
    expected_keys = {(p, m, h) for p in POPULATIONS for m in MONTHS for h in HORIZONS}
    if set(by_key) != expected_keys:
        raise ValueError("counts gate primary rows incomplete")
    result: dict[tuple[str, str], tuple[int, int]] = {}
    for pop in POPULATIONS:
        for month in MONTHS:
            h90 = by_key[(pop, month, 90)]
            eligible = h90.get("eligible_customer_month_count")
            mature = h90.get("h_mature_customer_month_count")
            if type(eligible) is not int or type(mature) is not int or not (0 <= mature <= eligible):
                raise ValueError("counts gate primary counts invalid")
            for horizon in HORIZONS:
                row = by_key[(pop, month, horizon)]
                if row.get("eligible_customer_month_count") != eligible:
                    raise ValueError("counts gate eligible counts vary by horizon")
                if row.get("common_90_mature_customer_month_count") != mature:
                    raise ValueError("counts gate common risk set mismatch")
                if horizon == 90 and row.get("h_mature_customer_month_count") != mature:
                    raise ValueError("counts gate H90 maturity mismatch")
            result[(pop, month)] = (eligible, mature)
    return result


def _load_b2b2_regression_reference() -> dict[tuple[str, str], tuple[int, int]]:
    """Read the two approved B2B-2 table cells without regenerating B2B-2."""
    try:
        raw = B2B2_FINDINGS_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != B2B2_FINDINGS_SHA256:
            raise ValueError
        text = raw.decode("utf-8")
        targets = {("left_censored", "2009-12"): "Left-censored", ("proxy_1", "2010-12"): "Proxy 1"}
        found = {}
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            for key, label in targets.items():
                if cells[0] != key[1] or cells[1] != label:
                    continue
                if key in found:
                    raise ValueError
                denominator = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", cells[2])
                outcome = re.match(r"(\d+)\s*/\s*(\d+)\s*=", cells[3])
                if not denominator or not outcome:
                    raise ValueError
                eligible, mature, immature = map(int, denominator.groups())
                successes, outcome_denominator = map(int, outcome.groups())
                if eligible != mature or immature != 0 or mature != outcome_denominator:
                    raise ValueError
                found[key] = (successes, mature)
        if set(found) != set(targets):
            raise ValueError
        return found
    except Exception:
        raise RuntimeError("approved B2B-2 regression reference unavailable or ambiguous") from None


def _check_b2b2_regression(payload: dict, reference: dict[tuple[str, str], tuple[int, int]]) -> None:
    if set(reference) != {("left_censored", "2009-12"), ("proxy_1", "2010-12")}:
        raise ValueError("B2B-2 regression reference keys invalid")
    cells = {(row["population"], row["month"]): row for row in payload["monthly_results"]}
    for key, (expected_repeat90, expected_denominator) in reference.items():
        row = cells.get(key)
        if row is None or row["mature_90d_customer_month_anchor_count"] != expected_denominator:
            raise ValueError("B2B-2 outcome denominator regression mismatch")
        if row["repeat_90_count"] != expected_repeat90:
            raise ValueError("B2B-2 repeat-90 regression mismatch")


def _normalise_occasions(occasions: list[dict]) -> tuple[dict[str, list[date]], dict[str, str]]:
    if not isinstance(occasions, (list, tuple)):
        raise ValueError("occasion input invalid")
    dates_by_customer: dict[str, set[date]] = defaultdict(set)
    seen_invoices: set[str] = set()
    for row in occasions:
        if not isinstance(row, dict) or not {"customer_id", "invoice_id", "transaction_date"} <= set(row):
            raise ValueError("occasion input schema invalid")
        raw_customer, raw_invoice, raw_date = row["customer_id"], row["invoice_id"], row["transaction_date"]
        customer = str(raw_customer).strip() if type(raw_customer) in (str, int) else ""
        invoice = raw_invoice.strip() if type(raw_invoice) is str else ""
        if not re.fullmatch(r"[1-9][0-9]*", customer) or not re.fullmatch(r"[0-9]{6}", invoice) or invoice in seen_invoices:
            raise ValueError("duplicate or invalid occasion identity")
        seen_invoices.add(invoice)
        try:
            day = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            raise ValueError("occasion date invalid") from None
        if type(raw_date) is not str or day.isoformat() != raw_date or not (SOURCE_START <= day <= OBSERVATION_CUTOFF):
            raise ValueError("occasion date outside frozen source window")
        dates_by_customer[customer].add(day)
    ordered = {cid: sorted(days) for cid, days in dates_by_customer.items()}
    first_dates = {cid: days[0] for cid, days in ordered.items()}
    return ordered, first_dates


def _derive_memberships(dates_by_customer: dict[str, list[date]], classified_frame) -> dict[str, set[str]]:
    first_dates = {cid: {"first_observed_date": days[0]} for cid, days in dates_by_customer.items()}
    try:
        memberships = derive_population_memberships(first_dates, classified_frame)
    except Exception:
        raise ValueError("frozen population membership derivation failed") from None
    selected = {pop: set(memberships[pop]) for pop in POPULATIONS}
    if selected["left_censored"] & selected["proxy_1"]:
        raise ValueError("primary populations overlap")
    if selected["left_censored"] | selected["proxy_1"] != set(dates_by_customer):
        raise ValueError("primary populations do not partition observed customers")
    return selected


def _wilson(successes: int, total: int) -> tuple[float, float]:
    if total <= 0 or not (0 <= successes <= total):
        raise ValueError("Wilson interval inputs invalid")
    p = successes / total
    z = WILSON_Z_95
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denominator
    half = z * math.sqrt((p * (1.0 - p) / total) + (z2 / (4.0 * total * total))) / denominator
    return round(max(0.0, center - half), ROUND_DIGITS), round(min(1.0, center + half), ROUND_DIGITS)


def _new_row(population: str, month: str, eligible: int, mature_customers: int, outcomes: dict[int, int] | None) -> dict:
    row = {
        "population": population,
        "month": month,
        "eligible_customer_month_anchor_count": eligible,
        "mature_90d_customer_month_anchor_count": mature_customers,
        "distinct_mature_customer_count": mature_customers,
        "outcome_status": "reportable" if mature_customers >= MIN_REPORTABLE_MATURE_N else "suppressed_below_threshold",
    }
    for horizon in HORIZONS:
        count = outcomes[horizon] if outcomes is not None else None
        if count is None:
            metrics = (None, None, None, None)
        else:
            low, high = _wilson(count, mature_customers)
            metrics = (count, round(count / mature_customers, ROUND_DIGITS), low, high)
        row.update({
            f"repeat_{horizon}_count": metrics[0],
            f"repeat_{horizon}_proportion": metrics[1],
            f"repeat_{horizon}_wilson_95_low": metrics[2],
            f"repeat_{horizon}_wilson_95_high": metrics[3],
        })
    return row


def _calculate_outcomes(occasions: list[dict], classified_frame, counts_gate: dict, provenance: dict) -> dict:
    gate_counts = _validate_counts_gate(counts_gate)
    dates_by_customer, _ = _normalise_occasions(occasions)
    memberships = _derive_memberships(dates_by_customer, classified_frame)

    anchors: dict[tuple[str, str], list[tuple[str, date]]] = defaultdict(list)
    for customer, days in dates_by_customer.items():
        by_month: dict[str, list[date]] = defaultdict(list)
        for day in days:
            by_month[_month_id(day)].append(day)
        for month, month_days in by_month.items():
            anchors[(customer, month)].append((customer, min(month_days)))

    by_population_month: dict[tuple[str, str], list[tuple[str, date]]] = defaultdict(list)
    for population in POPULATIONS:
        for (customer, month), customer_anchors in anchors.items():
            if customer in memberships[population]:
                by_population_month[(population, month)].extend(customer_anchors)

    output_rows = []
    for population in POPULATIONS:
        for month in MONTHS:
            eligible_gate, mature_gate = gate_counts[(population, month)]
            month_anchors = by_population_month.get((population, month), [])
            mature_anchors = [
                (customer, anchor)
                for customer, anchor in month_anchors
                if anchor + timedelta(days=COMMON_MATURITY_DAYS) <= OBSERVATION_CUTOFF
            ]
            eligible = len(month_anchors)
            denominator = len(mature_anchors)
            distinct_mature = len({customer for customer, _ in mature_anchors})
            if eligible != eligible_gate or denominator != mature_gate or distinct_mature != denominator:
                raise ValueError("outcome anchor counts do not reconcile with final counts gate")

            internal_horizon_counts = {horizon: 0 for horizon in HORIZONS}
            for customer, anchor in mature_anchors:
                customer_days = dates_by_customer[customer]
                for horizon in HORIZONS:
                    boundary = anchor + timedelta(days=horizon)
                    if any(anchor < day < boundary and day <= OBSERVATION_CUTOFF for day in customer_days):
                        internal_horizon_counts[horizon] += 1
            if not (internal_horizon_counts[30] <= internal_horizon_counts[60]
                    <= internal_horizon_counts[90] <= denominator):
                raise ValueError("repeat horizon nesting invariant failed")
            # Counts for small cells exist only transiently in local memory;
            # no suppressed value enters the report or a diagnostic artifact.
            reportable_counts = internal_horizon_counts if denominator >= MIN_REPORTABLE_MATURE_N else None
            output_rows.append(_new_row(population, month, eligible, denominator, reportable_counts))

    payload = {
        "metadata": {
            "schema_id": SCHEMA_ID,
            "analysis_version": "1.0.0",
            **provenance,
            "input_source_pins": {key: counts_gate["metadata"][key] for key in INPUT_PIN_KEYS},
            "source_start": SOURCE_START.isoformat(),
            "observation_cutoff": OBSERVATION_CUTOFF.isoformat(),
            "occasion_contract_id": "O-9",
            "anchor_rule_id": "earliest_qualifying_date_per_customer_calendar_month_v1",
            "outcome_rule_id": "later_distinct_qualifying_date_strictly_before_anchor_plus_H_v1",
            "common_maturity_days": COMMON_MATURITY_DAYS,
            "horizons_days": list(HORIZONS),
            "minimum_reportable_mature_n": MIN_REPORTABLE_MATURE_N,
            "wilson_z_95": WILSON_Z_95,
            "wilson_round_digits": ROUND_DIGITS,
            "populations": list(POPULATIONS),
            "estimand": "observed share of 90-day-mature primary customer-month anchors followed by a later qualifying purchase date strictly before day H",
            "release_status": "NOT_APPROVED_FOR_PUBLICATION",
            "release_blocker": "D-1 unresolved cross-artifact inference risk; owner disclosure decision required",
            "uncertainty_note": "Wilson intervals are within-cell; they do not adjust for customers repeated across months.",
            "population_interpretation": "Frozen left_censored and proxy_1 first-observed groups partition identified customers; proxy_1 is not verified acquisition.",
            "runtime_context": {"python_version": platform.python_version(), "pandas_version": pd.__version__},
            "outcomes_computed": True,
        },
        "monthly_results": output_rows,
    }
    validate_output(payload)
    return payload


def build_primary_outcome_report(occasions: list[dict], classified_frame, counts_gate: dict) -> dict:
    """Synthetic/in-memory test adapter. Real runs must use execute_real_candidate."""
    if not isinstance(counts_gate, dict):
        raise ValueError("synthetic builder requires a counts-gate dictionary")
    gate_digest = hashlib.sha256(_canonical_json(counts_gate)).hexdigest()
    provenance = {
        "run_id": "SYNTHETIC_TEST_ONLY",
        "execution_mode": "synthetic",
        "outcome_producer_sha256": _sha256(Path(__file__)),
        "counts_gate_path": "synthetic-fixture",
        "counts_gate_sha256": gate_digest,
        "counts_gate_producer_sha256": counts_gate.get("metadata", {}).get("producer_sha256"),
        "authorization_id": None,
        "authorization_sha256": None,
        "approved_scope": "SYNTHETIC_TEST_ONLY",
    }
    return _calculate_outcomes(occasions, classified_frame, counts_gate, provenance)


def _ensure_private_output_root(root: Path) -> Path:
    root = Path(root)
    local = root.parent
    if root != PRIVATE_OUTPUT_ROOT or root.is_symlink() or local.is_symlink():
        raise ValueError("approved private outcome root invalid")
    local.mkdir(parents=True, exist_ok=True, mode=0o700)
    if local.stat().st_mode & 0o777 != 0o700:
        raise ValueError("private local directory permissions invalid")
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    if root.stat().st_mode & 0o777 != 0o700:
        raise ValueError("private outcome root permissions invalid")
    return root


def _run_context(run_id: str, producer_sha: str, gate: VerifiedCountsGate, authorization: dict,
                 authorization_sha: str, started_at: str, status: str, **extra) -> dict:
    return {
        "context_schema": "B2B3_OUTCOME_PRIVATE_RUN_CONTEXT_V1",
        "run_id": run_id,
        "operator_id": "Codex CLI",
        "execution_mode": "real",
        "status": status,
        "producer_sha256": producer_sha,
        "counts_gate_path": gate.path,
        "counts_gate_sha256": gate.sha256,
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": authorization_sha,
        "approved_scope": authorization["approved_scope"],
        "input_source_pins": {key: gate.payload["metadata"][key] for key in INPUT_PIN_KEYS},
        "runtime_context": {"python_version": platform.python_version(), "pandas_version": pd.__version__},
        "started_at_utc": started_at,
        **extra,
    }


def _execute_real_candidate(authorization_path: str | Path, run_id: str, *, mode: str,
                            output_root: Path = PRIVATE_OUTPUT_ROOT, gate_loader=None) -> Path:
    """Single-run real entry. All gates are checked before the source loader is called."""
    if mode != "candidate-real":
        raise ValueError("explicit candidate-real mode required")
    if os.environ.get(AUTH_ENV_VAR) != "1":
        raise ValueError("real outcome execution environment gate is closed")
    run_id = _safe_run_id(run_id)
    root = Path(output_root)
    if root != PRIVATE_OUTPUT_ROOT and gate_loader is None:
        raise ValueError("real output root override refused")
    if root == PRIVATE_OUTPUT_ROOT and gate_loader is not None:
        raise ValueError("production execution cannot substitute the final counts-gate loader")
    if root != PRIVATE_OUTPUT_ROOT and (root.is_symlink() or not root.is_absolute()):
        raise ValueError("test output root invalid")
    run_dir = root / run_id
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError("outcome run ID already used; retries are refused")

    authorization = _load_owner_authorization(authorization_path)
    _validate_owner_authorization(authorization, run_id=run_id, output_root=root)
    gate = (gate_loader or load_verified_final_counts_gate)()
    if not isinstance(gate, VerifiedCountsGate):
        raise ValueError("verified counts gate evidence required")
    _validate_counts_gate(gate.payload)
    if authorization["counts_gate_sha256"] != gate.sha256:
        raise ValueError("owner authorization counts-gate hash mismatch")
    reference = _load_b2b2_regression_reference()

    if root == PRIVATE_OUTPUT_ROOT:
        _ensure_private_output_root(root)
    else:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError("outcome run ID already used; retries are refused")
    run_dir.mkdir(mode=0o700)
    os.chmod(run_dir, 0o700)

    producer_sha = _sha256(Path(__file__))
    authorization_sha = hashlib.sha256(_canonical_json(authorization)).hexdigest()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    context = _run_context(run_id, producer_sha, gate, authorization, authorization_sha, started_at, "claimed")
    try:
        _atomic_private_write(run_dir / "run_context.json", _canonical_json(context))
        _atomic_private_write(run_dir / "operation.log", b"B2B3 outcome execution claimed\n")
        validated = load_validated_purchase_input()
        occasions, _summary = build_purchase_occasions(validated)
        provenance = {
            "run_id": run_id,
            "execution_mode": "real",
            "outcome_producer_sha256": producer_sha,
            "counts_gate_path": gate.path,
            "counts_gate_sha256": gate.sha256,
            "counts_gate_producer_sha256": gate.payload["metadata"]["producer_sha256"],
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": authorization_sha,
            "approved_scope": authorization["approved_scope"],
        }
        candidate = _calculate_outcomes(occasions, validated._frame, gate.payload, provenance)
        _check_b2b2_regression(candidate, reference)
        if _sha256(Path(__file__)) != producer_sha:
            raise RuntimeError("outcome producer changed during execution")
        candidate_bytes = serialize_output(candidate)
        _atomic_private_write(run_dir / "candidate.json", candidate_bytes)
        context = _run_context(
            run_id, producer_sha, gate, authorization, authorization_sha, started_at,
            "candidate_generated", candidate_sha256=hashlib.sha256(candidate_bytes).hexdigest(),
            completed_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        _atomic_private_write(run_dir / "run_context.json", _canonical_json(context), overwrite=True)
        _atomic_private_write(run_dir / "operation.log", b"B2B3 outcome candidate generated\n", overwrite=True)
        return run_dir / "candidate.json"
    except Exception:
        try:
            (run_dir / "candidate.json").unlink()
        except FileNotFoundError:
            pass
        failed = _run_context(
            run_id, producer_sha, gate, authorization, authorization_sha, started_at, "failed",
            completed_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        try:
            _atomic_private_write(run_dir / "run_context.json", _canonical_json(failed), overwrite=True)
            _atomic_private_write(run_dir / "operation.log", b"B2B3 outcome operation failed\n", overwrite=True)
        except Exception:
            pass
        raise RuntimeError("B2B3 outcome operation failed; run ID is consumed and retry is refused") from None


def execute_real_candidate(authorization_path: str | Path, run_id: str, *, mode: str) -> Path:
    return _execute_real_candidate(authorization_path, run_id, mode=mode)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Create one privately authorized B2B-3 outcome candidate")
    parser.add_argument("--mode", choices=("candidate-real",), required=True)
    parser.add_argument("--authorization-file", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        execute_real_candidate(args.authorization_file, args.run_id, mode=args.mode)
        print("B2B3 outcome candidate generated")
        return 0
    except Exception:
        print("B2B3 outcome operation failed", file=sys.stderr)
        return 2


def validate_output(payload: dict) -> bool:
    if not isinstance(payload, dict) or set(payload) != TOP_KEYS:
        raise ValueError("outcome output schema invalid")
    metadata = payload["metadata"]
    if not isinstance(metadata, dict) or set(metadata) != METADATA_KEYS:
        raise ValueError("outcome metadata schema invalid")
    if metadata.get("schema_id") != SCHEMA_ID or metadata.get("outcomes_computed") is not True:
        raise ValueError("outcome metadata boundary invalid")
    execution_mode = metadata.get("execution_mode")
    if execution_mode not in ("synthetic", "real"):
        raise ValueError("outcome execution mode invalid")
    if (type(metadata.get("run_id")) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", metadata["run_id"])
            or type(metadata.get("outcome_producer_sha256")) is not str
            or metadata["outcome_producer_sha256"] != _sha256(Path(__file__))
            or type(metadata.get("counts_gate_sha256")) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", metadata["counts_gate_sha256"])
            or metadata.get("counts_gate_producer_sha256") != EXPECTED_COUNTS_PRODUCER_SHA256):
        raise ValueError("outcome provenance metadata invalid")
    if execution_mode == "synthetic":
        if (metadata.get("counts_gate_path") != "synthetic-fixture"
                or metadata.get("authorization_id") is not None
                or metadata.get("authorization_sha256") is not None
                or metadata.get("approved_scope") != "SYNTHETIC_TEST_ONLY"):
            raise ValueError("synthetic provenance invalid")
    elif (type(metadata.get("counts_gate_path")) is not str or not Path(metadata["counts_gate_path"]).is_absolute()
          or type(metadata.get("authorization_id")) is not str or not metadata["authorization_id"]
          or type(metadata.get("authorization_sha256")) is not str
          or not re.fullmatch(r"[0-9a-f]{64}", metadata["authorization_sha256"])
          or metadata.get("approved_scope") != AUTH_SCOPE):
        raise ValueError("real provenance invalid")
    expected_metadata = {
        "schema_id": SCHEMA_ID,
        "analysis_version": "1.0.0",
        "run_id": metadata["run_id"],
        "execution_mode": execution_mode,
        "outcome_producer_sha256": metadata["outcome_producer_sha256"],
        "counts_gate_path": metadata["counts_gate_path"],
        "counts_gate_sha256": metadata["counts_gate_sha256"],
        "counts_gate_producer_sha256": metadata["counts_gate_producer_sha256"],
        "authorization_id": metadata["authorization_id"],
        "authorization_sha256": metadata["authorization_sha256"],
        "approved_scope": metadata["approved_scope"],
        "input_source_pins": metadata.get("input_source_pins"),
        "source_start": SOURCE_START.isoformat(),
        "observation_cutoff": OBSERVATION_CUTOFF.isoformat(),
        "occasion_contract_id": "O-9",
        "anchor_rule_id": "earliest_qualifying_date_per_customer_calendar_month_v1",
        "outcome_rule_id": "later_distinct_qualifying_date_strictly_before_anchor_plus_H_v1",
        "common_maturity_days": COMMON_MATURITY_DAYS,
        "horizons_days": list(HORIZONS),
        "minimum_reportable_mature_n": MIN_REPORTABLE_MATURE_N,
        "wilson_z_95": WILSON_Z_95,
        "wilson_round_digits": ROUND_DIGITS,
        "populations": list(POPULATIONS),
        "estimand": "observed share of 90-day-mature primary customer-month anchors followed by a later qualifying purchase date strictly before day H",
        "release_status": "NOT_APPROVED_FOR_PUBLICATION",
        "release_blocker": "D-1 unresolved cross-artifact inference risk; owner disclosure decision required",
        "uncertainty_note": "Wilson intervals are within-cell; they do not adjust for customers repeated across months.",
        "population_interpretation": "Frozen left_censored and proxy_1 first-observed groups partition identified customers; proxy_1 is not verified acquisition.",
        "runtime_context": {"python_version": platform.python_version(), "pandas_version": pd.__version__},
        "outcomes_computed": True,
    }
    if metadata != expected_metadata:
        raise ValueError("outcome metadata values invalid")
    pins = metadata.get("input_source_pins")
    if (not isinstance(pins, dict) or set(pins) != set(INPUT_PIN_KEYS)
            or any(type(pins[key]) is not str or not re.fullmatch(r"[0-9a-f]{64}", pins[key]) for key in INPUT_PIN_KEYS)):
        raise ValueError("outcome input provenance invalid")
    if metadata.get("horizons_days") != list(HORIZONS) or metadata.get("populations") != list(POPULATIONS):
        raise ValueError("outcome horizon or population set invalid")
    rows = payload["monthly_results"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != MONTHLY_KEYS for row in rows):
        raise ValueError("monthly outcome schema invalid")
    expected_order = [(population, month) for population in POPULATIONS for month in MONTHS]
    actual_order = [(row.get("population"), row.get("month")) for row in rows]
    if actual_order != expected_order:
        raise ValueError("monthly outcome ordering or coverage invalid")
    for row in rows:
        if row["population"] not in POPULATIONS or row["month"] not in MONTHS:
            raise ValueError("monthly outcome category invalid")
        eligible = row["eligible_customer_month_anchor_count"]
        denominator = row["mature_90d_customer_month_anchor_count"]
        distinct = row["distinct_mature_customer_count"]
        if any(type(value) is not int or value < 0 for value in (eligible, denominator, distinct)):
            raise ValueError("monthly structural counts invalid")
        if denominator > eligible or distinct != denominator:
            raise ValueError("monthly anchor denominator identity invalid")
        status = "reportable" if denominator >= MIN_REPORTABLE_MATURE_N else "suppressed_below_threshold"
        if row["outcome_status"] != status:
            raise ValueError("monthly suppression status invalid")
        counts = [row[f"repeat_{h}_count"] for h in HORIZONS]
        proportions = [row[f"repeat_{h}_proportion"] for h in HORIZONS]
        lows = [row[f"repeat_{h}_wilson_95_low"] for h in HORIZONS]
        highs = [row[f"repeat_{h}_wilson_95_high"] for h in HORIZONS]
        if denominator < MIN_REPORTABLE_MATURE_N:
            if any(value is not None for value in counts + proportions + lows + highs):
                raise ValueError("suppressed outcome value present")
        else:
            if any(type(value) is not int or value < 0 or value > denominator for value in counts):
                raise ValueError("repeat count invalid")
            if not (counts[0] <= counts[1] <= counts[2]):
                raise ValueError("repeat horizon order invalid")
            for count, proportion, low, high in zip(counts, proportions, lows, highs):
                if (type(proportion) not in (float, int) or type(low) not in (float, int)
                        or type(high) not in (float, int) or not (0 <= low <= proportion <= high <= 1)
                        or round(count / denominator, ROUND_DIGITS) != proportion):
                    raise ValueError("repeat proportion or Wilson interval invalid")
                if (low, high) != _wilson(count, denominator):
                    raise ValueError("Wilson interval does not match method")
    return True


def serialize_output(payload: dict) -> bytes:
    validate_output(payload)
    try:
        return (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("outcome output is not canonical JSON") from None


def _atomic_private_write(path: Path, raw: bytes, *, overwrite: bool = False) -> Path:
    path = Path(path)
    if path.name not in {"candidate.json", "run_context.json", "operation.log"}:
        raise ValueError("private outcome filename invalid")
    if path.parent.is_symlink() or path.is_symlink() or (path.exists() and not overwrite):
        raise ValueError("private outcome path unavailable")
    target_existed = path.exists()
    temporary = None
    target = path
    old_umask = os.umask(0o077)
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".b2b3-outcome-tmp-", dir=path.parent)
        temporary = Path(temp_name)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        os.chmod(target, 0o600)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return path
    except Exception:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        if not target_existed:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        raise RuntimeError("private outcome candidate write failed") from None
    finally:
        os.umask(old_umask)


def write_private_outcome_candidate(payload: dict, run_id: str, *, output_root: str | Path, synthetic: bool = False) -> Path:
    """Synthetic-only test writer; real writes are only available inside the authorized runner."""
    run_id = _safe_run_id(run_id)
    if synthetic is not True:
        raise ValueError("real outcome writes require the authorized candidate CLI")
    root = Path(output_root)
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = root.resolve()
    if (root.is_symlink() or resolved == PRIVATE_OUTPUT_ROOT.resolve()
            or temp_root not in resolved.parents and resolved != temp_root):
        raise ValueError("synthetic output must use an isolated temporary directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    if root.stat().st_mode & 0o777 != 0o700:
        raise ValueError("synthetic output permissions invalid")
    run_dir = root / run_id
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError("synthetic run directory already exists")
    run_dir.mkdir(mode=0o700)
    os.chmod(run_dir, 0o700)
    try:
        return _atomic_private_write(run_dir / "candidate.json", serialize_output(payload))
    except Exception:
        try:
            run_dir.rmdir()
        except OSError:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())


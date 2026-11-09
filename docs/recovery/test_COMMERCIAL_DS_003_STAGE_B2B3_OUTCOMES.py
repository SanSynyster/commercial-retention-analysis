from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import COMMERCIAL_DS_003_STAGE_B2B3_OUTCOMES as outcomes


def add_occasion(rows, customer, day, invoice):
    rows.append({"customer_id": str(customer), "invoice_id": f"{invoice:06d}", "transaction_date": day.isoformat()})


def frame_for(occasions):
    return pd.DataFrame([
        {"CustomerID": int(row["customer_id"]), "InvoiceDate": pd.Timestamp(row["transaction_date"])}
        for row in occasions
    ])


def synthetic_gate(occasions, classified_frame):
    dates, _ = outcomes._normalise_occasions(occasions)
    memberships = outcomes._derive_memberships(dates, classified_frame)
    anchors = defaultdict(list)
    for cid, days in dates.items():
        by_month = defaultdict(list)
        for day in days:
            by_month[outcomes._month_id(day)].append(day)
        for month, month_days in by_month.items():
            anchors[(cid, month)].append(min(month_days))
    rows = []
    for population in outcomes.POPULATIONS:
        for month in outcomes.MONTHS:
            customer_anchors = [
                (cid, anchor)
                for (cid, m), days in anchors.items()
                if m == month and cid in memberships[population]
                for anchor in days
            ]
            eligible = len(customer_anchors)
            common = sum(anchor + timedelta(days=90) <= outcomes.OBSERVATION_CUTOFF for _, anchor in customer_anchors)
            for horizon in outcomes.HORIZONS:
                mature = sum(anchor + timedelta(days=horizon) <= outcomes.OBSERVATION_CUTOFF for _, anchor in customer_anchors)
                rows.append({
                    "population": population,
                    "month": month,
                    "horizon_days": horizon,
                    "eligible_customer_month_count": eligible,
                    "h_mature_customer_month_count": mature,
                    "h_immature_customer_month_count": eligible - mature,
                    "common_90_mature_customer_month_count": common,
                    "coverage_status": "source_complete",
                    "possible_followup_start": None,
                    "possible_followup_end": None,
                    "followup_months_crossed": [],
                    "followup_coverage_status": "synthetic_fixture",
                })
    return {
        "metadata": {
            "schema_id": outcomes.COUNTS_SCHEMA_ID,
            "producer_sha256": outcomes.EXPECTED_COUNTS_PRODUCER_SHA256,
            "outcomes_computed": False,
            **{key: (f"{index + 1:064x}") for index, key in enumerate(outcomes.INPUT_PIN_KEYS)},
        },
        "calendar_coverage": [],
        "primary_monthly_counts": rows,
        "quarter_thresholds": [],
        "proxy_feasibility_flags": [],
        "integrity": [{"check_id": key, "passed": True} for key in (
            "schema_allowlist", "count_arithmetic", "horizon_common_risk_set",
            "calendar_span_derivation", "b2b2_structural_regression",
            "independent_reconstruction", "c8_boundary_audit", "privacy_transcript_audit",
        )],
    }


def report_for(occasions):
    frame = frame_for(occasions)
    gate = synthetic_gate(occasions, frame)
    return outcomes.build_primary_outcome_report(occasions, frame, gate)


def result(payload, population, month):
    return next(row for row in payload["monthly_results"] if row["population"] == population and row["month"] == month)


def make_auth_record(path, *, run_id, output_root, counts_gate_sha256, producer_sha256=None):
    now = datetime.now(timezone.utc)
    record = {
        "authorization_id": "SYNTHETIC-AUTH-ONLY",
        "approved_by": "synthetic-owner-fixture",
        "approved_at_utc": (now - timedelta(minutes=1)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "decision": "APPROVED",
        "action": outcomes.AUTH_ACTION,
        "schema_id": outcomes.SCHEMA_ID,
        "producer_sha256": producer_sha256 or outcomes._sha256(Path(outcomes.__file__)),
        "run_id": run_id,
        "counts_gate_sha256": counts_gate_sha256,
        "approved_scope": outcomes.AUTH_SCOPE,
        "output_root": str(Path(output_root).resolve()),
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    path.write_bytes(outcomes._canonical_json(record))
    os.chmod(path, 0o600)
    return record


def b2b2_regression_fixture():
    rows = []
    seq = 1
    # Small synthetic cohorts deliberately unrelated to the private B2B-2 cells.
    for cid in range(1, 41):
        add_occasion(rows, cid, date(2009, 12, 1), seq); seq += 1
        if cid <= 17:
            add_occasion(rows, cid, date(2009, 12, 2), seq); seq += 1
    for cid in range(2001, 2041):
        add_occasion(rows, cid, date(2010, 12, 1), seq); seq += 1
        if cid < 2010:
            add_occasion(rows, cid, date(2010, 12, 2), seq); seq += 1
    return rows


class PrimaryOutcomeTests(unittest.TestCase):
    def build_nested_month_fixture(self):
        rows = []
        invoice = 1
        # Left-censored synthetic cohort: nested observed repeat windows.
        for cid in range(1, 31):
            add_occasion(rows, cid, date(2010, 1, 1), invoice); invoice += 1
            if cid <= 10:
                add_occasion(rows, cid, date(2010, 1, 20), invoice); invoice += 1
            elif cid <= 25:
                add_occasion(rows, cid, date(2010, 3, 1), invoice); invoice += 1
            elif cid <= 30:
                add_occasion(rows, cid, date(2010, 3, 31), invoice); invoice += 1
        # Proxy-1 synthetic cohort: one customer-month anchor despite multiple
        # January dates; two invoices on the same later date remain one event date.
        for cid in range(101, 131):
            add_occasion(rows, cid, date(2011, 1, 15), invoice); invoice += 1
            if cid == 101:
                add_occasion(rows, cid, date(2011, 1, 25), invoice); invoice += 1
                add_occasion(rows, cid, date(2011, 2, 1), invoice); invoice += 1
                add_occasion(rows, cid, date(2011, 2, 1), invoice); invoice += 1
            elif cid <= 115:
                add_occasion(rows, cid, date(2011, 2, 1), invoice); invoice += 1
            elif cid <= 120:
                add_occasion(rows, cid, date(2011, 3, 1), invoice); invoice += 1
            elif cid <= 125:
                add_occasion(rows, cid, date(2011, 4, 1), invoice); invoice += 1
        return rows

    def test_nested_horizons_month_boundary_same_day_and_one_anchor_per_customer_month(self):
        payload = report_for(self.build_nested_month_fixture())
        left = result(payload, "left_censored", "2010-01")
        self.assertEqual(left["eligible_customer_month_anchor_count"], 30)
        self.assertEqual(left["mature_90d_customer_month_anchor_count"], 30)
        self.assertEqual([left[f"repeat_{h}_count"] for h in outcomes.HORIZONS], [10, 25, 30])
        p1 = result(payload, "proxy_1", "2011-01")
        self.assertEqual(p1["eligible_customer_month_anchor_count"], 30)
        self.assertEqual(p1["distinct_mature_customer_count"], 30)
        self.assertEqual([p1[f"repeat_{h}_count"] for h in outcomes.HORIZONS], [15, 20, 25])
        self.assertEqual(p1["repeat_30_proportion"], 0.5)
        # February 1 crosses the January month boundary and is a date-level event.
        self.assertGreater(p1["repeat_30_count"], 0)

    def test_exact_30_60_90_day_boundaries_are_excluded(self):
        rows = []
        invoice = 1
        anchor = date(2011, 1, 1)
        for cid in range(1, 31):
            add_occasion(rows, cid, anchor, invoice); invoice += 1
            # Separate cohorts isolate each exact excluded boundary while
            # preserving the nested nature of the shorter-horizon events.
            delta = 30 if cid <= 10 else (60 if cid <= 20 else 90)
            add_occasion(rows, cid, anchor + timedelta(days=delta), invoice); invoice += 1
        p1 = result(report_for(rows), "proxy_1", "2011-01")
        self.assertEqual([p1[f"repeat_{h}_count"] for h in outcomes.HORIZONS], [0, 10, 20])
        self.assertEqual([p1[f"repeat_{h}_proportion"] for h in outcomes.HORIZONS], [0.0, round(10/30, 12), round(20/30, 12)])

    def test_common_90_day_maturity_cutoff_and_partial_final_date(self):
        rows = []
        for cid in range(1, 31):
            add_occasion(rows, cid, date(2011, 9, 10), cid)
            add_occasion(rows, cid, date(2011, 12, 9), 1000 + cid)  # exact H90 boundary
        add_occasion(rows, 31, date(2011, 9, 11), 2000)
        add_occasion(rows, 31, date(2011, 12, 9), 2001)
        payload = report_for(rows)
        sep = result(payload, "proxy_1", "2011-09")
        self.assertEqual(sep["eligible_customer_month_anchor_count"], 31)
        self.assertEqual(sep["mature_90d_customer_month_anchor_count"], 30)
        self.assertEqual(sep["repeat_90_count"], 0)
        self.assertEqual(sep["outcome_status"], "reportable")

    def test_suppression_removes_all_outcome_fields_below_30(self):
        rows = []
        for cid in range(1, 30):
            add_occasion(rows, cid, date(2011, 1, 1), cid)
            add_occasion(rows, cid, date(2011, 1, 2), 100 + cid)
        jan = result(report_for(rows), "proxy_1", "2011-01")
        self.assertEqual(jan["eligible_customer_month_anchor_count"], 29)
        self.assertEqual(jan["mature_90d_customer_month_anchor_count"], 29)
        self.assertEqual(jan["distinct_mature_customer_count"], 29)
        self.assertEqual(jan["outcome_status"], "suppressed_below_threshold")
        for horizon in outcomes.HORIZONS:
            self.assertIsNone(jan[f"repeat_{horizon}_count"])
            self.assertIsNone(jan[f"repeat_{horizon}_proportion"])
            self.assertIsNone(jan[f"repeat_{horizon}_wilson_95_low"])
            self.assertIsNone(jan[f"repeat_{horizon}_wilson_95_high"])

    def test_duplicate_invoice_occasion_fails_closed(self):
        rows = [
            {"customer_id": "1", "invoice_id": "000001", "transaction_date": "2011-01-01"},
            {"customer_id": "1", "invoice_id": "000001", "transaction_date": "2011-01-01"},
        ]
        frame = frame_for(rows)
        gate = synthetic_gate(rows[:1], frame_for(rows[:1]))
        with self.assertRaisesRegex(ValueError, "duplicate or invalid occasion identity"):
            outcomes.build_primary_outcome_report(rows, frame, gate)

    def test_out_of_window_or_after_cutoff_purchase_fails_closed(self):
        for day in (date(2009, 11, 30), date(2011, 12, 10)):
            rows = [{"customer_id": "1", "invoice_id": "000001", "transaction_date": day.isoformat()}]
            frame = frame_for(rows)
            gate = synthetic_gate([], frame_for([]))
            with self.assertRaisesRegex(ValueError, "occasion date outside frozen source window"):
                outcomes.build_primary_outcome_report(rows, frame, gate)

    def test_overlapping_primary_populations_are_rejected(self):
        rows = [{"customer_id": "1", "invoice_id": "000001", "transaction_date": "2011-01-01"}]
        frame = frame_for(rows)
        gate = synthetic_gate(rows, frame)
        bad = {
            "all_observed": {"1"}, "left_censored": {"1"}, "proxy_1": {"1"},
            "proxy_2": set(), "proxy_3": set(),
        }
        with patch.object(outcomes, "derive_population_memberships", return_value=bad):
            with self.assertRaisesRegex(ValueError, "primary populations overlap"):
                outcomes.build_primary_outcome_report(rows, frame, gate)

    def test_gate_reconciliation_mismatch_rejected(self):
        rows = self.build_nested_month_fixture()
        frame = frame_for(rows)
        gate = synthetic_gate(rows, frame)
        gate["primary_monthly_counts"][0]["eligible_customer_month_count"] += 1
        with self.assertRaisesRegex(ValueError, "eligible counts vary by horizon|do not reconcile"):
            outcomes.build_primary_outcome_report(rows, frame, gate)

    def test_deterministic_serialization_and_aggregate_only_schema(self):
        rows = self.build_nested_month_fixture()
        frame = frame_for(rows)
        gate = synthetic_gate(rows, frame)
        first = outcomes.build_primary_outcome_report(rows, frame, gate)
        second = outcomes.build_primary_outcome_report(rows, frame, gate)
        self.assertEqual(outcomes.serialize_output(first), outcomes.serialize_output(second))
        self.assertEqual(set(first), {"metadata", "monthly_results"})
        self.assertEqual(len(first["monthly_results"]), 50)
        self.assertTrue(all(set(row) == outcomes.MONTHLY_KEYS for row in first["monthly_results"]))
        serialized = outcomes.serialize_output(first)
        for forbidden in (b"customer_id", b"invoice_id", b"transaction_date", b"source_row_numbers"):
            self.assertNotIn(forbidden, serialized)

    def test_wilson_interval_and_output_validator_boundaries(self):
        low, high = outcomes._wilson(15, 30)
        self.assertAlmostEqual(low, 0.33154, places=4)
        self.assertAlmostEqual(high, 0.66846, places=4)
        payload = report_for(self.build_nested_month_fixture())
        malformed = deepcopy(payload)
        row = result(malformed, "proxy_1", "2011-01")
        row["repeat_30_count"] = row["repeat_60_count"] + 1
        with self.assertRaisesRegex(ValueError, "repeat horizon order invalid"):
            outcomes.validate_output(malformed)

    def test_output_rejects_unapproved_metadata_and_person_level_fields(self):
        payload = report_for(self.build_nested_month_fixture())
        malformed = deepcopy(payload)
        malformed["metadata"]["estimand"] = "customer 101 had a repeat"
        with self.assertRaisesRegex(ValueError, "metadata values invalid"):
            outcomes.validate_output(malformed)
        malformed = deepcopy(payload)
        malformed["monthly_results"][0]["customer_id"] = "101"
        with self.assertRaisesRegex(ValueError, "monthly outcome schema invalid"):
            outcomes.validate_output(malformed)

    def test_private_candidate_writer_uses_restrictive_permissions_and_no_overwrite(self):
        payload = report_for(self.build_nested_month_fixture())
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-synthetic-") as temp:
            root = Path(temp) / "isolated-output"
            path = outcomes.write_private_outcome_candidate(
                payload, "SYNTHETIC-TEST-OUTCOME-001", output_root=root, synthetic=True,
            )
            self.assertEqual(path.read_bytes(), outcomes.serialize_output(payload))
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                outcomes.write_private_outcome_candidate(
                    payload, "SYNTHETIC-TEST-OUTCOME-001", output_root=root, synthetic=True,
                )
            with self.assertRaisesRegex(ValueError, "isolated temporary directory"):
                outcomes.write_private_outcome_candidate(
                    payload, "SYNTHETIC-NO-REAL-ROOT", output_root=outcomes.PRIVATE_OUTPUT_ROOT, synthetic=True,
                )

    def test_b2b2_reference_regression_uses_only_approved_report_cells(self):
        reference = outcomes._load_b2b2_regression_reference()
        expected_cells = {("left_censored", "2009-12"), ("proxy_1", "2010-12")}
        self.assertEqual(set(reference), expected_cells)
        self.assertTrue(all(type(numerator) is int and type(denominator) is int
                            and 0 <= numerator <= denominator and denominator > 0
                            for numerator, denominator in reference.values()))
        payload = report_for(b2b2_regression_fixture())
        synthetic_reference = {}
        for key in expected_cells:
            cell = result(payload, *key)
            synthetic_reference[key] = (
                cell["repeat_90_count"], cell["mature_90d_customer_month_anchor_count"],
            )
        outcomes._check_b2b2_regression(payload, synthetic_reference)
        changed = deepcopy(payload)
        proxy_key = ("proxy_1", "2010-12")
        proxy_cell = result(changed, *proxy_key)
        old_count = proxy_cell["repeat_90_count"]
        denominator = proxy_cell["mature_90d_customer_month_anchor_count"]
        proxy_cell["repeat_90_count"] = old_count + 1 if old_count < denominator else old_count - 1
        with self.assertRaisesRegex(ValueError, "B2B-2 repeat-90 regression mismatch"):
            outcomes._check_b2b2_regression(changed, synthetic_reference)

    def test_real_entry_rejects_environment_mode_and_missing_auth_before_loader(self):
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-auth-test-") as temp:
            root = Path(temp) / "private"
            sentinel = AssertionError("source loader must not be called")
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "0"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "environment gate"):
                    outcomes._execute_real_candidate(Path(temp)/"missing.json", "RUN-A", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "authorization file invalid"):
                    outcomes._execute_real_candidate(Path(temp)/"missing.json", "RUN-A", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "explicit candidate-real mode"):
                    outcomes._execute_real_candidate(Path(temp)/"missing.json", "RUN-A", mode="synthetic", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()

    def test_malformed_auth_wrong_producer_and_wrong_run_id_fail_before_source(self):
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-auth-test-") as temp:
            root = Path(temp) / "private"
            auth_dir = Path(temp) / "auth"
            auth_dir.mkdir(mode=0o700); os.chmod(auth_dir, 0o700)
            auth_path = auth_dir / "owner.json"
            auth_path.write_text('{"decision":"APPROVED","decision":"APPROVED"}')
            os.chmod(auth_path, 0o600)
            sentinel = AssertionError("source loader must not be called")
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "authorization|duplicate JSON"):
                    outcomes._execute_real_candidate(auth_path, "RUN-A", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()
            fake_hash = "a" * 64
            record = make_auth_record(auth_path, run_id="RUN-A", output_root=root, counts_gate_sha256=fake_hash, producer_sha256="0"*64)
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "binding mismatch"):
                    outcomes._execute_real_candidate(auth_path, "RUN-A", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()
            record["producer_sha256"] = outcomes._sha256(Path(outcomes.__file__))
            auth_path.write_bytes(outcomes._canonical_json(record))
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "binding mismatch"):
                    outcomes._execute_real_candidate(auth_path, "RUN-B", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}):
                with self.assertRaisesRegex(ValueError, "run identifier invalid"):
                    outcomes._execute_real_candidate(auth_path, "../escape", mode="candidate-real", output_root=root)

    def test_wrong_gate_hash_or_substituted_gate_fails_before_source(self):
        rows = self.build_nested_month_fixture()
        frame = frame_for(rows)
        fake_gate_payload = synthetic_gate(rows, frame)
        actual_sha = hashlib.sha256(outcomes._canonical_json(fake_gate_payload)).hexdigest()
        fake_gate = outcomes.VerifiedCountsGate(fake_gate_payload, actual_sha, "/private/synthetic-final.json")
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-auth-test-") as temp:
            root = Path(temp) / "private"
            auth_dir = Path(temp) / "auth"; auth_dir.mkdir(mode=0o700); os.chmod(auth_dir, 0o700)
            auth_path = auth_dir / "owner.json"
            make_auth_record(auth_path, run_id="RUN-GATE", output_root=root, counts_gate_sha256="b"*64)
            sentinel = AssertionError("source loader must not be called")
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_validated_purchase_input", side_effect=sentinel) as loader:
                with self.assertRaisesRegex(ValueError, "counts-gate hash mismatch"):
                    outcomes._execute_real_candidate(auth_path, "RUN-GATE", mode="candidate-real", output_root=root, gate_loader=lambda: fake_gate)
                loader.assert_not_called()
            substituted = Path(temp) / "substituted-final.json"
            substituted.write_bytes(b"{}\n")
            with self.assertRaisesRegex(RuntimeError, "approved final counts artifact failed verification"):
                outcomes.load_verified_final_counts_gate(substituted)

    def test_authorized_synthetic_stub_run_binds_context_and_refuses_duplicate(self):
        rows = b2b2_regression_fixture()
        frame = frame_for(rows)
        synthetic_report = report_for(rows)
        synthetic_reference = {
            (population, month): (
                result(synthetic_report, population, month)["repeat_90_count"],
                result(synthetic_report, population, month)["mature_90d_customer_month_anchor_count"],
            )
            for population, month in (("left_censored", "2009-12"), ("proxy_1", "2010-12"))
        }
        gate_payload = synthetic_gate(rows, frame)
        gate_sha = hashlib.sha256(outcomes._canonical_json(gate_payload)).hexdigest()
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-run-test-") as temp:
            root = Path(temp) / "private"
            root.mkdir(mode=0o700); os.chmod(root, 0o700)
            auth_dir = Path(temp) / "auth"; auth_dir.mkdir(mode=0o700); os.chmod(auth_dir, 0o700)
            auth_path = auth_dir / "owner.json"
            make_auth_record(auth_path, run_id="SYNTHETIC-RUN-ONCE", output_root=root, counts_gate_sha256=gate_sha)
            gate = outcomes.VerifiedCountsGate(gate_payload, gate_sha, str((Path(temp)/"final.json").resolve()))
            mock_validated = SimpleNamespace(_frame=frame)
            with patch.dict(os.environ, {outcomes.AUTH_ENV_VAR: "1"}), \
                 patch.object(outcomes, "load_verified_final_counts_gate", return_value=gate), \
                 patch.object(outcomes, "load_validated_purchase_input", return_value=mock_validated) as loader, \
                 patch.object(outcomes, "build_purchase_occasions", return_value=(rows, {})), \
                 patch.object(outcomes, "_load_b2b2_regression_reference", return_value=synthetic_reference):
                candidate_path = outcomes._execute_real_candidate(auth_path, "SYNTHETIC-RUN-ONCE", mode="candidate-real", output_root=root, gate_loader=lambda: gate)
                loader.assert_called_once_with()
                candidate = json.loads(candidate_path.read_bytes())
                self.assertEqual(candidate["metadata"]["counts_gate_sha256"], gate_sha)
                self.assertEqual(candidate["metadata"]["outcome_producer_sha256"], outcomes._sha256(Path(outcomes.__file__)))
                self.assertEqual(candidate["metadata"]["run_id"], "SYNTHETIC-RUN-ONCE")
                self.assertEqual(candidate["metadata"]["execution_mode"], "real")
                self.assertEqual(candidate["metadata"]["input_source_pins"], {
                    key: gate_payload["metadata"][key] for key in outcomes.INPUT_PIN_KEYS
                })
                self.assertEqual(set(candidate["metadata"]["runtime_context"]), {"python_version", "pandas_version"})
                self.assertNotIn("independent_reconstruction_passed", candidate["metadata"])
                self.assertNotIn("privacy_review_passed", candidate["metadata"])
                self.assertEqual(candidate["metadata"]["release_status"], "NOT_APPROVED_FOR_PUBLICATION")
                self.assertEqual((candidate_path.parent / "candidate.json").stat().st_mode & 0o777, 0o600)
                loader.reset_mock()
                with self.assertRaisesRegex(FileExistsError, "already used"):
                    outcomes._execute_real_candidate(auth_path, "SYNTHETIC-RUN-ONCE", mode="candidate-real", output_root=root, gate_loader=lambda: self.fail("gate loader called"))
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)

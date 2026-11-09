from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import builtins
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import COMMERCIAL_DS_003_STAGE_B2B3_OUTCOME_FINALIZE as finalize


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_private(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    path.write_bytes(raw)
    os.chmod(path, 0o600)
    return path


def make_fixture(base: Path):
    run_id = "SYNTHETIC-OUTCOME-FINAL-TEST-001"
    run_dir = base / run_id
    evidence_dir = base / "verification"
    run_dir.mkdir(mode=0o700)
    evidence_dir.mkdir(mode=0o700)
    os.chmod(run_dir, 0o700)
    os.chmod(evidence_dir, 0o700)
    producer_path = base / "synthetic-outcome-producer.py"
    producer_bytes = b"# synthetic producer identity only\n"
    producer_path.write_bytes(producer_bytes)
    producer_sha = digest(producer_bytes)
    gate_path = base / "synthetic-final-counts.json"
    gate_bytes = b'{"synthetic_gate":true}\n'
    gate_path.write_bytes(gate_bytes)
    gate_sha = digest(gate_bytes)

    auth_path = base / "authorizations" / "synthetic-owner-auth.json"
    auth = {
        "action": "b2b3_primary_outcome_candidate",
        "approved_at_utc": "2026-11-09T00:00:00Z",
        "approved_by": "Synthetic owner fixture",
        "approved_scope": "B2B3_PRIMARY_REPEAT_OUTCOMES_V1_PRIVATE_CANDIDATE_ONLY",
        "authorization_id": "SYNTHETIC-AUTH-001",
        "counts_gate_sha256": gate_sha,
        "decision": "APPROVED",
        "expires_at_utc": "2026-11-09T02:00:00Z",
        "output_root": str(run_dir.parent.resolve()),
        "producer_sha256": producer_sha,
        "run_id": run_id,
        "schema_id": "B2B3_PRIMARY_REPEAT_OUTCOMES_V1",
    }
    auth_raw = canonical(auth)
    write_private(auth_path, auth_raw)
    auth_sha = digest(auth_raw)

    candidate = {
        "metadata": {
            "schema_id": "B2B3_PRIMARY_REPEAT_OUTCOMES_V1",
            "run_id": run_id,
            "execution_mode": "real",
            "outcome_producer_sha256": producer_sha,
            "counts_gate_path": str(gate_path.resolve()),
            "counts_gate_sha256": gate_sha,
            "counts_gate_producer_sha256": "f89c09638a5acf4494627e218e26cc1cdf447f204499fa33fa9fa0242eba12b2",
            "authorization_id": auth["authorization_id"],
            "authorization_sha256": auth_sha,
            "approved_scope": auth["approved_scope"],
            "release_status": finalize.RELEASE_STATUS,
            "outcomes_computed": True,
        },
        "monthly_results": [{"synthetic_aggregate_fixture": True}],
    }
    candidate_raw = canonical(candidate)
    write_private(run_dir / "candidate.json", candidate_raw)
    started = "2026-11-09T00:10:00Z"
    context = {
        "context_schema": "B2B3_OUTCOME_PRIVATE_RUN_CONTEXT_V1",
        "run_id": run_id,
        "operator_id": "Codex CLI",
        "execution_mode": "real",
        "status": "candidate_generated",
        "producer_sha256": producer_sha,
        "counts_gate_path": str(gate_path.resolve()),
        "counts_gate_sha256": gate_sha,
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": auth_sha,
        "approved_scope": auth["approved_scope"],
        "input_source_pins": {},
        "runtime_context": {"python_version": "3.11.14", "pandas_version": "3.0.2"},
        "started_at_utc": started,
        "candidate_sha256": digest(candidate_raw),
    }
    context_raw = canonical(context)
    write_private(run_dir / "run_context.json", context_raw)
    operation_raw = b"B2B3 outcome candidate generated\n"
    write_private(run_dir / "operation.log", operation_raw)

    report_path = evidence_dir / "independent-review.md"
    report_raw = b"Synthetic independent verification report: all 22 B2B-2 reference cells matched.\n"
    write_private(report_path, report_raw)
    reconstruction_raw = b"synthetic reconstruction artifact\n"
    reviewer_code_raw = b"# independent synthetic reviewer\n"
    stdout_raw = b"synthetic verifier output\n"
    write_private(evidence_dir / "reconstructed_outcomes.json", reconstruction_raw)
    write_private(evidence_dir / "claude_outcome_reconstruction.py", reviewer_code_raw)
    write_private(evidence_dir / "verification_stdout.txt", stdout_raw)
    checks = {f"check_{i:02d}": {"passed": True} for i in range(38)}
    checks["b2b2_all_published_first_observed_cells_reproduced"] = {"passed": True, "detail": "22 reference cells matched"}
    checks["b2b2_doc_sha256"] = {"passed": True}
    results = {
        "run_id": run_id,
        "candidate_sha256": digest(candidate_raw),
        "counts_gate_sha256": gate_sha,
        "outcome_producer_sha256": producer_sha,
        "authorization_sha256": auth_sha,
        "field_comparisons": 900,
        "field_mismatches": [],
        "metadata_mismatches": [],
        "all_checks_passed": True,
        "checks": checks,
        "privacy_scan": {
            name: {"customer_id_matches": 0, "invoice_id_matches": 0}
            for name in (
                "COMMERCIAL_DS_B2B3_OUTCOME_RUN_001_CODEX_EXECUTION_REPORT.md",
                "OWNER-AUTH-B2B3-OUTCOME-RUN-001-20261109.json", "candidate.json",
                "operation.log", "run_context.json", "verification_stdout.txt",
            )
        },
    }
    results_raw = canonical(results)
    write_private(evidence_dir / "verification_results.json", results_raw)
    manifest = {
        "run_id": run_id,
        "candidate_sha256": digest(candidate_raw),
        "counts_gate_sha256": gate_sha,
        "outcome_producer_sha256": producer_sha,
        "authorization_sha256": auth_sha,
        "operation_log_sha256": digest(operation_raw),
        "run_context_sha256": digest(context_raw),
        "verification_results_sha256": digest(results_raw),
        "reconstructed_outcomes_sha256": digest(reconstruction_raw),
        "reviewer_code_sha256": digest(reviewer_code_raw),
        "verification_stdout_sha256": digest(stdout_raw),
        "field_comparisons": 900,
        "field_mismatches": 0,
        "checks": 40,
        "verdict": "PASS — INDEPENDENT OUTCOME RECONSTRUCTION VERIFIED",
        "finalised": False,
        "privacy_receipt_created": False,
        "release_status": finalize.RELEASE_STATUS,
    }
    write_private(evidence_dir / "binding_manifest.json", canonical(manifest))
    report_sha = digest(report_raw)
    manifest_sha = digest((evidence_dir / "binding_manifest.json").read_bytes())
    results_sha = digest(results_raw)

    receipt = {
        "schema_id": finalize.RECEIPT_SCHEMA,
        "receipt_id": "SYNTHETIC-PRIVACY-RECEIPT-001",
        "run_id": run_id,
        "candidate_sha256": digest(candidate_raw),
        "operation_log_sha256": digest(operation_raw),
        "authorization_sha256": auth_sha,
        "verification_report_path": str(report_path.resolve()),
        "verification_report_sha256": report_sha,
        "verification_manifest_sha256": manifest_sha,
        "verification_results_sha256": results_sha,
        "decision": "APPROVED",
        "reviewer": "Project owner (ChatGPT confirmation; transcribed by Codex CLI)",
        "approval_scope": finalize.RECEIPT_SCOPE,
        "owner_confirmation_date": "2026-11-09",
        "owner_statement_source": "owner_confirmation_in_chatgpt",
        "owner_statements": {key: True for key in finalize.OWNER_STATEMENT_KEYS},
        "publication_status": finalize.RELEASE_STATUS,
    }
    receipt_path = write_private(run_dir / "privacy_receipt.json", canonical(receipt))
    trust = finalize.TrustedEvidence(
        run_id, digest(candidate_raw), producer_sha, gate_sha, auth_sha, digest(operation_raw),
        digest(context_raw), report_sha, manifest_sha, results_sha, digest(reconstruction_raw),
        digest(reviewer_code_raw), digest(stdout_raw), gate_path, producer_path, auth_path,
        evidence_dir, report_path,
    )
    return {
        "run_dir": run_dir, "verification_dir": evidence_dir, "receipt_path": receipt_path,
        "trust": trust, "candidate_raw": candidate_raw, "candidate": candidate,
    }


class OutcomeOfflineFinalizationTests(unittest.TestCase):
    def with_fixture(self, test):
        with tempfile.TemporaryDirectory(prefix="b2b3-outcome-finalize-") as tmp:
            base = Path(tmp)
            os.chmod(base, 0o700)
            fixture = make_fixture(base)
            test(fixture, base)

    def finalize(self, f):
        return finalize._finalize_bundle(
            run_dir=f["run_dir"], receipt_path=f["receipt_path"],
            verification_dir=f["verification_dir"], trust=f["trust"], allow_temp_test_root=True,
        )

    def assert_no_partial_artifact(self, f):
        self.assertFalse((f["run_dir"] / "final.json").exists())
        self.assertEqual(list(f["run_dir"].glob(".outcome-final-tmp-*")), [])

    def test_successful_synthetic_finalization_preserves_candidate_and_blocks_publication(self):
        def run(f, base):
            path, artifact_sha = self.finalize(f)
            saved = json.loads(path.read_bytes())
            self.assertEqual(path, f["run_dir"] / "final.json")
            self.assertEqual(digest((f["run_dir"] / "candidate.json").read_bytes()), f["trust"].candidate_sha256)
            self.assertEqual(saved["candidate"], f["candidate"])
            self.assertEqual(saved["finalization"]["candidate_sha256"], f["trust"].candidate_sha256)
            self.assertEqual(saved["finalization"]["publication_status"], finalize.RELEASE_STATUS)
            self.assertEqual(saved["final_status"], "FINALISED_PRIVATE")
            self.assertEqual(artifact_sha, digest(path.read_bytes()))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(base.resolve() in p.resolve().parents or p.resolve() == base.resolve() for p in base.rglob("*")))
        self.with_fixture(run)

    def test_incorrect_candidate_hash_is_refused(self):
        def run(f, _):
            with self.assertRaisesRegex(ValueError, "candidate hash mismatch"):
                finalize._finalize_bundle(run_dir=f["run_dir"], receipt_path=f["receipt_path"], verification_dir=f["verification_dir"], trust=replace(f["trust"], candidate_sha256="0"*64), allow_temp_test_root=True)
            self.assertFalse((f["run_dir"] / "final.json").exists())
        self.with_fixture(run)

    def test_incorrect_run_id_and_receipt_binding_are_refused(self):
        def run(f, _):
            with self.assertRaisesRegex(ValueError, "run or receipt location mismatch"):
                finalize._finalize_bundle(run_dir=f["run_dir"], receipt_path=f["receipt_path"], verification_dir=f["verification_dir"], trust=replace(f["trust"], run_id="OTHER-RUN"), allow_temp_test_root=True)
            receipt = json.loads(f["receipt_path"].read_bytes()); receipt["run_id"] = "OTHER-RUN"
            f["receipt_path"].write_bytes(canonical(receipt))
            with self.assertRaisesRegex(ValueError, "privacy receipt binding or scope mismatch"):
                self.finalize(f)
            self.assertFalse((f["run_dir"] / "final.json").exists())
        self.with_fixture(run)

    def test_incorrect_producer_gate_authorization_log_and_context_hashes_are_refused(self):
        cases = (
            ("producer_sha256", "candidate provenance or release status invalid"),
            ("gate_sha256", "candidate provenance or release status invalid"),
            ("authorization_sha256", "run context identity mismatch"),
            ("operation_log_sha256", "operation log identity mismatch"),
            ("run_context_sha256", "run context hash mismatch"),
        )
        for field, message in cases:
            with self.subTest(field=field):
                def run(f, _):
                    trust = replace(f["trust"], **{field: "0"*64})
                    with self.assertRaisesRegex(ValueError, message):
                        finalize._finalize_bundle(run_dir=f["run_dir"], receipt_path=f["receipt_path"], verification_dir=f["verification_dir"], trust=trust, allow_temp_test_root=True)
                    self.assertFalse((f["run_dir"] / "final.json").exists())
                self.with_fixture(run)

    def test_missing_malformed_and_wrongly_scoped_receipts_fail(self):
        cases = (
            ("missing", None),
            ("malformed", b'{"decision":"APPROVED","decision":"APPROVED"}\n'),
            ("wrong scope", "scope"),
        )
        for label, mode in cases:
            with self.subTest(label=label):
                def run(f, _):
                    if mode is None:
                        f["receipt_path"].unlink()
                    elif mode == "scope":
                        rec = json.loads(f["receipt_path"].read_bytes()); rec["approval_scope"] = "PUBLICATION"
                        f["receipt_path"].write_bytes(canonical(rec))
                    else:
                        f["receipt_path"].write_bytes(mode)
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        self.finalize(f)
                    self.assertFalse((f["run_dir"] / "final.json").exists())
                self.with_fixture(run)

    def test_missing_verification_and_mismatched_candidate_identity_fail(self):
        def missing(f, _):
            f["verification_dir"].rename(f["verification_dir"].with_name("missing-verification"))
            with self.assertRaises((ValueError, FileNotFoundError)):
                self.finalize(f)
            self.assertFalse((f["run_dir"] / "final.json").exists())
        self.with_fixture(missing)

        def mismatch(f, _):
            p = f["verification_dir"] / "binding_manifest.json"
            manifest = json.loads(p.read_bytes()); manifest["candidate_sha256"] = "f"*64
            raw = canonical(manifest); p.write_bytes(raw)
            trust = replace(f["trust"], manifest_sha256=digest(raw))
            receipt = json.loads(f["receipt_path"].read_bytes())
            receipt["verification_manifest_sha256"] = digest(raw)
            f["receipt_path"].write_bytes(canonical(receipt))
            with self.assertRaisesRegex(ValueError, "independent reconstruction binding mismatch"):
                finalize._finalize_bundle(run_dir=f["run_dir"], receipt_path=f["receipt_path"], verification_dir=f["verification_dir"], trust=trust, allow_temp_test_root=True)
            self.assertFalse((f["run_dir"] / "final.json").exists())
        self.with_fixture(mismatch)

    def test_duplicate_finalization_is_refused(self):
        def run(f, _):
            final_path, _ = self.finalize(f)
            original = final_path.read_bytes()
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                self.finalize(f)
            self.assertEqual(final_path.read_bytes(), original)
        self.with_fixture(run)

    def test_preexisting_artifact_is_never_overwritten_or_removed(self):
        def run(f, _):
            path = f["run_dir"] / "final.json"
            raw = b"pre-existing synthetic artifact\n"
            path.write_bytes(raw)
            os.chmod(path, 0o600)
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                finalize._atomic_publish(path, b"replacement\n")
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(list(f["run_dir"].glob(".outcome-final-tmp-*")), [])
        self.with_fixture(run)

    def test_post_link_permission_failure_rolls_back_only_its_artifact(self):
        def run(f, _):
            final_path = f["run_dir"] / "final.json"
            real_chmod = os.chmod
            def fail_final_chmod(path, mode, *args, **kwargs):
                if Path(path) == final_path:
                    raise PermissionError("synthetic chmod failure")
                return real_chmod(path, mode, *args, **kwargs)
            with patch.object(finalize.os, "chmod", side_effect=fail_final_chmod):
                with self.assertRaisesRegex(PermissionError, "synthetic chmod failure"):
                    self.finalize(f)
            self.assert_no_partial_artifact(f)
        self.with_fixture(run)

    def test_post_link_directory_sync_failure_rolls_back_and_syncs_cleanup(self):
        def run(f, _):
            real_sync = finalize._fsync_directory
            calls = 0
            def fail_once(directory):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("synthetic directory sync failure")
                return real_sync(directory)
            with patch.object(finalize, "_fsync_directory", side_effect=fail_once):
                with self.assertRaisesRegex(OSError, "synthetic directory sync failure"):
                    self.finalize(f)
            self.assertGreaterEqual(calls, 2)
            self.assert_no_partial_artifact(f)
        self.with_fixture(run)

    def test_pre_link_file_sync_failure_removes_temporary_file(self):
        def run(f, _):
            original_fsync = os.fsync
            calls = 0
            def fail_once(fd):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("synthetic file sync failure")
                return original_fsync(fd)
            with patch.object(finalize.os, "fsync", side_effect=fail_once):
                with self.assertRaisesRegex(OSError, "synthetic file sync failure"):
                    finalize._atomic_publish(f["run_dir"] / "final.json", b"synthetic")
            self.assertGreaterEqual(calls, 2)
            self.assert_no_partial_artifact(f)
        self.with_fixture(run)

    def test_post_link_saved_artifact_validation_failure_rolls_back(self):
        def run(f, _):
            real_check_file = finalize._check_file
            final_path = f["run_dir"] / "final.json"
            def fail_validation(path, **kwargs):
                if Path(path) == final_path:
                    raise RuntimeError("synthetic post-link validation failure")
                return real_check_file(path, **kwargs)
            with patch.object(finalize, "_check_file", side_effect=fail_validation):
                with self.assertRaisesRegex(RuntimeError, "synthetic post-link validation failure"):
                    self.finalize(f)
            self.assert_no_partial_artifact(f)
        self.with_fixture(run)

    def test_cleanup_failure_reports_original_reason_and_unresolved_artifact(self):
        def run(f, _):
            final_path = f["run_dir"] / "final.json"
            real_chmod = os.chmod
            real_unlink = os.unlink
            def fail_final_chmod(path, mode, *args, **kwargs):
                if Path(path) == final_path:
                    raise PermissionError("original chmod reason")
                return real_chmod(path, mode, *args, **kwargs)
            def fail_final_unlink(path, *args, **kwargs):
                if Path(path) == final_path:
                    raise OSError("synthetic cleanup reason")
                return real_unlink(path, *args, **kwargs)
            with patch.object(finalize.os, "chmod", side_effect=fail_final_chmod), \
                 patch.object(finalize.os, "unlink", side_effect=fail_final_unlink):
                with self.assertRaises(finalize.ArtifactCleanupError) as caught:
                    self.finalize(f)
            error = caught.exception
            self.assertEqual(error.artifact_path, final_path)
            self.assertIn("original chmod reason", str(error))
            self.assertIn("synthetic cleanup reason", str(error))
            self.assertTrue(final_path.exists())
            self.assertEqual(list(f["run_dir"].glob(".outcome-final-tmp-*")), [])
        self.with_fixture(run)

    def test_finalizer_hash_is_independently_supplied_and_checked(self):
        path = Path(finalize.__file__).resolve()
        actual = digest(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "does not match independent approval"):
            finalize._verify_finalizer_identity("0" * 64, path)
        self.assertEqual(finalize._verify_finalizer_identity(actual, path), actual)

        def run(f, _):
            calls = 0
            original_verify = finalize._verify_finalizer_identity
            def fail_after_publish(expected, finalizer_path=None):
                nonlocal calls
                calls += 1
                if calls >= 3:
                    raise ValueError("synthetic post-finalizer hash mismatch")
                return original_verify(expected, finalizer_path)
            with patch.object(finalize, "_verify_finalizer_identity", side_effect=fail_after_publish):
                with self.assertRaisesRegex(ValueError, "synthetic post-finalizer hash mismatch"):
                    finalize._finalize_bundle(
                        run_dir=f["run_dir"], receipt_path=f["receipt_path"],
                        verification_dir=f["verification_dir"], trust=f["trust"],
                        allow_temp_test_root=True, approved_finalizer_sha256=actual,
                    )
            self.assertGreaterEqual(calls, 2)
            self.assert_no_partial_artifact(f)
        self.with_fixture(run)

    def test_receipt_identifier_rejects_path_whitespace_and_multiline_values(self):
        invalid_ids = (" ", "has space", "../escape", "line\nbreak", "bad\x00id", "x" * 65)
        for invalid in invalid_ids:
            with self.subTest(receipt_id=repr(invalid)):
                def run(f, _):
                    receipt = json.loads(f["receipt_path"].read_bytes())
                    receipt["receipt_id"] = invalid
                    f["receipt_path"].write_bytes(canonical(receipt))
                    with self.assertRaisesRegex(ValueError, "privacy receipt identifier invalid"):
                        self.finalize(f)
                    self.assert_no_partial_artifact(f)
                self.with_fixture(run)

    def test_production_cli_refuses_missing_independent_finalizer_hash(self):
        argv = [
            "--mode", "finalize-private", "--run-id", finalize.RUN_ID,
            "--private-output-directory", str(finalize.RUN_DIR),
            "--receipt-file", str(finalize.RUN_DIR / "privacy_receipt.json"),
            "--verification-directory", str(finalize.VERIFICATION_DIR),
        ]
        supplied = {
            "--candidate-sha256": finalize.EXPECTED_CANDIDATE_SHA256,
            "--producer-sha256": finalize.EXPECTED_PRODUCER_SHA256,
            "--counts-gate-sha256": finalize.EXPECTED_GATE_SHA256,
            "--authorization-sha256": finalize.EXPECTED_AUTH_SHA256,
            "--operation-log-sha256": finalize.EXPECTED_OPERATION_LOG_SHA256,
            "--run-context-sha256": finalize.EXPECTED_RUN_CONTEXT_SHA256,
            "--verification-report-sha256": finalize.EXPECTED_VERIFICATION_REPORT_SHA256,
            "--verification-manifest-sha256": finalize.EXPECTED_MANIFEST_SHA256,
            "--verification-results-sha256": finalize.EXPECTED_RESULTS_SHA256,
            "--reconstruction-sha256": finalize.EXPECTED_RECONSTRUCTION_SHA256,
            "--reviewer-code-sha256": finalize.EXPECTED_REVIEWER_CODE_SHA256,
        }
        for key, value in supplied.items():
            argv.extend((key, value))
        with patch.object(finalize, "finalize_production", side_effect=AssertionError("must not execute")) as production:
            with redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    finalize.main(argv)
            self.assertEqual(caught.exception.code, 2)
            production.assert_not_called()

    def test_production_finalization_rejects_wrong_independent_finalizer_hash_first(self):
        with patch.object(finalize, "_finalize_bundle", side_effect=AssertionError("bundle must not be read")) as bundle:
            with self.assertRaisesRegex(ValueError, "does not match independent approval"):
                finalize.finalize_production(
                    run_id=finalize.RUN_ID, private_output_directory=finalize.RUN_DIR,
                    receipt_file=finalize.RUN_DIR / "privacy_receipt.json",
                    verification_directory=finalize.VERIFICATION_DIR, supplied_hashes={},
                    approved_finalizer_sha256="0" * 64,
                )
            bundle.assert_not_called()

    def test_interrupted_atomic_publish_leaves_no_partial_final_and_can_resume(self):
        def run(f, _):
            with patch.object(finalize.os, "link", side_effect=OSError("synthetic interruption")):
                with self.assertRaisesRegex(OSError, "synthetic interruption"):
                    self.finalize(f)
            self.assertFalse((f["run_dir"] / "final.json").exists())
            self.assertFalse(list(f["run_dir"].glob(".outcome-final-tmp-*")))
            self.assertEqual(digest((f["run_dir"] / "candidate.json").read_bytes()), f["trust"].candidate_sha256)
            self.finalize(f)
        self.with_fixture(run)

    def test_finalizer_does_not_import_or_invoke_source_or_estimator_modules(self):
        forbidden = {"COMMERCIAL_DS_003_STAGE_B2B3_OUTCOMES", "COMMERCIAL_DS_003_PURCHASE_OCCASIONS", "COMMERCIAL_DS_003_STAGE_B2B2"}
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name in forbidden:
                raise AssertionError("source or estimator module import attempted")
            return original_import(name, *args, **kwargs)
        def run(f, _):
            with patch.object(builtins, "__import__", side_effect=guarded):
                self.finalize(f)
        self.with_fixture(run)
        source = Path(finalize.__file__).read_text()
        self.assertNotIn("COMMERCIAL_DS_003_PURCHASE_OCCASIONS", source)
        self.assertNotIn("COMMERCIAL_DS_003_STAGE_B2B2", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

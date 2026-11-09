"""Offline, private finalisation for the independently verified B2B-3 outcome run.

This module uses only the Python standard library. It never imports the outcome
producer, the Stage A source loader, or any transaction-processing module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import sys


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PRIVATE_ROOT = REPO_ROOT / ".local/b2b3-outcome-output"
RUN_ID = "B2B3-OUTCOME-RUN-001-20261109"
RUN_DIR = PRIVATE_ROOT / RUN_ID
AUTH_PATH = PRIVATE_ROOT / "authorizations/OWNER-AUTH-B2B3-OUTCOME-RUN-001-20261109.json"
COUNTS_GATE_PATH = REPO_ROOT / ".local/b2b3-gate-output/B2B3-RUN-001-20261108/final.json"
VERIFICATION_DIR = PRIVATE_ROOT / "CLAUDE-OUTCOME-VERIFY-001-B2B3-OUTCOME-RUN-001-20261109"
VERIFICATION_REPORT = REPO_ROOT.parent / "commercial-ds-release-backups/2026-11-01/COMMERCIAL_DS_B2B3_OUTCOME_VERIFY_001_CLAUDE_REPORT.md"

EXPECTED_CANDIDATE_SHA256 = "c6374f3dee288fef8c2d152c6339372010290181c9a5eb4d9873d05a5fdd9c59"
EXPECTED_PRODUCER_SHA256 = "48c1aa5badb3fec5dc920cb5346f333e3279d8d2314ad48bda5f7d8d46b77f44"
EXPECTED_GATE_SHA256 = "20d2eea6a0dffb57430491cf2e3d995b229eefdfae3c4ecd11846024ec29f6d4"
EXPECTED_AUTH_SHA256 = "6ebc2159982fec5597bef5dbc10a355c5a2412355c02eb7a6083a3804fd40880"
EXPECTED_OPERATION_LOG_SHA256 = "680ec6ae67edabe07b798dce3a469da644abe715727266e5fc95d2d51dcf221a"
EXPECTED_RUN_CONTEXT_SHA256 = "a88e56d0c3f9e529486282e175667319fa2adb10fcfff44c01ceaa775f333fe4"
EXPECTED_VERIFICATION_REPORT_SHA256 = "9cbbcf657d6cca441f6c473a15b32e387cf7d4eda369008542d6dbcadd7f466b"
EXPECTED_MANIFEST_SHA256 = "5a141bad64994d187f3e5f68d833ee7f6e1058a646d4a49a0033211f96c9692e"
EXPECTED_RESULTS_SHA256 = "3d5d99741d27e6eb3cce810177a3f1bf140963247ca1ffbf6e24677cf62ee87b"
EXPECTED_RECONSTRUCTION_SHA256 = "b376ede371021fa0feb2c0572652cccdf03dd8e90cf893550503926156c886b6"
EXPECTED_REVIEWER_CODE_SHA256 = "3fb0272e6f9c485adb5f08e10e3cef76201656940ee5cbc582d1be3fa1a4e373"
EXPECTED_VERIFICATION_STDOUT_SHA256 = "98113aa01ce718c54f033983dbad0a83736dfb91c88526bbe6869d0634d0dcc7"
EXPECTED_B2B2_REFERENCE_SHA256 = "1546b9def54fd99665e73341f3577dbd8acb556f0f2e80769d8e274838c2196e"

RECEIPT_SCHEMA = "B2B3_OUTCOME_PRIVACY_RECEIPT_V1"
RECEIPT_SCOPE = "B2B3_OUTCOME_RUN_001_PRIVATE_FINALISATION_ONLY_NO_PUBLICATION"
RELEASE_STATUS = "NOT_APPROVED_FOR_PUBLICATION"
FINAL_SCHEMA = "B2B3_OUTCOME_PRIVATE_FINAL_V1"
AUTH_KEYS = {
    "action", "approved_at_utc", "approved_by", "approved_scope", "authorization_id",
    "counts_gate_sha256", "decision", "expires_at_utc", "output_root", "producer_sha256",
    "run_id", "schema_id",
}
RECEIPT_KEYS = {
    "schema_id", "receipt_id", "run_id", "candidate_sha256", "operation_log_sha256",
    "authorization_sha256", "verification_report_path", "verification_report_sha256",
    "verification_manifest_sha256", "verification_results_sha256", "decision", "reviewer",
    "approval_scope", "owner_confirmation_date", "owner_statement_source", "owner_statements",
    "publication_status",
}
OWNER_STATEMENT_KEYS = {
    "complete_codex_execution_transcript_reviewed",
    "no_customer_level_disclosure_observed_by_owner",
    "codex_authorization_transcription_confirmed_by_owner",
    "scientific_and_operational_limitations_accepted_by_owner",
    "private_finalisation_approved_by_owner",
}
FINAL_TOP_KEYS = {"artifact_schema", "final_status", "candidate", "finalization"}
RECEIPT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class ArtifactCleanupError(RuntimeError):
    """A failed finalisation whose invocation-owned artifact could not be removed."""

    def __init__(self, artifact_path: Path, original_failure: BaseException,
                 cleanup_failure: BaseException):
        self.artifact_path = Path(artifact_path)
        self.original_failure = original_failure
        self.cleanup_failure = cleanup_failure
        super().__init__(
            f"cleanup unresolved for artifact {self.artifact_path}; "
            f"original failure: {original_failure}; cleanup failure: {cleanup_failure}"
        )


@dataclass(frozen=True)
class TrustedEvidence:
    run_id: str
    candidate_sha256: str
    producer_sha256: str
    gate_sha256: str
    authorization_sha256: str
    operation_log_sha256: str
    run_context_sha256: str
    verification_report_sha256: str
    manifest_sha256: str
    results_sha256: str
    reconstruction_sha256: str
    reviewer_code_sha256: str
    verification_stdout_sha256: str
    gate_path: Path
    producer_path: Path
    authorization_path: Path
    verification_dir: Path
    verification_report_path: Path


PRODUCTION_EVIDENCE = TrustedEvidence(
    RUN_ID, EXPECTED_CANDIDATE_SHA256, EXPECTED_PRODUCER_SHA256, EXPECTED_GATE_SHA256,
    EXPECTED_AUTH_SHA256, EXPECTED_OPERATION_LOG_SHA256, EXPECTED_RUN_CONTEXT_SHA256,
    EXPECTED_VERIFICATION_REPORT_SHA256, EXPECTED_MANIFEST_SHA256, EXPECTED_RESULTS_SHA256,
    EXPECTED_RECONSTRUCTION_SHA256, EXPECTED_REVIEWER_CODE_SHA256,
    EXPECTED_VERIFICATION_STDOUT_SHA256, COUNTS_GATE_PATH,
    HERE / "COMMERCIAL_DS_003_STAGE_B2B3_OUTCOMES.py", AUTH_PATH, VERIFICATION_DIR,
    VERIFICATION_REPORT,
)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _reject_constant(value: str):
    raise ValueError("non-finite JSON value")


def _parse_json(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _parse_canonical_object(raw: bytes) -> dict:
    value = _parse_json(raw)
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise ValueError("canonical JSON evidence required")
    return value


def _check_file(path: Path, *, mode: int | None = 0o600) -> bytes:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("required evidence file missing or unsafe")
    if mode is not None and path.stat().st_mode & 0o777 != mode:
        raise ValueError("private evidence file mode invalid")
    return path.read_bytes()


def _check_dir(path: Path, *, mode: int = 0o700) -> None:
    path = Path(path)
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o777 != mode:
        raise ValueError("private evidence directory invalid")


def _utc(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError("timestamp invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _verify_authorization(raw: bytes, trust: TrustedEvidence, run_dir: Path, context: dict) -> dict:
    record = _parse_canonical_object(raw)
    if set(record) != AUTH_KEYS or any(type(v) is not str or not v.strip() for v in record.values()):
        raise ValueError("authorization schema invalid")
    if (record["decision"] != "APPROVED" or record["action"] != "b2b3_primary_outcome_candidate"
            or record["schema_id"] != "B2B3_PRIMARY_REPEAT_OUTCOMES_V1"
            or record["run_id"] != trust.run_id or record["producer_sha256"] != trust.producer_sha256
            or record["counts_gate_sha256"] != trust.gate_sha256
            or record["approved_scope"] != "B2B3_PRIMARY_REPEAT_OUTCOMES_V1_PRIVATE_CANDIDATE_ONLY"
            or record["output_root"] != str(run_dir.parent.resolve())):
        raise ValueError("authorization identity mismatch")
    approved, expires, started = map(_utc, (record["approved_at_utc"], record["expires_at_utc"], context["started_at_utc"]))
    if expires <= approved or started < approved or started >= expires:
        raise ValueError("authorization was not valid at run start")
    return record


def _verify_candidate(raw: bytes, trust: TrustedEvidence) -> dict:
    if _sha256_bytes(raw) != trust.candidate_sha256:
        raise ValueError("candidate hash mismatch")
    obj = _parse_canonical_object(raw)
    if set(obj) != {"metadata", "monthly_results"} or not isinstance(obj["monthly_results"], list):
        raise ValueError("candidate shape invalid")
    meta = obj["metadata"]
    if not isinstance(meta, dict):
        raise ValueError("candidate metadata invalid")
    if (meta.get("schema_id") != "B2B3_PRIMARY_REPEAT_OUTCOMES_V1"
            or meta.get("run_id") != trust.run_id or meta.get("execution_mode") != "real"
            or meta.get("outcome_producer_sha256") != trust.producer_sha256
            or meta.get("counts_gate_sha256") != trust.gate_sha256
            or meta.get("counts_gate_producer_sha256") != "f89c09638a5acf4494627e218e26cc1cdf447f204499fa33fa9fa0242eba12b2"
            or meta.get("release_status") != RELEASE_STATUS or meta.get("outcomes_computed") is not True):
        raise ValueError("candidate provenance or release status invalid")
    if any(k in meta for k in ("independent_reconstruction_passed", "privacy_review_passed", "finalized", "finalised")):
        raise ValueError("candidate contains a premature verification or finalisation claim")
    return obj


def _verify_reconstruction(report_raw: bytes, manifest_raw: bytes, results_raw: bytes,
                           reconstruction_raw: bytes, reviewer_code_raw: bytes,
                           stdout_raw: bytes, trust: TrustedEvidence, candidate_sha: str,
                           operation_sha: str, auth_sha: str, context_sha: str) -> tuple[dict, dict]:
    if _sha256_bytes(report_raw) != trust.verification_report_sha256:
        raise ValueError("independent verification report hash mismatch")
    if _sha256_bytes(manifest_raw) != trust.manifest_sha256:
        raise ValueError("verification manifest hash mismatch")
    if _sha256_bytes(results_raw) != trust.results_sha256:
        raise ValueError("verification results hash mismatch")
    if _sha256_bytes(reconstruction_raw) != trust.reconstruction_sha256:
        raise ValueError("reconstructed artifact hash mismatch")
    if _sha256_bytes(reviewer_code_raw) != trust.reviewer_code_sha256:
        raise ValueError("reviewer implementation hash mismatch")
    if _sha256_bytes(stdout_raw) != trust.verification_stdout_sha256:
        raise ValueError("verification stdout hash mismatch")

    manifest = _parse_json(manifest_raw)
    results = _parse_json(results_raw)
    if not isinstance(manifest, dict) or not isinstance(results, dict):
        raise ValueError("verification evidence schema invalid")
    identity = {
        "run_id": trust.run_id,
        "candidate_sha256": candidate_sha,
        "counts_gate_sha256": trust.gate_sha256,
        "outcome_producer_sha256": trust.producer_sha256,
        "authorization_sha256": auth_sha,
        "operation_log_sha256": operation_sha,
        "run_context_sha256": context_sha,
        "verification_results_sha256": trust.results_sha256,
        "reconstructed_outcomes_sha256": trust.reconstruction_sha256,
        "reviewer_code_sha256": trust.reviewer_code_sha256,
        "verification_stdout_sha256": trust.verification_stdout_sha256,
    }
    if any(manifest.get(k) != v for k, v in identity.items()):
        raise ValueError("independent reconstruction binding mismatch")
    results_identity = {
        "run_id": trust.run_id, "candidate_sha256": candidate_sha,
        "counts_gate_sha256": trust.gate_sha256, "outcome_producer_sha256": trust.producer_sha256,
        "authorization_sha256": auth_sha,
    }
    if any(results.get(k) != v for k, v in results_identity.items()):
        raise ValueError("verification results identity mismatch")
    if (manifest.get("field_comparisons") != 900 or manifest.get("field_mismatches") != 0
            or manifest.get("checks") != 40
            or manifest.get("verdict") != "PASS — INDEPENDENT OUTCOME RECONSTRUCTION VERIFIED"
            or manifest.get("finalised") is not False
            or manifest.get("privacy_receipt_created") is not False
            or manifest.get("release_status") != RELEASE_STATUS):
        raise ValueError("independent verification summary invalid")
    checks = results.get("checks")
    if (results.get("all_checks_passed") is not True or results.get("field_comparisons") != 900
            or results.get("field_mismatches") != [] or results.get("metadata_mismatches") != []
            or not isinstance(checks, dict) or len(checks) != 40
            or any(not isinstance(value, dict) or value.get("passed") is not True for value in checks.values())):
        raise ValueError("independent verification checks incomplete or failed")
    b2b2_check = checks.get("b2b2_all_published_first_observed_cells_reproduced")
    b2b2_doc_check = checks.get("b2b2_doc_sha256")
    if (not isinstance(b2b2_check, dict) or b2b2_check.get("passed") is not True
            or "22" not in str(b2b2_check.get("detail", ""))
            or not isinstance(b2b2_doc_check, dict) or b2b2_doc_check.get("passed") is not True):
        raise ValueError("B2B-2 reference comparison incomplete")
    privacy_scan = results.get("privacy_scan")
    expected_scan_files = {
        "COMMERCIAL_DS_B2B3_OUTCOME_RUN_001_CODEX_EXECUTION_REPORT.md",
        "OWNER-AUTH-B2B3-OUTCOME-RUN-001-20261109.json", "candidate.json", "operation.log",
        "run_context.json", "verification_stdout.txt",
    }
    if (not isinstance(privacy_scan, dict) or set(privacy_scan) != expected_scan_files
            or any(not isinstance(row, dict) or row != {"customer_id_matches": 0, "invoice_id_matches": 0}
                   for row in privacy_scan.values())):
        raise ValueError("verification privacy-scan evidence invalid")
    if "all 22" not in report_raw.decode("utf-8").lower():
        raise ValueError("verification report does not identify the B2B-2 reference result")
    return manifest, results


def _verify_receipt(raw: bytes, trust: TrustedEvidence, *, receipt_path: Path,
                    candidate_sha: str, operation_sha: str, auth_sha: str) -> dict:
    receipt = _parse_canonical_object(raw)
    if set(receipt) != RECEIPT_KEYS:
        raise ValueError("privacy receipt schema invalid")
    if (type(receipt["receipt_id"]) is not str
            or not RECEIPT_ID_RE.fullmatch(receipt["receipt_id"])):
        raise ValueError("privacy receipt identifier invalid")
    if any(type(receipt[k]) is not str or not receipt[k].strip() for k in RECEIPT_KEYS - {"owner_statements"}):
        raise ValueError("privacy receipt field invalid")
    if (receipt["schema_id"] != RECEIPT_SCHEMA or receipt["run_id"] != trust.run_id
            or receipt["candidate_sha256"] != candidate_sha or receipt["operation_log_sha256"] != operation_sha
            or receipt["authorization_sha256"] != auth_sha
            or receipt["verification_report_path"] != str(trust.verification_report_path.resolve())
            or receipt["verification_report_sha256"] != trust.verification_report_sha256
            or receipt["verification_manifest_sha256"] != trust.manifest_sha256
            or receipt["verification_results_sha256"] != trust.results_sha256
            or receipt["decision"] != "APPROVED"
            or receipt["reviewer"] != "Project owner (ChatGPT confirmation; transcribed by Codex CLI)"
            or receipt["approval_scope"] != RECEIPT_SCOPE
            or receipt["owner_confirmation_date"] != "2026-11-09"
            or receipt["owner_statement_source"] != "owner_confirmation_in_chatgpt"
            or receipt["publication_status"] != RELEASE_STATUS):
        raise ValueError("privacy receipt binding or scope mismatch")
    statements = receipt["owner_statements"]
    if not isinstance(statements, dict) or set(statements) != OWNER_STATEMENT_KEYS or any(type(v) is not bool or v is not True for v in statements.values()):
        raise ValueError("owner privacy statements incomplete")
    if receipt_path.name != "privacy_receipt.json":
        raise ValueError("privacy receipt path invalid")
    return receipt


def _identity(path: Path) -> tuple[int, int]:
    info = os.stat(path, follow_symlinks=False)
    return info.st_dev, info.st_ino


def _fsync_directory(directory: Path) -> None:
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _unlink_owned(path: Path, identity: tuple[int, int]) -> None:
    try:
        observed = _identity(path)
    except FileNotFoundError:
        return
    if observed != identity:
        raise RuntimeError("artifact identity changed; refusing cleanup")
    os.unlink(path)
    try:
        _identity(path)
    except FileNotFoundError:
        return
    raise RuntimeError("artifact remained after cleanup")


def _rollback_linked_artifact(final_path: Path, final_identity: tuple[int, int],
                              temp_path: Path | None, temp_identity: tuple[int, int] | None,
                              original_failure: BaseException) -> None:
    failures = []
    try:
        _unlink_owned(final_path, final_identity)
        _fsync_directory(final_path.parent)
        if final_path.exists() or final_path.is_symlink():
            raise RuntimeError("artifact reappeared after cleanup")
    except BaseException as exc:
        failures.append(exc)
    if temp_path is not None and temp_identity is not None:
        try:
            _unlink_owned(temp_path, temp_identity)
            _fsync_directory(final_path.parent)
        except FileNotFoundError:
            pass
        except BaseException as exc:
            failures.append(exc)
    if failures:
        raise ArtifactCleanupError(final_path, original_failure, RuntimeError("; ".join(map(str, failures)))) from original_failure


def _atomic_publish(final_path: Path, raw: bytes) -> tuple[int, int]:
    if final_path.exists() or final_path.is_symlink():
        raise FileExistsError("private final artifact already exists")
    tmp_path = None
    tmp_identity = None
    linked = False
    final_identity = None
    old_umask = os.umask(0o077)
    try:
        fd, name = tempfile.mkstemp(prefix=".outcome-final-tmp-", dir=final_path.parent)
        tmp_path = Path(name)
        tmp_stat = os.fstat(fd)
        tmp_identity = (tmp_stat.st_dev, tmp_stat.st_ino)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        # Hard-link creation is atomic and fails if another finalizer won the race.
        os.link(tmp_path, final_path)
        linked = True
        final_identity = tmp_identity
        if _identity(final_path) != final_identity:
            raise RuntimeError("linked artifact identity mismatch")
        os.chmod(final_path, 0o600)
        _fsync_directory(final_path.parent)
        _unlink_owned(tmp_path, tmp_identity)
        tmp_path = None
        _fsync_directory(final_path.parent)
        return final_identity
    except BaseException as original_failure:
        if linked and final_identity is not None:
            _rollback_linked_artifact(final_path, final_identity, tmp_path, tmp_identity, original_failure)
        elif isinstance(original_failure, FileExistsError):
            if tmp_path is not None and tmp_identity is not None:
                try:
                    _unlink_owned(tmp_path, tmp_identity)
                    _fsync_directory(final_path.parent)
                except FileNotFoundError:
                    pass
                except BaseException as cleanup_failure:
                    raise ArtifactCleanupError(final_path, original_failure, cleanup_failure) from original_failure
            raise
        elif tmp_path is not None and tmp_identity is not None:
            try:
                _unlink_owned(tmp_path, tmp_identity)
                _fsync_directory(final_path.parent)
            except FileNotFoundError:
                pass
            except BaseException as cleanup_failure:
                raise ArtifactCleanupError(tmp_path, original_failure, cleanup_failure) from original_failure
        raise
    finally:
        os.umask(old_umask)


def _verify_finalizer_identity(expected_sha256: str, finalizer_path: Path | None = None) -> str:
    if type(expected_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("independently approved finaliser SHA-256 is required")
    path = Path(finalizer_path or __file__).resolve()
    actual = _sha256_file(path)
    if actual != expected_sha256:
        raise ValueError("finaliser identity does not match independent approval")
    return actual


def _finalize_bundle(*, run_dir: Path, receipt_path: Path, verification_dir: Path,
                     trust: TrustedEvidence, allow_temp_test_root: bool = False,
                     approved_finalizer_sha256: str | None = None) -> tuple[Path, str]:
    run_dir, receipt_path, verification_dir = Path(run_dir), Path(receipt_path), Path(verification_dir)
    if run_dir.name != trust.run_id or receipt_path.parent.resolve() != run_dir.resolve():
        raise ValueError("run or receipt location mismatch")
    if run_dir.is_symlink() or verification_dir.is_symlink() or receipt_path.is_symlink():
        raise ValueError("symlink evidence path refused")
    if allow_temp_test_root:
        temp_root = Path(tempfile.gettempdir()).resolve()
        if temp_root not in run_dir.resolve().parents:
            raise ValueError("synthetic finalization must stay in a temporary directory")
    else:
        if run_dir.resolve() != RUN_DIR.resolve() or verification_dir.resolve() != VERIFICATION_DIR.resolve():
            raise ValueError("production evidence directories are fixed")
        _verify_finalizer_identity(approved_finalizer_sha256 or "")
    if approved_finalizer_sha256 is not None:
        _verify_finalizer_identity(approved_finalizer_sha256)
    _check_dir(run_dir)
    _check_dir(run_dir.parent)
    _check_dir(verification_dir)
    final_path = run_dir / "final.json"
    if final_path.exists() or final_path.is_symlink():
        raise FileExistsError("private final artifact already exists")

    candidate_path = run_dir / "candidate.json"
    candidate_raw = _check_file(candidate_path)
    candidate_sha = _sha256_bytes(candidate_raw)
    candidate = _verify_candidate(candidate_raw, trust)
    context_raw = _check_file(run_dir / "run_context.json")
    context_sha = _sha256_bytes(context_raw)
    if context_sha != trust.run_context_sha256:
        raise ValueError("run context hash mismatch")
    context = _parse_canonical_object(context_raw)
    if (context.get("run_id") != trust.run_id or context.get("status") != "candidate_generated"
            or context.get("execution_mode") != "real" or context.get("producer_sha256") != trust.producer_sha256
            or context.get("counts_gate_sha256") != trust.gate_sha256
            or context.get("candidate_sha256") != candidate_sha
            or context.get("counts_gate_path") != str(trust.gate_path.resolve())
            or context.get("authorization_sha256") != trust.authorization_sha256):
        raise ValueError("run context identity mismatch")

    log_raw = _check_file(run_dir / "operation.log")
    operation_sha = _sha256_bytes(log_raw)
    if operation_sha != trust.operation_log_sha256 or log_raw != b"B2B3 outcome candidate generated\n":
        raise ValueError("operation log identity mismatch")
    auth_raw = _check_file(trust.authorization_path)
    auth_sha = _sha256_bytes(auth_raw)
    if auth_sha != trust.authorization_sha256:
        raise ValueError("authorization record hash mismatch")
    authorization = _verify_authorization(auth_raw, trust, run_dir, context)
    if context.get("authorization_id") != authorization["authorization_id"]:
        raise ValueError("run context authorization identity mismatch")
    candidate_meta = candidate["metadata"]
    if (candidate_meta.get("authorization_sha256") != auth_sha
            or candidate_meta.get("authorization_id") != authorization["authorization_id"]
            or candidate_meta.get("approved_scope") != authorization["approved_scope"]
            or candidate_meta.get("counts_gate_path") != str(trust.gate_path.resolve())):
        raise ValueError("candidate authorization or gate path binding mismatch")
    gate_raw = _check_file(trust.gate_path, mode=None)
    if _sha256_bytes(gate_raw) != trust.gate_sha256:
        raise ValueError("finalized counts-gate hash mismatch")
    if trust.producer_path.is_symlink() or _sha256_file(trust.producer_path) != trust.producer_sha256:
        raise ValueError("reviewed outcome producer hash mismatch")

    _check_dir(trust.authorization_path.parent)
    receipt_raw = _check_file(receipt_path)
    receipt = _verify_receipt(receipt_raw, trust, receipt_path=receipt_path,
                              candidate_sha=candidate_sha, operation_sha=operation_sha, auth_sha=auth_sha)
    report_raw = _check_file(trust.verification_report_path, mode=None)
    manifest_raw = _check_file(verification_dir / "binding_manifest.json")
    results_raw = _check_file(verification_dir / "verification_results.json")
    reconstruction_raw = _check_file(verification_dir / "reconstructed_outcomes.json")
    reviewer_code_raw = _check_file(verification_dir / "claude_outcome_reconstruction.py")
    stdout_raw = _check_file(verification_dir / "verification_stdout.txt")
    manifest, _results = _verify_reconstruction(
        report_raw, manifest_raw, results_raw, reconstruction_raw, reviewer_code_raw,
        stdout_raw, trust, candidate_sha, operation_sha, auth_sha, context_sha,
    )

    if hashlib.sha256(candidate_path.read_bytes()).hexdigest() != candidate_sha:
        raise ValueError("candidate changed during finalisation validation")
    finalizer_sha = None
    if approved_finalizer_sha256 is not None:
        finalizer_sha = _verify_finalizer_identity(approved_finalizer_sha256 or "")
    else:
        finalizer_sha = _sha256_file(Path(__file__).resolve())
    finalization = {
        "finalization_schema": "B2B3_OUTCOME_FINALIZATION_PROVENANCE_V1",
        "status": "FINALISED_PRIVATE",
        "run_id": trust.run_id,
        "candidate_sha256": candidate_sha,
        "outcome_producer_sha256": trust.producer_sha256,
        "counts_gate_sha256": trust.gate_sha256,
        "authorization_sha256": auth_sha,
        "operation_log_sha256": operation_sha,
        "run_context_sha256": context_sha,
        "privacy_receipt_id": receipt["receipt_id"],
        "privacy_receipt_sha256": _sha256_bytes(receipt_raw),
        "verification_report_sha256": trust.verification_report_sha256,
        "verification_manifest_sha256": trust.manifest_sha256,
        "verification_results_sha256": trust.results_sha256,
        "verification_checks_passed": manifest["checks"],
        "field_comparisons": manifest["field_comparisons"],
        "publication_status": RELEASE_STATUS,
        "release_blocker": "D-1 unresolved cross-artifact disclosure risk; future disclosure requires separate owner approval",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "finalizer_sha256": finalizer_sha,
    }
    final_obj = {"artifact_schema": FINAL_SCHEMA, "final_status": "FINALISED_PRIVATE",
                 "candidate": candidate, "finalization": finalization}
    final_raw = _canonical_json(final_obj)
    created_identity = _atomic_publish(final_path, final_raw)
    try:
        saved_raw = _check_file(final_path)
        saved = _parse_canonical_object(saved_raw)
        if (set(saved) != FINAL_TOP_KEYS or saved.get("artifact_schema") != FINAL_SCHEMA
                or saved.get("final_status") != "FINALISED_PRIVATE"
                or saved.get("candidate") != candidate or saved.get("finalization") != finalization
                or saved["finalization"].get("publication_status") != RELEASE_STATUS
                or _sha256_bytes(candidate_path.read_bytes()) != candidate_sha):
            raise RuntimeError("saved final artifact revalidation failed")
        if approved_finalizer_sha256 is not None:
            _verify_finalizer_identity(approved_finalizer_sha256 or "")
        return final_path, _sha256_bytes(saved_raw)
    except BaseException as original_failure:
        _rollback_linked_artifact(final_path, created_identity, None, None, original_failure)
        raise


def finalize_production(*, run_id: str, private_output_directory: Path, receipt_file: Path,
                         verification_directory: Path, supplied_hashes: dict[str, str],
                         approved_finalizer_sha256: str) -> tuple[Path, str]:
    _verify_finalizer_identity(approved_finalizer_sha256)
    if run_id != RUN_ID:
        raise ValueError("approved run ID required")
    required = {
        "candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "producer_sha256": EXPECTED_PRODUCER_SHA256,
        "counts_gate_sha256": EXPECTED_GATE_SHA256,
        "authorization_sha256": EXPECTED_AUTH_SHA256,
        "operation_log_sha256": EXPECTED_OPERATION_LOG_SHA256,
        "run_context_sha256": EXPECTED_RUN_CONTEXT_SHA256,
        "verification_report_sha256": EXPECTED_VERIFICATION_REPORT_SHA256,
        "verification_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "verification_results_sha256": EXPECTED_RESULTS_SHA256,
        "reconstruction_sha256": EXPECTED_RECONSTRUCTION_SHA256,
        "reviewer_code_sha256": EXPECTED_REVIEWER_CODE_SHA256,
    }
    if supplied_hashes != required:
        raise ValueError("explicit finalisation hashes do not match reviewed identities")
    if Path(private_output_directory).resolve() != RUN_DIR.resolve():
        raise ValueError("private run output directory mismatch")
    if Path(receipt_file).resolve() != (RUN_DIR / "privacy_receipt.json").resolve():
        raise ValueError("privacy receipt path mismatch")
    if Path(verification_directory).resolve() != VERIFICATION_DIR.resolve():
        raise ValueError("independent verification directory mismatch")
    return _finalize_bundle(run_dir=RUN_DIR, receipt_path=RUN_DIR / "privacy_receipt.json",
                            verification_dir=VERIFICATION_DIR, trust=PRODUCTION_EVIDENCE,
                            approved_finalizer_sha256=approved_finalizer_sha256)


def _production_hash_args(parser) -> None:
    parser.add_argument("--approved-finalizer-sha256", required=True,
                        help="finaliser SHA-256 independently pinned by the reviewer")
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--producer-sha256", required=True)
    parser.add_argument("--counts-gate-sha256", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--operation-log-sha256", required=True)
    parser.add_argument("--run-context-sha256", required=True)
    parser.add_argument("--verification-report-sha256", required=True)
    parser.add_argument("--verification-manifest-sha256", required=True)
    parser.add_argument("--verification-results-sha256", required=True)
    parser.add_argument("--reconstruction-sha256", required=True)
    parser.add_argument("--reviewer-code-sha256", required=True)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Offline private finalisation of the verified B2B-3 outcome candidate")
    parser.add_argument("--mode", choices=("finalize-private",), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-output-directory", required=True)
    parser.add_argument("--receipt-file", required=True)
    parser.add_argument("--verification-directory", required=True)
    _production_hash_args(parser)
    args = parser.parse_args(argv)
    hashes = {
        "candidate_sha256": args.candidate_sha256, "producer_sha256": args.producer_sha256,
        "counts_gate_sha256": args.counts_gate_sha256, "authorization_sha256": args.authorization_sha256,
        "operation_log_sha256": args.operation_log_sha256, "run_context_sha256": args.run_context_sha256,
        "verification_report_sha256": args.verification_report_sha256,
        "verification_manifest_sha256": args.verification_manifest_sha256,
        "verification_results_sha256": args.verification_results_sha256,
        "reconstruction_sha256": args.reconstruction_sha256, "reviewer_code_sha256": args.reviewer_code_sha256,
    }
    try:
        finalize_production(run_id=args.run_id, private_output_directory=Path(args.private_output_directory),
                            receipt_file=Path(args.receipt_file), verification_directory=Path(args.verification_directory),
                            supplied_hashes=hashes,
                            approved_finalizer_sha256=args.approved_finalizer_sha256)
        print("Private outcome final artifact generated")
        return 0
    except ArtifactCleanupError as exc:
        print(f"Private finalisation failed; {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("Private outcome finalisation failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

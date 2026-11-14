"""Build and validate the aggregate-only P3-008 causal evidence app bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT.parent / "source_data/hillstrom"
DEFAULT_BUNDLE = ROOT / "app_data/p3_causal_v1.json"
EXPECTED_CONTENT_SHA256 = "720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b"
EXPECTED_DATASET_SHA256 = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
EXPECTED_SPLIT_SHA256 = "0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce"
SCHEMA_VERSION = 1
REPORTS = {
    "p3_008a": "docs/research/COMMERCIAL_DS_P3_008A_CAUSAL_DATASET_AND_DESIGN.md",
    "p3_008b": "docs/research/COMMERCIAL_DS_P3_008B_CAUSAL_ML_AND_UPLIFT.md",
    "p3_008c": "docs/research/COMMERCIAL_DS_P3_008C_LOCKED_TEST_CAUSAL_EVALUATION.md",
    "p3_008d": "docs/research/COMMERCIAL_DS_P3_008D_CAUSAL_RESEARCH_SYNTHESIS.md",
}
SOURCES = {
    "p3_008a": {
        "path": "p3_008a_outputs/hillstrom_audit_aggregate_private.json",
        "sha256": "58a33907a118990ae12f91f7d560527d84034d06dfb581f02461065e5f756c70",
        "report": REPORTS["p3_008a"],
    },
    "p3_008b": {
        "path": "p3_008b_outputs/hillstrom_uplift_aggregate_private.json",
        "sha256": "baee1318cd1e21c8b51fed04340184dbf68c4cc7e9054bc1a7a87e27b58ff362",
        "report": REPORTS["p3_008b"],
    },
    "p3_008c": {
        "path": "p3_008c_outputs/hillstrom_locked_test_aggregate_private.json",
        "sha256": "ac22045cbb94379295cbd5950ab017608d2d10d3bde5575c854ed8cc2c7fb3ac",
        "report": REPORTS["p3_008c"],
    },
}
EXPECTED_P3_008D_REPORT_SHA256 = "af639847c792ccfcf8850e0f91b8cdce4aa99ba29fb6ad52fa88799e2fca9ba1"
FORBIDDEN_MARKERS = ("customer_id", "customerid", "private_test_rows", "development_predictions", ".parquet", ".csv", "/users/")


class BundleError(ValueError):
    """Invalid application bundle or source provenance."""


class SourceUnavailableError(FileNotFoundError):
    """An explicitly configured private source is unavailable."""


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_sources(source_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    aggregates: dict[str, dict[str, Any]] = {}
    provenance: dict[str, dict[str, str]] = {}
    for name, spec in SOURCES.items():
        path = source_root / spec["path"]
        if not path.is_file():
            raise SourceUnavailableError(f"Missing required P3-008 {name.upper()} aggregate: {path}")
        digest = raw_sha256(path)
        if digest != spec["sha256"]:
            raise BundleError(f"P3-008 {name.upper()} aggregate SHA-256 mismatch: {digest}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleError(f"P3-008 {name.upper()} aggregate is invalid UTF-8 JSON: {exc}") from None
        if not isinstance(payload, dict):
            raise BundleError(f"P3-008 {name.upper()} aggregate must be a JSON object")
        aggregates[name] = payload
        provenance[name] = {
            "report": spec["report"],
            "source_file": f"source_data/hillstrom/{spec['path']}",
            "sha256_raw_file": digest,
        }

    report_path = ROOT / REPORTS["p3_008d"]
    if not report_path.is_file():
        raise SourceUnavailableError(f"Missing committed P3-008D synthesis report: {report_path}")
    report_digest = raw_sha256(report_path)
    if report_digest != EXPECTED_P3_008D_REPORT_SHA256:
        raise BundleError(f"P3-008D synthesis report SHA-256 mismatch: {report_digest}")
    provenance["p3_008d"] = {
        "report": REPORTS["p3_008d"],
        "sha256_report": report_digest,
    }
    return aggregates, provenance


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BundleError(f"{field} must be a finite number")
    return float(value)


def _project(aggregates: dict[str, dict[str, Any]], provenance: dict[str, dict[str, str]]) -> dict[str, Any]:
    a, b, c = aggregates["p3_008a"], aggregates["p3_008b"], aggregates["p3_008c"]
    try:
        arm_counts = a["assignment"]["arm_counts"]
        split_counts = a["split"]["allocation_by_arm"]
        primary = c["primary"]
        secondary_source = c["secondary"]
        expected_random = c["expected_random_policy_20pct"]
        dev_comparisons = b["expected_random_comparisons"]
        dev_pop = b["population"]
        dev_input = b["input"]
    except (KeyError, TypeError) as exc:
        raise BundleError(f"P3-008 aggregate missing required section: {exc}") from None

    if a.get("dataset", {}).get("rows") != 64000 or a.get("dataset", {}).get("raw_sha256") != EXPECTED_DATASET_SHA256:
        raise BundleError("P3-008A aggregate does not match the documented Hillstrom dataset")
    if a.get("dataset", {}).get("row_split_sha256") != EXPECTED_SPLIT_SHA256:
        raise BundleError("P3-008A aggregate split hash differs from the frozen split")
    if b.get("input", {}).get("source_sha256") != EXPECTED_DATASET_SHA256 or b.get("input", {}).get("split_sha256") != EXPECTED_SPLIT_SHA256:
        raise BundleError("P3-008B aggregate does not use the frozen dataset and split")
    if c.get("metadata", {}).get("source_sha256") != EXPECTED_DATASET_SHA256 or c.get("metadata", {}).get("split_sha256") != EXPECTED_SPLIT_SHA256:
        raise BundleError("P3-008C aggregate does not use the frozen dataset and split")
    if (b.get("selected_policy") != "constant_ate" or b.get("re_evaluation", {}).get("model_fit_calls") != 0
            or b.get("input", {}).get("test_outcomes_accessed") is not False
            or b.get("population", {}).get("test_outcomes_accessed") is not False):
        raise BundleError("P3-008B selection or no-refit provenance did not match the synthesis")
    if c.get("metadata", {}).get("model_fit_calls") != 0 or c.get("metadata", {}).get("model_selection_performed") is not False or c.get("metadata", {}).get("candidate_diagnostics_run") is not False:
        raise BundleError("P3-008C must remain a no-fit, no-selection locked evaluation")
    if c.get("protocol", {}).get("secondary_holm_tests") != 8 or c.get("protocol", {}).get("primary_outcome") != "visit":
        raise BundleError("P3-008C protocol fields differ from the committed report")

    arms = [
        {"label": "Men's email", "assigned": int(arm_counts["Mens E-Mail"])},
        {"label": "Women's email", "assigned": int(arm_counts["Womens E-Mail"])},
        {"label": "No email", "assigned": int(arm_counts["No E-Mail"])},
    ]
    split_labels = {"train": "Training", "development": "Development", "test": "Locked test"}
    partition_sizes = {split_labels[split]: sum(row.values()) for split, row in split_counts.items()}
    primary_data = {
        "contrast": "Men's email assignment vs no email assignment",
        "outcome": "Website visit during the original two-week window",
        "n_treated": int(primary["n_treated"]),
        "events_treated": int(primary["events_treated"]),
        "rate_treated": _finite(primary["rate_treated"], "primary.rate_treated"),
        "n_control": int(primary["n_control"]),
        "events_control": int(primary["events_control"]),
        "rate_control": _finite(primary["rate_control"], "primary.rate_control"),
        "risk_difference_pp": _finite(primary["risk_difference_pp"], "primary.risk_difference_pp"),
        "ci95_low_pp": _finite(primary["ci95_low_pp"], "primary.ci95_low_pp"),
        "ci95_high_pp": _finite(primary["ci95_high_pp"], "primary.ci95_high_pp"),
        "exact_two_sided_randomization_p": _finite(primary["exact_two_sided_randomization_p"], "primary.p"),
        "additional_visits_per_1000": _finite(primary["additional_events_per_1000"], "primary.additional_per_1000"),
        "ci_method": primary["ci_method"],
        "test_method": primary["test_method"],
    }
    secondary_visits = []
    for result in secondary_source:
        if result.get("outcome") != "visit":
            continue
        label_map = {
            "Womens E-Mail vs No E-Mail": "Women's email vs no email",
            "Mens E-Mail vs Womens E-Mail": "Men's email vs Women's email",
        }
        contrast = label_map.get(result.get("contrast"))
        if contrast is None:
            continue
        secondary_visits.append({
            "contrast": contrast,
            "n_treated": int(result["n_treated"]),
            "events_treated": int(result["events_treated"]),
            "rate_treated": _finite(result["rate_treated"], f"{contrast}.rate_treated"),
            "n_control": int(result["n_control"]),
            "events_control": int(result["events_control"]),
            "rate_control": _finite(result["rate_control"], f"{contrast}.rate_control"),
            "risk_difference_pp": _finite(result["risk_difference_pp"], f"{contrast}.risk_difference_pp"),
            "ci95_low_pp": _finite(result["ci95_low_pp"], f"{contrast}.ci95_low_pp"),
            "ci95_high_pp": _finite(result["ci95_high_pp"], f"{contrast}.ci95_high_pp"),
            "holm_adjusted_p": _finite(result["holm_adjusted_p"], f"{contrast}.holm_adjusted_p"),
        })
    if len(secondary_visits) != 2:
        raise BundleError("P3-008C aggregate must contain both predeclared secondary website-visit comparisons")

    display_names = {
        "constant_ate": ("Seeded constant-ATE draw", "Reference baseline", "The selected constant-effect score produces random tie-breaking; this is one seeded draw."),
        "history_recency": ("Historical behavior", "Historical benchmark", "Ranks prior history and recency; this is not a CATE estimator."),
        "t_logistic": ("Logistic T-learner", "Logistic", "Separate logistic outcome models for treatment and control."),
        "s_logistic": ("Logistic S-learner", "Logistic", "One logistic outcome model with assignment as an input."),
        "x_logistic": ("Logistic X-learner", "Logistic", "Logistic outcome models with an X-learner effect stage."),
        "dr_logistic": ("Logistic DR-learner", "Logistic", "Cross-fitted doubly robust learner with logistic nuisance models."),
        "t_hgb": ("HGB T-learner", "HistGradientBoosting", "Separate HGB outcome models for treatment and control."),
        "s_hgb": ("HGB S-learner", "HistGradientBoosting", "One HGB outcome model with assignment as an input."),
        "x_hgb": ("HGB X-learner", "HistGradientBoosting", "HGB outcome models with an X-learner effect stage."),
        "dr_hgb": ("HGB DR-learner", "HistGradientBoosting", "Cross-fitted doubly robust learner with HGB nuisance models."),
        "t_xgboost_optional": ("XGBoost T-learner (supplementary)", "Supplementary XGBoost", "Supplementary descriptive model; not promotion-eligible."),
    }
    development_comparisons = []
    for item in dev_comparisons:
        key = item.get("candidate")
        if key not in display_names:
            raise BundleError(f"Unexpected P3-008B expected-random comparison: {key}")
        label, family, note = display_names[key]
        development_comparisons.append({
            "candidate": key,
            "label": label,
            "family": family,
            "description": note,
            "delta_visits_per_1000": _finite(item["delta_point_per_1000"], f"{key}.delta"),
            "ci95_low": _finite(item["ci95_low"], f"{key}.ci95_low"),
            "ci95_high": _finite(item["ci95_high"], f"{key}.ci95_high"),
            "formal_promotion_candidate": bool(item["formal_promotion_candidate"]),
        })

    expected_random_20 = expected_random["increment_per_1000"]
    policy = {
        "budget": _finite(expected_random["budget"], "expected_random.budget"),
        "increment_visits_per_1000": _finite(expected_random["increment_per_1000"], "expected_random.increment"),
        "ci95_low_per_1000": _finite(expected_random["ci95_low_per_1000"], "expected_random.ci_low"),
        "ci95_high_per_1000": _finite(expected_random["ci95_high_per_1000"], "expected_random.ci_high"),
    }
    if len(dev_comparisons) != 11:
        raise BundleError("P3-008B expected-random development comparison table has an unexpected row count")
    if not all(item["ci95_low"] < 0 < item["ci95_high"] for item in development_comparisons):
        raise BundleError("Expected-random development comparison intervals should include zero")

    synthesis = {
        "average_assignment_effect": "The locked randomized test supports an average increase in two-week website visits for assignment to this historical Men's email campaign.",
        "individual_response": "Development CATE models did not establish reliable person-level treatment-effect ranking; CATE scores are predictions, not observed individual causal effects.",
        "targeting_policy": "No personalised model established reliable superiority over expected random targeting at the 20% development budget; constant ATE / expected random targeting remained the research reference.",
        "heterogeneity": "No uplift improvement was demonstrated; this is not proof that treatment effects are homogeneous.",
        "transport": "Hillstrom is a separate experimental population. Its effects and uplift predictions do not directly apply to UCI Online Retail II customers or current campaigns.",
    }
    data = {
        "design": {
            "dataset_name": "MineThatData E-Mail Analytics and Data Mining Challenge (Hillstrom, 2008)",
            "observations": 64000,
            "arms": arms,
            "outcome_window": "Two weeks after assignment",
            "assignment_interpretation": "Randomized assignment-based intent-to-treat; delivery, opening and reading were not observed.",
            "partition_sizes": partition_sizes,
            "primary_pairwise_partition_sizes": {"Training": int(dev_input["training_n_pairwise"]), "Development": int(dev_input["development_n_pairwise"]), "Locked test": int(primary_data["n_treated"] + primary_data["n_control"])},
            "separate_from_uci": True,
        },
        "primary": primary_data,
        "secondary_visits": secondary_visits,
        "secondary_other_outcomes_note": "The predeclared secondary conversion and spend comparisons were inconclusive after Holm adjustment; this does not establish zero effect.",
        "development": {
            "eligible_rows": int(dev_pop["development_n"]),
            "training_pairwise_rows": int(dev_pop["train_n"]),
            "budget": 0.20,
            "selected_rows_at_budget": int(b["development_metrics"]["constant_ate"]["policies_per_1000"]["20%"]["selected_n"]),
            "expected_random_visits_per_1000": _finite(b["expected_random_reference"]["budgets"]["20%"]["expected_random_increment_per_1000"], "development.random_20"),
            "selected_reference": b["selected_policy"],
            "locked_test_candidate_diagnostics_run": c["metadata"]["candidate_diagnostics_run"],
            "locked_test_model_fit_calls": c["metadata"]["model_fit_calls"],
            "comparisons": development_comparisons,
            "evidence_label": "Exploratory development — CATE and targeting-policy evaluation",
            "outcome_unit": "Incremental website visits per 1,000 pairwise-eligible experiment rows, relative to expected random targeting at the same 20% budget.",
        },
        "test_policy": policy,
        "interpretation": synthesis,
        "evidence": {
            "design": "Historical description",
            "primary": "Confirmatory randomised evidence — locked test",
            "secondary": "Secondary randomised — Holm-adjusted comparisons",
            "development": "Exploratory development — CATE and targeting-policy evaluation",
        },
        "provenance": {
            "sources": provenance,
            "dataset_sha256": EXPECTED_DATASET_SHA256,
            "split_sha256": EXPECTED_SPLIT_SHA256,
        },
    }
    return data


def _validate_data(data: Any) -> None:
    required = {"design", "primary", "secondary_visits", "secondary_other_outcomes_note", "development", "test_policy", "interpretation", "evidence", "provenance"}
    if not isinstance(data, dict) or set(data) != required:
        raise BundleError("causal bundle data has invalid top-level schema")
    serialized = json.dumps(data, ensure_ascii=True, allow_nan=False).lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in serialized:
            raise BundleError(f"causal bundle contains prohibited private marker: {marker}")
    design, primary, dev = data["design"], data["primary"], data["development"]
    if design["observations"] != 64000 or sum(arm["assigned"] for arm in design["arms"]) != 64000:
        raise BundleError("experiment arm counts do not reconcile to 64,000 observations")
    if design["partition_sizes"] != {"Training": 38400, "Development": 12800, "Locked test": 12800}:
        raise BundleError("frozen 60/20/20 partition sizes do not reconcile")
    if primary["n_treated"] != 4262 or primary["n_control"] != 4261 or primary["events_treated"] != 802 or primary["events_control"] != 454:
        raise BundleError("primary locked-test arm counts differ from the reviewed result")
    effect = primary["rate_treated"] - primary["rate_control"]
    if abs(effect * 100 - primary["risk_difference_pp"]) > 1e-10:
        raise BundleError("primary risk difference does not reconcile to the arm rates")
    if not primary["ci95_low_pp"] < primary["risk_difference_pp"] < primary["ci95_high_pp"]:
        raise BundleError("primary confidence interval does not contain the effect estimate")
    if len(data["secondary_visits"]) != 2 or any(not row["ci95_low_pp"] < row["risk_difference_pp"] < row["ci95_high_pp"] for row in data["secondary_visits"]):
        raise BundleError("secondary visit comparisons are incomplete or have invalid intervals")
    if dev["eligible_rows"] != 8522 or dev["budget"] != 0.20 or len(dev["comparisons"]) != 11:
        raise BundleError("development policy-value population or budget is invalid")
    if any(not row["ci95_low"] < 0 < row["ci95_high"] for row in dev["comparisons"]):
        raise BundleError("a development expected-random comparison interval does not include zero")
    if dev["selected_reference"] != "constant_ate" or dev["locked_test_candidate_diagnostics_run"] is not False or dev["locked_test_model_fit_calls"] != 0:
        raise BundleError("constant ATE must remain the selected research reference")
    if data["evidence"]["primary"] != "Confirmatory randomised evidence — locked test" or data["evidence"]["secondary"] != "Secondary randomised — Holm-adjusted comparisons":
        raise BundleError("causal evidence classifications are invalid")
    sources = data["provenance"]["sources"]
    if set(sources) != {"p3_008a", "p3_008b", "p3_008c", "p3_008d"}:
        raise BundleError("causal bundle source provenance is incomplete")
    for key in ("p3_008a", "p3_008b", "p3_008c"):
        if sources[key]["sha256_raw_file"] != SOURCES[key]["sha256"] or sources[key]["source_file"] != f"source_data/hillstrom/{SOURCES[key]['path']}":
            raise BundleError(f"{key} fixed source provenance mismatch")
    if sources["p3_008d"].get("sha256_report") != EXPECTED_P3_008D_REPORT_SHA256:
        raise BundleError("P3-008D synthesis report provenance mismatch")


def build_bundle(source_root: Path = PRIVATE_ROOT) -> dict[str, Any]:
    aggregates, provenance = _read_sources(Path(source_root))
    data = _project(aggregates, provenance)
    _validate_data(data)
    return {
        "bundle_name": "commercial_retention_p3_causal_evidence_aggregate",
        "schema_version": SCHEMA_VERSION,
        "data": data,
        "content_sha256": _canonical_hash(data),
    }


def validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict) or set(bundle) != {"bundle_name", "schema_version", "data", "content_sha256"}:
        raise BundleError("causal bundle must have approved top-level fields")
    if bundle["bundle_name"] != "commercial_retention_p3_causal_evidence_aggregate" or bundle["schema_version"] != SCHEMA_VERSION:
        raise BundleError("causal bundle name or schema version is unsupported")
    actual = _canonical_hash(bundle["data"])
    if bundle["content_sha256"] != actual:
        raise BundleError("causal bundle content SHA-256 does not match its data")
    if EXPECTED_CONTENT_SHA256 and actual != EXPECTED_CONTENT_SHA256:
        raise BundleError("causal bundle content SHA-256 differs from approved application pin")
    _validate_data(bundle["data"])
    return bundle


def load_bundle(path: Path = DEFAULT_BUNDLE) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise BundleError(f"causal evidence bundle not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"causal evidence bundle is not valid JSON: {exc}") from None
    return validate_bundle(value)


def write_bundle(source_root: Path = PRIVATE_ROOT, output: Path = DEFAULT_BUNDLE) -> dict[str, Any]:
    bundle = build_bundle(source_root)
    validate_bundle(bundle)
    Path(output).write_text(json.dumps(bundle, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="rebuild the aggregate-only causal evidence bundle")
    args = parser.parse_args()
    value = write_bundle() if args.build else load_bundle()
    print(json.dumps({"bundle": str(DEFAULT_BUNDLE), "content_sha256": value["content_sha256"]}, indent=2))


if __name__ == "__main__":
    main()

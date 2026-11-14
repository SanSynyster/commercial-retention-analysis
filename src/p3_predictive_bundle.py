"""Build and validate the aggregate-only P3 predictive research app bundle.

Private aggregate sources are addressed by fixed paths. The committed bundle is
an allowlisted projection; source metadata and row-level artifacts are never
copied wholesale.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "app_data/p3_predictive_v1.json"
PRIVATE_ROOT = ROOT.parent / "source_data"

# SHA-256 values are raw bytes of the named aggregate JSON files. P3-002's
# digest is recorded directly in its frozen report. P3-003/004/005 digests are
# pinned from each report-cited aggregate's sibling manifest and independently
# verified against the raw aggregate bytes at build time.
SOURCES = {
    "p3_002": {
        "path": "uci_online_retail_ii/p3_002_outputs/p3_002_aggregate_results.json",
        "manifest": "uci_online_retail_ii/p3_002_outputs/p3_002_manifest.json",
        "sha256": "f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb",
        "manifest_declares_sha": True,
        "report": "docs/research/COMMERCIAL_DS_P3_002_ADVANCED_ML_BENCHMARK.md",
    },
    "p3_003": {
        "path": "uci_online_retail_ii/p3_003_outputs/p3_003_aggregate_results.json",
        "manifest": "uci_online_retail_ii/p3_003_outputs/p3_003_manifest.json",
        "sha256": "0d9280d4926b3819df02b33cb2c67d7decc560db57517ba8add65964e811d0d5",
        "manifest_declares_sha": True,
        "report": "docs/research/COMMERCIAL_DS_P3_003_XGBOOST_LIGHTGBM_BENCHMARK.md",
    },
    "p3_004": {
        "path": "uci_online_retail_ii/p3_004_outputs/p3_004_aggregate_results.json",
        "manifest": "uci_online_retail_ii/p3_004_outputs/p3_004_manifest.json",
        "sha256": "a04d7cd1919af7ae9304c4d2b3817597558680f7a3d82971de23fb2711919d47",
        "manifest_declares_sha": True,
        "report": "docs/research/COMMERCIAL_DS_P3_004_SHAP_EXPLAINABILITY.md",
    },
    "p3_005": {
        "path": "uci_online_retail_ii/p3_005_outputs/p3_005_aggregate_results.json",
        "manifest": "uci_online_retail_ii/p3_005_outputs/p3_005_manifest.json",
        "sha256": "d4fa81bbb8bae9c484917981fa15fc94591668f96d427926030fe25d29b72484",
        "manifest_declares_sha": True,
        "report": "docs/research/COMMERCIAL_DS_P3_005_CALIBRATION_UNCERTAINTY.md",
    },
}

BUNDLE_NAME = "commercial_retention_p3_predictive_aggregate"
BUNDLE_VERSION = "1.0.0"
SCHEMA_VERSION = 1
EXPECTED_CONTENT_SHA256 = "40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd"
MODEL_NAMES = ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting", "XGBoost", "LightGBM")
FORBIDDEN_KEYS = ("customer_id", "customerid", "invoice", "stockcode", "prediction_row", "feature_matrix", "private_path")


class BundleError(ValueError):
    """Malformed bundle or provenance mismatch."""


class SourceUnavailableError(FileNotFoundError):
    """One or more explicitly configured private source files are unavailable."""


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_source(name: str, source_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    spec = SOURCES[name]
    aggregate_path = source_root / spec["path"]
    manifest_path = source_root / spec["manifest"]
    if not aggregate_path.is_file() or not manifest_path.is_file():
        missing = [str(p) for p in (aggregate_path, manifest_path) if not p.is_file()]
        raise SourceUnavailableError(f"Missing required private {name} source file(s): {', '.join(missing)}")
    digest = raw_sha256(aggregate_path)
    if digest != spec["sha256"]:
        raise BundleError(f"{name} aggregate SHA-256 mismatch for explicit source {spec['path']}: {digest}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise BundleError(f"{name} source manifest must be a JSON object")
    if spec["manifest_declares_sha"]:
        if manifest.get("aggregate_sha256") != digest:
            raise BundleError(f"{name} manifest does not declare the verified aggregate SHA-256")
        expected_name = Path(spec["path"]).name
        manifest_name = manifest.get("aggregate")
        if manifest_name is not None and manifest_name != expected_name:
            raise BundleError(f"{name} manifest points to an unexpected aggregate filename")
    try:
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{name} aggregate is not valid UTF-8 JSON: {exc}") from None
    if not isinstance(aggregate, dict):
        raise BundleError(f"{name} aggregate must be a JSON object")
    provenance = {"report": spec["report"], "source_file": f"source_data/{spec['path']}", "sha256_raw_file": digest}
    return aggregate, provenance


def _number(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BundleError(f"{field} must be a finite number" if not nullable else f"{field} must be finite or null")
    return float(value)


def _extract_model(metrics: dict[str, Any], model: str, crm_key: str = "10") -> dict[str, Any]:
    m = metrics[model]
    crm = m.get("crm", {}).get(crm_key, {})
    return {
        "roc_auc": _number(m.get("roc_auc"), f"{model}.roc_auc"),
        "average_precision": _number(m.get("average_precision"), f"{model}.average_precision"),
        "brier_score": _number(m.get("brier_score"), f"{model}.brier_score", nullable=True),
        "log_loss": _number(m.get("log_loss"), f"{model}.log_loss", nullable=True),
        "top_decile_precision": _number(crm.get("precision"), f"{model}.top_decile_precision", nullable=True),
        "top_decile_capture": _number(crm.get("capture_recall"), f"{model}.top_decile_capture", nullable=True),
    }


def _ci_pair(value: dict[str, Any]) -> dict[str, Any]:
    return {"estimate": _number(value["point_difference"], "comparison.estimate"),
            "ci95": [_number(v, "comparison.ci95") for v in value["ci95"]]}


def _safe_bundle(p2: dict[str, Any], p3: dict[str, Any], p4: dict[str, Any], p5: dict[str, Any],
                 source_provenance: dict[str, dict[str, str]]) -> dict[str, Any]:
    dev = p3["development"]["pooled_oof"]
    hold = p3["exploratory_published_holdout"]["pooled"]
    model_metrics = {}
    selection = p2["search"]["selected"]
    for model in MODEL_NAMES:
        model_metrics[model] = {
            "development": _extract_model(dev["models"], model),
            "holdout": _extract_model(hold["models"], model),
            "selection_status": (
                "P3-002 retained development reference" if model == "Random Forest" else
                "frozen logistic baseline" if model == "Logistic C" else
                "operational ranking baseline" if model == "Frequency" else
                "configuration selected within family; RF remains reference" if model == "HistGradientBoosting" else
                "configuration selected for exploratory family comparison; not promoted over RF" if model in ("XGBoost", "LightGBM") else
                "evaluated"
            ),
        }
    model_metrics["Random Forest"]["selected_configuration"] = selection["Random Forest"]["parameters"]
    model_metrics["Random Forest"]["mean_fold_average_precision"] = _number(
        selection["Random Forest"]["mean_fold_average_precision"], "RF.mean_fold_average_precision")
    model_metrics["HistGradientBoosting"]["selected_configuration"] = selection["HistGradientBoosting"]["parameters"]
    model_metrics["HistGradientBoosting"]["mean_fold_average_precision"] = _number(
        selection["HistGradientBoosting"]["mean_fold_average_precision"], "HGB.mean_fold_average_precision")
    for model in ("XGBoost", "LightGBM"):
        sel = p3["selection"]["selected"][model]
        model_metrics[model]["selected_configuration"] = sel["parameters"]
        model_metrics[model]["mean_fold_average_precision"] = _number(sel["mean_fold_average_precision"], f"{model}.mean_fold_average_precision")

    comparisons: dict[str, Any] = {}
    for name, value in p2["development_ranking_bootstrap"]["comparisons"].items():
        comparisons[name] = {metric: _ci_pair(row) for metric, row in value.items() if metric in ("roc_auc", "average_precision")}
    p3_comparisons = p3["development"]["ranking_bootstrap_vs_random_forest"]["comparisons"]
    for name, value in p3_comparisons.items():
        comparisons[name] = {metric: _ci_pair(row) for metric, row in value.items() if metric in ("roc_auc", "average_precision")}
    holdout_comparisons = p2["exploratory_ranking_bootstrap"]["comparisons"]
    for name, value in holdout_comparisons.items():
        comparisons[f"Exploratory holdout: {name}"] = {
            metric: _ci_pair(row) for metric, row in value.items() if metric in ("roc_auc", "average_precision")
        }

    overall = p4["development"]["overall_importance"]
    dev_periods = p4["development"]["period_importance"]
    hold_periods = p4["exploratory_holdout"]["month_importance"]
    shap = {
        "output": "class-1 purchase probability contribution",
        "method": "Interventional TreeExplainer; fold-specific training-only 100-row background",
        "explained_rows_per_development_fold": 1000,
        "overall_development": [
            {"feature": r["feature"], "mean_abs": _number(r["mean_abs_shap_probability"], "SHAP.mean_abs"),
             "mean_signed": _number(r["mean_signed_shap_probability"], "SHAP.mean_signed")}
            for r in overall
        ],
        "development_by_period": [
            {"period": period["period"], "n_explained": int(period["n_explained"]),
             "features": [{"feature": f["feature"], "mean_abs": _number(f["mean_abs_shap_probability"], "SHAP.period.mean_abs")}
                          for f in period["importance"]]}
            for period in dev_periods
        ],
        "exploratory_holdout_by_month": [
            {"period": period["period"], "features": [
                {"feature": f["feature"], "mean_abs": _number(f["mean_abs_shap_probability"], "SHAP.holdout.mean_abs")}
                for f in period["importance"]]}
            for period in hold_periods
        ],
        "rank_stability": [{"period_a": x["period_a"], "period_b": x["period_b"],
                            "spearman": _number(x["spearman_rank_correlation"], "SHAP.spearman")}
                           for x in p4["development"]["temporal_stability"]["pairwise_period_rank_similarity"]],
        "correlated_groups": p4["development"]["group_contribution_summary"],
        "correlation_limit": "Correlated predictors can share attribution; SHAP is predictive attribution, not causal importance.",
    }

    cal_models = p5["development_evaluation"]["models"]
    rf_uncal = cal_models["Random Forest|uncalibrated"]
    rf_intercept = cal_models["Random Forest|intercept_only"]
    ci = p5["development_evaluation"]["paired_customer_bootstrap"]["Random Forest"]["comparisons"]["intercept_only"]
    calibration = {
        "reference": "uncalibrated Random Forest",
        "provisional_candidate": "intercept-only recalibration",
        "deployment_status": "not selected for deployment; uncalibrated RF remains reference",
        "development": {
            "uncalibrated": {k: _number(rf_uncal["pooled"][src], f"cal.uncal.{k}") for k, src in
                              (("brier", "brier"), ("log_loss", "log_loss"), ("roc_auc", "roc_auc"),
                               ("average_precision", "average_precision"), ("mean_predicted", "mean_predicted"),
                               ("observed_prevalence", "prevalence"))},
            "intercept_only": {k: _number(rf_intercept["pooled"][src], f"cal.intercept.{k}") for k, src in
                               (("brier", "brier"), ("log_loss", "log_loss"), ("roc_auc", "roc_auc"),
                                ("average_precision", "average_precision"), ("mean_predicted", "mean_predicted"),
                                ("observed_prevalence", "prevalence"))},
            "paired_difference_intercept_minus_uncalibrated": {
                metric: {"estimate": _number(ci[metric]["delta_vs_uncalibrated"], f"cal.{metric}.delta"),
                         "ci95": [_number(v, f"cal.{metric}.ci") for v in ci[metric]["ci95"]]}
                for metric in ("brier", "log_loss")},
            "monthly": [{"month": month, "uncalibrated_brier": _number(rf_uncal["monthly"][month]["brier"], "monthly.brier"),
                         "intercept_only_brier": _number(rf_intercept["monthly"][month]["brier"], "monthly.brier"),
                         "uncalibrated_log_loss": _number(rf_uncal["monthly"][month]["log_loss"], "monthly.log_loss"),
                         "intercept_only_log_loss": _number(rf_intercept["monthly"][month]["log_loss"], "monthly.log_loss"),
                         "brier_difference": _number(rf_intercept["monthly"][month]["brier"] - rf_uncal["monthly"][month]["brier"], "monthly.delta")}
                        for month in ("2011-04", "2011-05", "2011-06")],
        },
        "exploratory_holdout": {
            "uncalibrated": p5["exploratory_published_holdout"]["models"]["Random Forest|uncalibrated"]["pooled"],
            "intercept_only": p5["exploratory_published_holdout"]["models"]["Random Forest|intercept_only"]["pooled"],
        },
        "interpretation": "Monotone intercept adjustment does not change within-month ranking; calibration gains are not uniform across validation months and are not prospective evidence.",
    }
    # Explicitly project the holdout diagnostics, avoiding private provenance,
    # fit logs, paths, and row-level explanation references.
    for key in ("uncalibrated", "intercept_only"):
        raw = calibration["exploratory_holdout"][key]
        calibration["exploratory_holdout"][key] = {
            name: _number(raw[src], f"holdout.calibration.{name}")
            for name, src in (("brier", "brier"), ("log_loss", "log_loss"), ("roc_auc", "roc_auc"),
                              ("average_precision", "average_precision"), ("mean_predicted", "mean_predicted"),
                              ("observed_prevalence", "prevalence"))
        }
    calibration["exploratory_holdout"]["monthly"] = []
    hold_cal = p5["exploratory_published_holdout"]["models"]
    for month in ("2011-07", "2011-08", "2011-09", "2011-10", "2011-11"):
        u = hold_cal["Random Forest|uncalibrated"]["monthly"][month]
        c = hold_cal["Random Forest|intercept_only"]["monthly"][month]
        calibration["exploratory_holdout"]["monthly"].append({
            "month": month, "uncalibrated_brier": _number(u["brier"], "holdout.monthly.brier"),
            "intercept_only_brier": _number(c["brier"], "holdout.monthly.brier"),
        })

    result = {
        "bundle_name": BUNDLE_NAME,
        "bundle_version": BUNDLE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "evidence": {
            "analysis_type": "Historical prediction",
            "development": "Development — used for model selection",
            "holdout": "Previously examined holdout — exploratory",
            "causal_status": "Predictive, not causal; no confirmatory randomised label applies to this page.",
        },
        "task": {
            "name": "M2 established-customer next-month purchase propensity",
            "outcome": "Any qualifying purchase in the next 30 days",
            "features": "Frozen 11 point-in-time features over the preceding 365 days",
            "development_period": "March–June 2011 expanding validation folds",
            "development_snapshots": int(dev["snapshots"]), "development_customers": int(dev["customers"]),
            "development_prevalence": _number(dev["prevalence"], "development.prevalence"),
            "holdout_period": "July–November 2011",
            "holdout_snapshots": int(hold["snapshots"]), "holdout_customers": int(hold["customers"]),
            "holdout_prevalence": _number(hold["prevalence"], "holdout.prevalence"),
        },
        "selection": {
            "reference_model": "Random Forest",
            "criterion": "Bounded configurations selected using mean average precision across the four development folds.",
            "decision": "Retain RF as the development reference; XGBoost and LightGBM did not meet the predeclared adoption criteria.",
            "uncertainty_note": "Tree-model differences are small; available paired intervals are conditional on fitted models and do not include selection or future-period uncertainty.",
        },
        "models": model_metrics,
        "comparisons": comparisons,
        "shap": shap,
        "calibration": calibration,
        "provenance": {"sources": source_provenance, "privacy": "Aggregate-safe metrics only; no customer rows, identifiers, or predictions included."},
    }
    result["content_sha256"] = _canonical_hash(result)
    return result


def validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise BundleError("P3 predictive bundle must be a JSON object")
    expected = {"bundle_name", "bundle_version", "schema_version", "evidence", "task", "selection",
                "models", "comparisons", "shap", "calibration", "provenance", "content_sha256"}
    if set(bundle) != expected:
        raise BundleError("P3 predictive bundle has missing or unexpected fields")
    if (bundle["bundle_name"], bundle["bundle_version"], bundle["schema_version"]) != (BUNDLE_NAME, BUNDLE_VERSION, SCHEMA_VERSION):
        raise BundleError("Unsupported P3 predictive bundle identity/version")
    supplied = bundle["content_sha256"]
    if supplied != EXPECTED_CONTENT_SHA256:
        raise BundleError("P3 predictive bundle differs from the expected committed content pin")
    copy = dict(bundle)
    del copy["content_sha256"]
    if supplied != _canonical_hash(copy):
        raise BundleError("P3 predictive bundle content checksum mismatch")
    if bundle["evidence"].get("analysis_type") != "Historical prediction":
        raise BundleError("Predictive page must use the Historical prediction evidence label")
    if bundle["evidence"].get("development") != "Development — used for model selection":
        raise BundleError("Development evidence label is incorrect")
    if bundle["evidence"].get("holdout") != "Previously examined holdout — exploratory":
        raise BundleError("Holdout evidence label is incorrect")
    if len(bundle["models"]) != len(MODEL_NAMES) or set(bundle["models"]) != set(MODEL_NAMES):
        raise BundleError("P3 model set is incomplete or unexpected")
    task = bundle["task"]
    for field in ("development_snapshots", "development_customers", "holdout_snapshots", "holdout_customers"):
        if isinstance(task.get(field), bool) or not isinstance(task.get(field), int) or task[field] <= 0:
            raise BundleError(f"task.{field} must be a positive integer")
    for field in ("development_prevalence", "holdout_prevalence"):
        value = _number(task.get(field), f"task.{field}")
        if not 0 <= value <= 1:
            raise BundleError(f"task.{field} must be a probability")
    for model, sections in bundle["models"].items():
        if not isinstance(sections, dict) or not {"development", "holdout", "selection_status"} <= set(sections):
            raise BundleError(f"Malformed model entry: {model}")
        for period in ("development", "holdout"):
            row = sections[period]
            for metric in ("roc_auc", "average_precision", "brier_score", "log_loss", "top_decile_precision", "top_decile_capture"):
                if metric not in row:
                    raise BundleError(f"Missing {period} {metric} for {model}")
                _number(row[metric], f"{model}.{period}.{metric}", nullable=True)
    for record in bundle["shap"]["overall_development"]:
        if not isinstance(record.get("feature"), str):
            raise BundleError("SHAP feature name must be text")
        _number(record.get("mean_abs"), "SHAP.mean_abs")
        _number(record.get("mean_signed"), "SHAP.mean_signed")
    if len(bundle["shap"]["overall_development"]) != 11 or len(bundle["shap"]["development_by_period"]) != 4:
        raise BundleError("SHAP global/fold feature summary has an unexpected population shape")
    if len(bundle["shap"]["exploratory_holdout_by_month"]) != 5 or not isinstance(bundle["shap"]["correlated_groups"], list):
        raise BundleError("SHAP holdout/correlation summary has an unexpected shape")
    for period in bundle["shap"]["development_by_period"]:
        for feature in period["features"]:
            _number(feature["mean_abs"], "SHAP.period.mean_abs")
    for comparison, metrics in bundle["comparisons"].items():
        if not isinstance(comparison, str) or not isinstance(metrics, dict) or not metrics:
            raise BundleError("Malformed paired ranking comparison")
        for metric, result in metrics.items():
            if metric not in ("roc_auc", "average_precision") or not isinstance(result, dict) or set(result) != {"estimate", "ci95"}:
                raise BundleError("Malformed paired ranking interval")
            _number(result["estimate"], "comparison.estimate")
            if not isinstance(result["ci95"], list) or len(result["ci95"]) != 2:
                raise BundleError("Comparison confidence interval must contain two bounds")
            for bound in result["ci95"]:
                _number(bound, "comparison.ci95")
    for metric in ("uncalibrated", "intercept_only"):
        row = bundle["calibration"]["development"][metric]
        for name in ("brier", "log_loss", "roc_auc", "average_precision", "mean_predicted", "observed_prevalence"):
            _number(row[name], f"calibration.{metric}.{name}")
    if bundle["calibration"].get("deployment_status") != "not selected for deployment; uncalibrated RF remains reference":
        raise BundleError("Calibration deployment status is not approved")
    for metric in ("brier", "log_loss"):
        interval = bundle["calibration"]["development"]["paired_difference_intercept_minus_uncalibrated"][metric]
        if not isinstance(interval, dict) or set(interval) != {"estimate", "ci95"} or not isinstance(interval["ci95"], list) or len(interval["ci95"]) != 2:
            raise BundleError(f"Malformed calibration {metric} interval")
        _number(interval["estimate"], f"calibration.{metric}.estimate")
        for bound in interval["ci95"]:
            _number(bound, f"calibration.{metric}.ci95")
    if len(bundle["calibration"]["development"]["monthly"]) != 3 or len(bundle["calibration"]["exploratory_holdout"]["monthly"]) != 5:
        raise BundleError("Calibration period summaries have an unexpected shape")
    sources = bundle["provenance"].get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        raise BundleError("Source provenance list is incomplete")
    for source_name, source in sources.items():
        if not isinstance(source, dict) or set(source) != {"report", "source_file", "sha256_raw_file"}:
            raise BundleError(f"Malformed source provenance for {source_name}")
        if len(source["sha256_raw_file"]) != 64 or any(c not in "0123456789abcdef" for c in source["sha256_raw_file"]):
            raise BundleError(f"Malformed SHA-256 digest for {source_name}")
    _reject_private_or_row_data(bundle)
    return bundle


def _reject_private_or_row_data(value: Any, where: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in FORBIDDEN_KEYS):
                raise BundleError(f"Prohibited row-level/private field {where}.{key}")
            _reject_private_or_row_data(item, f"{where}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _reject_private_or_row_data(item, f"{where}[{i}]")
    elif isinstance(value, str):
        if item_is_private_path(value):
            raise BundleError(f"Private or absolute path found at {where}")
    elif isinstance(value, float) and not math.isfinite(value):
        raise BundleError(f"Non-finite numeric value at {where}")
    elif value is not None and not isinstance(value, (int, bool, float)):
        raise BundleError(f"Unsupported value type at {where}: {type(value).__name__}")


def item_is_private_path(value: str) -> bool:
    return value.startswith("/") or "/Users/" in value or "private/" in value or "customer_id" in value.lower()


def load_bundle(path: Path = DEFAULT_BUNDLE) -> dict[str, Any]:
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"P3 predictive bundle could not be loaded: {exc}") from None
    return validate_bundle(bundle)


def build_bundle(source_root: Path = PRIVATE_ROOT) -> dict[str, Any]:
    loaded = {name: _load_source(name, source_root) for name in SOURCES}
    raw = {name: pair[0] for name, pair in loaded.items()}
    provenance = {name: pair[1] for name, pair in loaded.items()}
    return validate_bundle(_safe_bundle(raw["p3_002"], raw["p3_003"], raw["p3_004"], raw["p3_005"], provenance))


def write_bundle(bundle: dict[str, Any], path: Path = DEFAULT_BUNDLE) -> None:
    validate_bundle(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build app_data/p3_predictive_v1.json from explicitly pinned private sources")
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE, help="bundle output path (defaults to committed app_data bundle)")
    args = parser.parse_args()
    if args.build:
        bundle = build_bundle()
        write_bundle(bundle, args.output)
        print(f"Wrote validated aggregate P3 bundle: {args.output.name} ({bundle['content_sha256']})")
    else:
        bundle = load_bundle(args.output)
        print(f"Valid P3 predictive bundle: {bundle['bundle_name']} {bundle['bundle_version']}")


if __name__ == "__main__":
    main()

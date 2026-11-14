"""Build and validate the aggregate-only P3-007 segmentation app bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT.parent / "source_data"
DEFAULT_SOURCE_ROOT = PRIVATE_ROOT / "uci_online_retail_ii/p3_007_outputs"
DEFAULT_BUNDLE = ROOT / "app_data/p3_segmentation_v1.json"
SOURCE_AGGREGATE = "uci_online_retail_ii/p3_007_outputs/p3_007_aggregate_results.json"
SOURCE_MANIFEST = "uci_online_retail_ii/p3_007_outputs/p3_007_manifest.json"
EXPECTED_SOURCE_SHA256 = "53a7636b839e97cfc489cfa5688076edef3337abaf76b3bb326316b1a5ecf209"
EXPECTED_MANIFEST_SHA256 = "35bb459509ab58d4d41f519fa3374339b7717d0206412bdd75295aeedc94dea6"
EXPECTED_DATASET_SHA256 = "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8"
EXPECTED_CONTENT_SHA256 = "590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8"
SCHEMA_VERSION = 1
FORBIDDEN_KEYS = ("customer_id", "customerid", "prediction", "private_path", "customer_month_assignments", "parquet")
REPORT = "docs/research/COMMERCIAL_DS_P3_007_ADVANCED_SEGMENTATION.md"


class BundleError(ValueError):
    """Invalid bundle or source provenance."""


class SourceUnavailableError(FileNotFoundError):
    """An explicitly configured private source is absent."""


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any, field: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BundleError(f"{field} must be finite numeric data")
    if integer and (not isinstance(value, int) or value < 0):
        raise BundleError(f"{field} must be a non-negative integer")
    return value


def _source_files(source_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    aggregate_path = source_root / "p3_007_aggregate_results.json"
    manifest_path = source_root / "p3_007_manifest.json"
    missing = [str(path) for path in (aggregate_path, manifest_path) if not path.is_file()]
    if missing:
        raise SourceUnavailableError(f"Missing required P3-007 private aggregate source file(s): {', '.join(missing)}")
    aggregate_sha = raw_sha256(aggregate_path)
    manifest_sha = raw_sha256(manifest_path)
    if aggregate_sha != EXPECTED_SOURCE_SHA256:
        raise BundleError(f"P3-007 aggregate SHA-256 mismatch for explicit source: {aggregate_sha}")
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise BundleError(f"P3-007 manifest SHA-256 mismatch for explicit source: {manifest_sha}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"P3-007 source is not valid UTF-8 JSON: {exc}") from None
    if not isinstance(manifest, dict) or not isinstance(aggregate, dict):
        raise BundleError("P3-007 source aggregate and manifest must be JSON objects")
    if manifest.get("experiment") != "P3-007" or manifest.get("aggregate_sha256") != aggregate_sha:
        raise BundleError("P3-007 manifest does not declare the verified aggregate checksum")
    if (manifest.get("dataset_sha256") != EXPECTED_DATASET_SHA256 or manifest.get("reference_month") != "2011-03"
            or manifest.get("selected_algorithm") != "KMeans" or manifest.get("selected_k") != 3):
        raise BundleError("P3-007 manifest does not match the report-cited selected experiment")
    return aggregate, {
        "report": REPORT,
        "source_file": f"source_data/{SOURCE_AGGREGATE}",
        "sha256_raw_file": aggregate_sha,
        "manifest_file": f"source_data/{SOURCE_MANIFEST}",
        "sha256_manifest": manifest_sha,
        "dataset_sha256": EXPECTED_DATASET_SHA256,
    }


def _project(source: dict[str, Any], provenance: dict[str, str]) -> dict[str, Any]:
    try:
        cohort = source["cohort"]
        rfm_source = source["rfm_baseline"]
        rfm_rule = rfm_source["rule"]
        rfm_profiles = rfm_source["segments_reference_profiles"]
        clusters = source["reference_cluster_profiles"]["clusters"]
        selected = source["candidate_quality"]["KMeans"]["3"]
        outcomes = source["mature_30_day_outcome_profiles_descriptive_only"]["development_Apr-Jun"]
        ml_transition = source["temporal_transitions"]["through_exploratory_replay"]["adjacent_months"]
        rfm_transition = source["temporal_transitions"]["rfm_through_exploratory_replay"]["adjacent_months"]
    except (KeyError, TypeError) as exc:
        raise BundleError(f"P3-007 aggregate is missing required section: {exc}") from None
    if source.get("experiment") != "COMMERCIAL_DS_P3_007":
        raise BundleError("P3-007 aggregate experiment identifier is unexpected")
    cutpoints = {}
    for dimension, rule in rfm_rule["thresholds"].items():
        cutpoints[dimension] = {
            "original_scale": [math.expm1(x) for x in rule["thresholds_log1p"]],
            "reverse": bool(rule["reverse"]),
            "column": rule["column"],
        }
    outcome_periods = {"development_apr_jun": {}}
    for key in ("rfm_segment", "ml_segment"):
        source_key = "rfm_segment" if key == "rfm_segment" else "ml_segment"
        outcome_periods["development_apr_jun"][key] = {
            str(name): {
                field: _finite(row[field], f"outcomes.{key}.{name}.{field}")
                for field in ("n", "purchase_rate", "mean_future_gross_gbp", "mean_future_occasion_count_30d")
            }
            for name, row in outcomes[source_key].items()
        }
    data = {
        "cohort": {
            "reference_month": cohort["reference_month"],
            "reference_customers": cohort["reference_n"],
            "development_months": cohort["development_evaluation_months"],
            "development_snapshots": sum(cohort["monthly_counts"][m] for m in cohort["development_evaluation_months"]),
            "exploratory_months": cohort["exploratory_replay_months"],
            "exploratory_snapshots": sum(cohort["monthly_counts"][m] for m in cohort["exploratory_replay_months"]),
        },
        "rfm": {
            "score_definition": rfm_rule["score_definition"],
            "fit_month": rfm_rule["fit_month"],
            "cutpoints": cutpoints,
            "assignment_precedence": rfm_source["assignment_precedence"],
            "segment_descriptions": {
                "Champions": "R≥4, F≥4, M≥4",
                "At risk": "R≤2, F≥3",
                "Hibernating": "R≤2, F≤2",
                "Loyal": "R≥4, F≥3",
                "Potential": "R≥4, F≤2",
                "Big spenders": "M≥4 after higher-precedence rules",
                "Regular": "All remaining eligible customers",
            },
            "reference_profiles": rfm_profiles,
        },
        "kmeans": {
            "selection": {"algorithm": "KMeans", "k": 3, "criteria": source["model_selection"]["rule"],
                          "used_future_outcomes": source["model_selection"]["selection_used_future_outcomes"]},
            "quality": {
                field: selected[field] for field in ("silhouette_sampled", "davies_bouldin", "calinski_harabasz",
                    "minimum_cluster_share", "mean_seed_ari", "customer_bootstrap_ari_mean",
                    "customer_bootstrap_ari_p10_p90", "customer_bootstrap_repetitions")
            },
            "reference_profiles": clusters,
            "standardized_centroid_profiles": source["reference_cluster_profiles"]["standardized_centroid_profiles"],
        },
        "outcomes": outcome_periods,
        "within_rfm_cluster_variation": outcomes["within_rfm_cluster_variation"],
        "comparison": {
            "rfm_vs_kmeans_by_month": {
                month: {"adjusted_rand_ml_vs_rfm": values["adjusted_rand_ml_vs_rfm"],
                        "normalized_mutual_information_ml_vs_rfm": values["normalized_mutual_information_ml_vs_rfm"]}
                for month, values in source["rfm_comparison"]["by_month"].items()
            },
            "reference_ari": source["rfm_comparison"]["reference_adjusted_rand"],
            "reference_nmi": source["rfm_comparison"]["reference_normalized_mutual_information"],
            "kmeans_transitions": ml_transition,
            "rfm_transitions": rfm_transition,
            "incremental_value_conclusion": "Available evidence does not demonstrate meaningful incremental purchase discrimination beyond RFM. Reviewer-derived April–June AUC diagnostics are not included because they are absent from the verified aggregate source.",
        },
        "evidence": {
            "rfm": "Historical description",
            "purchase_comparison": "Development — retrospective evaluation",
            "kmeans": "Exploratory",
            "exploratory_replay": "Previously examined holdout — exploratory",
            "targeting": "Retrospective targeting",
        },
        "provenance": provenance,
    }
    return data


def _validate_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or set(data) != {"cohort", "rfm", "kmeans", "outcomes", "within_rfm_cluster_variation", "comparison", "evidence", "provenance"}:
        raise BundleError("bundle data has invalid top-level schema")
    text = json.dumps(data, ensure_ascii=True, allow_nan=False).lower()
    for marker in FORBIDDEN_KEYS:
        if marker in text:
            raise BundleError(f"bundle contains forbidden private marker: {marker}")
    if set(data["rfm"]["reference_profiles"]) != set(data["rfm"]["segment_descriptions"]):
        raise BundleError("RFM reference profiles and definitions do not match")
    if sum(row["n"] for row in data["rfm"]["reference_profiles"].values()) != data["cohort"]["reference_customers"]:
        raise BundleError("RFM reference segment counts do not reconcile to the March cohort")
    if set(data["kmeans"]["reference_profiles"]) != {"0", "1", "2"}:
        raise BundleError("selected K-Means reference profiles must contain clusters 0, 1 and 2")
    if sum(row["n"] for row in data["kmeans"]["reference_profiles"].values()) != data["cohort"]["reference_customers"]:
        raise BundleError("K-Means reference cluster counts do not reconcile to the March cohort")
    for groups in data["outcomes"]["development_apr_jun"].values():
        for row in groups.values():
            if not 0 <= row["purchase_rate"] <= 1 or row["n"] <= 0:
                raise BundleError("outcome profile has an invalid count or rate")
    for label in data["evidence"].values():
        if not isinstance(label, str) or not label:
            raise BundleError("evidence labels must be non-empty strings")


def build_bundle(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    source, provenance = _source_files(Path(source_root))
    data = _project(source, provenance)
    _validate_data(data)
    bundle = {"bundle_name": "commercial_retention_p3_segmentation_aggregate", "schema_version": SCHEMA_VERSION,
              "data": data, "content_sha256": _canonical_hash(data)}
    return bundle


def validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict) or set(bundle) != {"bundle_name", "schema_version", "data", "content_sha256"}:
        raise BundleError("bundle must be a JSON object with the approved top-level fields")
    if bundle["bundle_name"] != "commercial_retention_p3_segmentation_aggregate" or bundle["schema_version"] != SCHEMA_VERSION:
        raise BundleError("bundle name or schema version is not supported")
    actual = _canonical_hash(bundle["data"])
    if bundle["content_sha256"] != actual:
        raise BundleError("bundle content hash does not match its data")
    if EXPECTED_CONTENT_SHA256 and actual != EXPECTED_CONTENT_SHA256:
        raise BundleError("bundle content hash differs from the approved application pin")
    _validate_data(bundle["data"])
    provenance = bundle["data"]["provenance"]
    if (provenance.get("sha256_raw_file") != EXPECTED_SOURCE_SHA256
            or provenance.get("sha256_manifest") != EXPECTED_MANIFEST_SHA256
            or provenance.get("source_file") != f"source_data/{SOURCE_AGGREGATE}"
            or provenance.get("manifest_file") != f"source_data/{SOURCE_MANIFEST}"
            or provenance.get("dataset_sha256") != EXPECTED_DATASET_SHA256
            or provenance.get("report") != REPORT):
        raise BundleError("bundle source provenance does not match the explicit P3-007 sources")
    return bundle


def load_bundle(path: Path = DEFAULT_BUNDLE) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise BundleError(f"Segmentation bundle not found: {path}")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BundleError(f"Segmentation bundle could not be read: {exc}") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"Segmentation bundle is not valid JSON: {exc}") from None
    return validate_bundle(bundle)


def write_bundle(source_root: Path = DEFAULT_SOURCE_ROOT, output: Path = DEFAULT_BUNDLE) -> dict[str, Any]:
    bundle = build_bundle(source_root)
    validate_bundle(bundle)
    Path(output).write_text(json.dumps(bundle, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build the reviewed aggregate-only application bundle")
    args = parser.parse_args()
    bundle = write_bundle() if args.build else load_bundle()
    print(json.dumps({"bundle": str(DEFAULT_BUNDLE), "content_sha256": bundle["content_sha256"]}, indent=2))


if __name__ == "__main__":
    main()

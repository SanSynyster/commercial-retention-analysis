"""Exploratory, as-of sequential intercept calibration for M2 monthly models."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from day21_baseline import calibration_diagnostic  # noqa: E402
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402

EXPECTED_DATASET_SHA256 = "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8"
EXPECTED_SOURCE_MANIFEST_SHA256 = "3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13"
EXPECTED_PROTOCOL_SHA256 = "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4"
EXPECTED_PREDICTIONS_SHA256 = "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1"
EXPECTED_MODELS_SHA256 = "e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f"
EXPECTED_RUN_MANIFEST_SHA256 = "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a"
PROTOCOL_PATH = ROOT / "docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md"
CUSTOMER = "customer_id"
MONTH = "snapshot_month"
DECISION = "decision_time"
LABEL = "outcome_label"
MODEL_B = "probability_B_rfm"
MODEL_C = "probability_C_full_11"
EPSILON = 1e-6
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261112
TARGET_MONTHS = ("2011-09", "2011-10", "2011-11")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _model_probability(features: pd.DataFrame, model: dict[str, Any]) -> np.ndarray:
    names = tuple(model["features"])
    if tuple(features.columns) != names:
        raise ValueError("Model feature order differs from the frozen artifact.")
    preprocessing = model["preprocessing"]
    raw = features.to_numpy(dtype=float, na_value=np.nan, copy=True)
    logged = np.log1p(raw)
    medians = np.asarray(preprocessing["log_medians"], dtype=float)
    means = np.asarray(preprocessing["training_log_means"], dtype=float)
    scales = np.asarray(preprocessing["training_log_population_sd"], dtype=float)
    for col, median in enumerate(medians):
        missing = np.isnan(logged[:, col])
        logged[missing, col] = median
    standardized = (logged - means) / scales
    coefficient = np.asarray(model["coefficients_standardized_log1p"], dtype=float)
    return expit(float(model["intercept"]) + standardized @ coefficient)


def verify_and_join_inputs(
    dataset_path: Path, source_manifest_path: Path, prediction_path: Path,
    models_path: Path, run_manifest_path: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Verify frozen hashes and reconstruct saved B/C predictions without refitting."""
    paths = {
        "dataset": dataset_path,
        "source_manifest": source_manifest_path,
        "predictions": prediction_path,
        "models": models_path,
        "run_manifest": run_manifest_path,
    }
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    expected = {
        "dataset": EXPECTED_DATASET_SHA256,
        "source_manifest": EXPECTED_SOURCE_MANIFEST_SHA256,
        "predictions": EXPECTED_PREDICTIONS_SHA256,
        "models": EXPECTED_MODELS_SHA256,
        "run_manifest": EXPECTED_RUN_MANIFEST_SHA256,
    }
    if hashes != expected:
        raise ValueError(f"Frozen input hash mismatch: {hashes}")
    if sha256_file(PROTOCOL_PATH) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Frozen M2-007 protocol hash differs.")
    source_manifest = _read_json(source_manifest_path)
    run_manifest = _read_json(run_manifest_path)
    model_artifact = _read_json(models_path)
    if tuple(source_manifest.get("feature_columns", [])) != tuple(FEATURE_COLUMNS):
        raise ValueError("Source manifest feature order differs from the frozen feature list.")
    if tuple(run_manifest.get("feature_order", [])) != tuple(FEATURE_COLUMNS):
        raise ValueError("Baseline run feature order differs from the frozen feature list.")
    if model_artifact.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Saved model artifact points to an unexpected protocol.")
    if model_artifact.get("dataset_sha256") != EXPECTED_DATASET_SHA256 or model_artifact.get("manifest_sha256") != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise ValueError("Saved model artifact provenance differs from frozen inputs.")
    if tuple(model_artifact.get("feature_order", [])) != tuple(FEATURE_COLUMNS):
        raise ValueError("Saved model feature order differs from the frozen feature list.")

    cohort = pd.read_parquet(dataset_path)
    predictions = pd.read_parquet(prediction_path)
    for frame in (cohort, predictions):
        frame[DECISION] = pd.to_datetime(frame[DECISION])
    test = cohort.loc[cohort.evaluation_partition.eq("test")].copy()
    if len(test) != 21672 or test.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Test cohort count or customer-decision keys differ from baseline.")
    if not test.outcome_window_mature.all() or test[LABEL].isna().any():
        raise ValueError("Baseline test rows must have mature binary labels.")
    test[LABEL] = test[LABEL].astype(int)
    saved = predictions.copy()
    if len(saved) != 21672 or saved.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Saved prediction table has unexpected count or duplicate keys.")
    cols = [CUSTOMER, DECISION, LABEL, "probability_A_constant", MODEL_B, MODEL_C]
    joined = test.merge(saved[cols], on=[CUSTOMER, DECISION], how="inner", validate="one_to_one", suffixes=("", "_saved"))
    if len(joined) != len(test) or not joined[LABEL].eq(joined[f"{LABEL}_saved"]).all():
        raise ValueError("Saved predictions do not align to the frozen customer-month labels.")
    if not joined.outcome_window_end_exclusive.eq(joined[DECISION] + pd.Timedelta(days=30)).all():
        raise ValueError("Outcome maturity timestamp differs from the frozen 30-day horizon.")
    for name, key in ((MODEL_B, "model_B"), (MODEL_C, "model_C")):
        model = model_artifact[key]
        reconstructed = _model_probability(joined.loc[:, list(model["features"])], model)
        if not np.allclose(reconstructed, joined[name].to_numpy(float), rtol=1e-11, atol=1e-12):
            raise ValueError(f"Reconstructed {name} predictions differ from frozen predictions.")
    prevalence = float(joined[LABEL].mean())
    if not np.allclose(joined["probability_A_constant"], 4573 / 25647, rtol=0, atol=1e-15):
        raise ValueError("Constant comparator differs from frozen training prevalence.")
    if joined.groupby(MONTH).size().to_dict() != {
        "2011-07": 4314, "2011-08": 4326, "2011-09": 4324,
        "2011-10": 4364, "2011-11": 4344,
    }:
        raise ValueError("Frozen test month counts differ.")
    if int(joined[LABEL].sum()) != 5092 or not np.isclose(prevalence, 5092 / 21672):
        raise ValueError("Frozen test label totals differ.")
    if not np.isclose(float(model_artifact["model_A"]["probability"]), 4573 / 25647, rtol=0, atol=1e-15):
        raise ValueError("Saved constant comparator differs from the training prevalence.")
    frozen_metrics = {
        MODEL_B: (0.7599526256091772, 0.5483029689, 0.1496769166),
        MODEL_C: (0.7659859786206419, 0.5659489004, 0.1474375620),
    }
    for name, expected_metrics in frozen_metrics.items():
        actual_metrics = (
            float(roc_auc_score(joined[LABEL], joined[name])),
            float(average_precision_score(joined[LABEL], joined[name])),
            float(brier_score_loss(joined[LABEL], joined[name])),
        )
        if not np.allclose(actual_metrics, expected_metrics, rtol=0, atol=1e-9):
            raise ValueError(f"Saved {name} metrics do not reproduce the M2-008 report.")
    return joined.sort_values([CUSTOMER, DECISION]).reset_index(drop=True), hashes


def historically_available_rows(frame: pd.DataFrame, target_decision: pd.Timestamp) -> pd.DataFrame:
    """Rows with complete labels matured strictly before a target decision."""
    target = pd.Timestamp(target_decision)
    end = pd.to_datetime(frame["outcome_window_end_exclusive"])
    decision = pd.to_datetime(frame[DECISION])
    valid = (
        frame["evaluation_partition"].eq("test")
        & frame["outcome_window_mature"].eq(True)
        & frame["outcome_coverage_status"].eq("complete")
        & frame[LABEL].isin([0, 1])
        & decision.lt(target)
        & end.lt(target)
    )
    return frame.loc[valid].copy()


def fit_intercept_adjustment(
    y_true: Iterable[int], probability: Iterable[float],
    sample_weight: Iterable[float] | None = None,
    *, epsilon: float = EPSILON,
) -> float:
    """Fit delta by MLE in logistic(logit(p) + delta), with slope fixed at 1."""
    y = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(probability), dtype=float)
    w = np.ones(len(y), dtype=float) if sample_weight is None else np.asarray(list(sample_weight), dtype=float)
    if len(y) == 0 or len(p) != len(y) or len(w) != len(y):
        raise ValueError("Calibration arrays must be nonempty and aligned.")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or not np.isfinite(w).all():
        raise ValueError("Calibration labels, probabilities or weights are invalid.")
    if (p < 0).any() or (p > 1).any() or (w < 0).any() or w.sum() <= 0:
        raise ValueError("Probabilities must be in [0,1] and weights nonnegative with positive sum.")
    if np.unique(y[w > 0]).size < 2:
        raise ValueError("Calibration pool must contain both outcome classes.")
    x = logit(np.clip(p, epsilon, 1 - epsilon))

    def score(delta: float) -> float:
        return float(np.dot(w, expit(x + delta) - y))

    low, high = -10.0, 10.0
    while score(low) >= 0 and low > -100:
        low *= 2
    while score(high) <= 0 and high < 100:
        high *= 2
    delta = float(brentq(score, low, high, xtol=1e-12, rtol=1e-12, maxiter=200))
    if not np.isfinite(delta):
        raise ValueError("Calibration intercept is not finite.")
    return delta


def apply_intercept_adjustment(probability: Iterable[float], delta: float, *, epsilon: float = EPSILON) -> np.ndarray:
    p = np.asarray(list(probability), dtype=float)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any() or not np.isfinite(delta):
        raise ValueError("Invalid probability or intercept adjustment.")
    return expit(logit(np.clip(p, epsilon, 1 - epsilon)) + float(delta))


def _weighted_metrics(y: np.ndarray, p: np.ndarray, weights: np.ndarray | None = None) -> dict[str, Any]:
    if weights is None:
        weights = np.ones(len(y), dtype=float)
    active = weights > 0
    ya, pa, wa = y[active], p[active], weights[active]
    prevalence = float(np.average(ya, weights=wa))
    return {
        "snapshots_weighted": float(wa.sum()),
        "positive_prevalence": prevalence,
        "mean_predicted_probability": float(np.average(pa, weights=wa)),
        "calibration_in_the_large_risk_difference": prevalence - float(np.average(pa, weights=wa)),
        "roc_auc": float(roc_auc_score(ya, pa, sample_weight=wa)) if np.unique(ya).size == 2 else None,
        "average_precision": float(average_precision_score(ya, pa, sample_weight=wa)),
        "brier_score": float(np.average((ya - pa) ** 2, weights=wa)),
        "calibration_intercept_slope": calibration_diagnostic(ya.astype(int), pa),
    }


def targeting_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    result = {}
    for capacity in (0.05, 0.10, 0.20):
        nominal = int(np.ceil(capacity * len(y)))
        threshold = np.sort(p)[::-1][nominal - 1]
        selected = p >= threshold
        precision = float(y[selected].mean())
        result[f"{int(capacity * 100)}pct"] = {
            "nominal_rows": nominal,
            "selected_rows_including_boundary_ties": int(selected.sum()),
            "actual_capacity": float(selected.mean()),
            "precision": precision,
            "lift_over_month_prevalence": precision / float(y.mean()),
        }
    return result


def sequential_calibration(frame: pd.DataFrame, *, weight_column: str | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Fit each target month's intercept from strictly prior mature test labels."""
    result = frame.copy()
    result["probability_C_sequential_adjusted"] = np.nan
    records: list[dict[str, Any]] = []
    for month in TARGET_MONTHS:
        target = pd.Timestamp(f"{month}-01 00:00:00")
        pool = historically_available_rows(result, target)
        evaluation = result.loc[result[MONTH].eq(month) & result["evaluation_partition"].eq("test")].copy()
        if evaluation.empty or not evaluation["outcome_window_mature"].all():
            raise ValueError(f"Target month {month} has no complete mature evaluation set.")
        weights = None if weight_column is None else pool[weight_column].to_numpy(float)
        delta = fit_intercept_adjustment(pool[LABEL], pool[MODEL_C], weights)
        adjusted = apply_intercept_adjustment(evaluation[MODEL_C], delta)
        result.loc[evaluation.index, "probability_C_sequential_adjusted"] = adjusted
        pool_y = pool[LABEL].to_numpy(int)
        pool_p = pool[MODEL_C].to_numpy(float)
        records.append({
            "target_month": month,
            "target_decision_time": target.isoformat(sep=" "),
            "availability_rule": "outcome_window_end_exclusive < target_decision_time; complete coverage required",
            "calibration_snapshots": int(len(pool)),
            "calibration_unique_customers": int(pool[CUSTOMER].nunique()),
            "calibration_positives": int(pool[LABEL].sum()),
            "calibration_negatives": int(len(pool) - pool[LABEL].sum()),
            "calibration_prevalence": float(pool[LABEL].mean()),
            "latest_maturity_timestamp": pd.to_datetime(pool["outcome_window_end_exclusive"]).max().isoformat(sep=" "),
            "fitted_intercept_delta": delta,
            "evaluation_snapshots": int(len(evaluation)),
            "evaluation_customers": int(evaluation[CUSTOMER].nunique()),
            "pool_predictions_mean_after_fit": float(apply_intercept_adjustment(pool_p, delta).mean()),
            "pool_predictions_mean_before_fit": float(pool_p.mean()),
            "sample_weighted_fit": weight_column is not None,
        })
    return result, records


def _monthly_metrics(evaluated: pd.DataFrame) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for month in ("2011-07", "2011-08", *TARGET_MONTHS):
        subset = evaluated.loc[evaluated[MONTH].eq(month)].copy()
        if subset.empty:
            continue
        y = subset[LABEL].to_numpy(int)
        row: dict[str, Any] = {
            "snapshots": len(subset), "unique_customers": int(subset[CUSTOMER].nunique()),
            "positives": int(y.sum()), "negatives": int(len(y) - y.sum()),
            "prevalence": float(y.mean()), "models": {},
        }
        for name, col in (("B_rfm", MODEL_B), ("C_full_raw", MODEL_C)):
            p = subset[col].to_numpy(float)
            row["models"][name] = {
                **_weighted_metrics(y, p), "targeting": targeting_metrics(y, p),
            }
        adjusted = subset["probability_C_sequential_adjusted"].to_numpy(float)
        if np.isfinite(adjusted).all():
            row["models"]["C_full_adjusted"] = {
                **_weighted_metrics(y, adjusted), "targeting": targeting_metrics(y, adjusted),
                "within_month_ranking_unchanged": bool(
                    np.array_equal(np.argsort(np.argsort(adjusted)), np.argsort(np.argsort(subset[MODEL_C].to_numpy(float))))
                ),
            }
        output[month] = row
    return output


def _pooled_calibration_comparison(evaluated: pd.DataFrame) -> dict[str, Any]:
    target = evaluated.loc[evaluated[MONTH].isin(TARGET_MONTHS)].copy()
    y = target[LABEL].to_numpy(int)
    raw = target[MODEL_C].to_numpy(float)
    adjusted = target["probability_C_sequential_adjusted"].to_numpy(float)
    return {
        "months": list(TARGET_MONTHS),
        "snapshots": int(len(target)),
        "unique_customers": int(target[CUSTOMER].nunique()),
        "raw_model_c": _weighted_metrics(y, raw),
        "sequentially_adjusted_model_c": _weighted_metrics(y, adjusted),
        "brier_difference_adjusted_minus_raw": float(np.mean((y - adjusted) ** 2) - np.mean((y - raw) ** 2)),
        "interpretation": "exploratory; these same months were previously used in the baseline holdout report",
    }


def customer_cluster_bootstrap_brier_difference(
    frame: pd.DataFrame, *, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired customer bootstrap, refitting lagged deltas inside each replicate."""
    rng = np.random.Generator(np.random.PCG64(seed))
    cluster_values, cluster_codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    clusters = np.asarray(cluster_values, dtype=str)
    if len(clusters) < 2:
        raise ValueError("At least two customers are required for cluster bootstrap.")
    y = frame[LABEL].to_numpy(dtype=int)
    probability = frame[MODEL_C].to_numpy(dtype=float)
    month_values = frame[MONTH].astype(str).to_numpy()
    decision = pd.to_datetime(frame[DECISION]).to_numpy(dtype="datetime64[ns]")
    maturity = pd.to_datetime(frame["outcome_window_end_exclusive"]).to_numpy(dtype="datetime64[ns]")
    complete = (
        frame["evaluation_partition"].eq("test").to_numpy()
        & frame["outcome_window_mature"].eq(True).to_numpy()
        & frame["outcome_coverage_status"].eq("complete").to_numpy()
        & np.isin(y, [0, 1])
    )
    target_specs = []
    for month in TARGET_MONTHS:
        target = np.datetime64(f"{month}-01T00:00:00", "ns")
        pool = np.flatnonzero(complete & (decision < target) & (maturity < target))
        evaluation = np.flatnonzero(month_values == month)
        target_specs.append((pool, evaluation))
    differences: list[float] = []
    omitted = 0
    for _ in range(n_resamples):
        draws = rng.integers(0, len(clusters), size=len(clusters))
        cluster_weights = np.bincount(draws, minlength=len(clusters)).astype(float)
        row_weights = cluster_weights[cluster_codes]
        total_loss_delta = 0.0
        total_eval_weight = 0.0
        try:
            for pool_idx, eval_idx in target_specs:
                fit_weights = row_weights[pool_idx]
                if fit_weights.sum() <= 0:
                    continue
                delta = fit_intercept_adjustment(y[pool_idx], probability[pool_idx], fit_weights)
                eval_weights = row_weights[eval_idx]
                active = eval_weights > 0
                if not active.any():
                    continue
                adjusted = apply_intercept_adjustment(probability[eval_idx][active], delta)
                labels = y[eval_idx][active]
                raw = probability[eval_idx][active]
                weights = eval_weights[active]
                total_loss_delta += float(np.dot(weights, (labels - adjusted) ** 2 - (labels - raw) ** 2))
                total_eval_weight += float(weights.sum())
        except ValueError:
            omitted += 1
            continue
        if total_eval_weight <= 0:
            omitted += 1
            continue
        differences.append(total_loss_delta / total_eval_weight)
    low, high = (np.percentile(differences, [2.5, 97.5]) if differences else (None, None))
    return {
        "estimate_brier_difference_adjusted_minus_raw": float(np.mean(differences)) if differences else None,
        "percentile_95_interval": [float(low), float(high)] if differences else [None, None],
        "requested_resamples": n_resamples, "valid_resamples": len(differences),
        "omitted_resamples": omitted, "seed": seed,
        "method": "paired customer-cluster bootstrap; preserve multiplicity and refit each lagged intercept per replicate",
        "limitation": "uncertainty is conditional on these historical months and does not quantify future-period variation",
    }


def run_analysis(
    dataset_path: Path, source_manifest_path: Path, prediction_path: Path,
    models_path: Path, run_manifest_path: Path,
) -> tuple[dict[str, Any], pd.DataFrame]:
    joined, hashes = verify_and_join_inputs(dataset_path, source_manifest_path, prediction_path, models_path, run_manifest_path)
    calibrated, calibration_records = sequential_calibration(joined)
    if calibrated.loc[calibrated[MONTH].isin(TARGET_MONTHS), "probability_C_sequential_adjusted"].isna().any():
        raise AssertionError("Every target-month row must receive exactly one lagged adjustment.")
    monthly = _monthly_metrics(calibrated)
    pooled = _pooled_calibration_comparison(calibrated)
    output = {
        "experiment": "M2-012 sequential intercept calibration; exploratory historical simulation",
        "input_sha256": hashes,
        "baseline_model_artifact_sha256": hashes["models"],
        "baseline_prediction_artifact_sha256": hashes["predictions"],
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "feature_order": list(FEATURE_COLUMNS),
        "baseline_models_refit": False,
        "strict_label_availability_rule": "outcome_window_end_exclusive < target decision_time and complete outcome coverage",
        "outcome_horizon_days": 30,
        "epsilon_for_logit_only": EPSILON,
        "calibration_pools": calibration_records,
        "pooled_september_november": pooled,
        "monthly_metrics": monthly,
        "paired_customer_cluster_bootstrap": customer_cluster_bootstrap_brier_difference(
            calibrated, n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
        ),
        "limitations": [
            "July-November holdout outcomes and metrics were already examined; this is exploratory, not independent confirmation.",
            "Only September-November are evaluated after two-month calibration warm-up.",
            "Customer clustering does not create independent calendar-period replications.",
            "Intercept adjustment corrects a prevalence-level offset only and preserves within-month ranks.",
            "Predictive ranking and lift are not causal CRM effects.",
        ],
    }
    return output, calibrated


def _write_outputs(output: dict[str, Any], predictions: pd.DataFrame, output_dir: Path) -> dict[str, str]:
    repo = ROOT.resolve()
    destination = output_dir.resolve()
    if destination == repo or repo in destination.parents:
        raise ValueError("Customer-level outputs must be written outside the repository.")
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "aggregate_results": destination / "m2_012_sequential_calibration_aggregate.json",
        "customer_predictions": destination / "m2_012_sequential_calibration_predictions.parquet",
        "run_manifest": destination / "m2_012_sequential_calibration_manifest.json",
    }
    if any(path.exists() for path in files.values()):
        raise FileExistsError("Refusing to overwrite existing M2-012 outputs.")
    public_aggregate = destination / "m2_012_sequential_calibration_aggregate.json"
    public_aggregate.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    private_columns = [CUSTOMER, DECISION, MONTH, LABEL, MODEL_B, MODEL_C, "probability_C_sequential_adjusted"]
    predictions.loc[:, private_columns].to_parquet(files["customer_predictions"], index=False)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": output["input_sha256"],
        "output_sha256": {
            "aggregate_results": sha256_file(public_aggregate),
            "customer_predictions": sha256_file(files["customer_predictions"]),
        },
        "output_files": {key: value.name for key, value in files.items()},
        "repository_output_refused": True,
    }
    files["run_manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {key: str(value) for key, value in files.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result, predictions = run_analysis(args.dataset, args.source_manifest, args.predictions, args.models, args.run_manifest)
    paths = _write_outputs(result, predictions, args.output_dir)
    print(json.dumps({"calibration_pools": result["calibration_pools"], "pooled_september_november": result["pooled_september_november"], "outputs": paths}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

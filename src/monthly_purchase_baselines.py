"""Execute the predeclared established-customer monthly baseline experiment."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from day21_baseline import calibration_diagnostic  # noqa: E402


PROTOCOL_PATH = REPO_ROOT / "docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md"
EXPECTED_PROTOCOL_SHA256 = "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4"
EXPECTED_DATASET_SHA256 = "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8"
EXPECTED_MANIFEST_SHA256 = "3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13"
EXPECTED_BUILDER_SHA256 = "58f29d2780f541c591312c8d7773815b28d3d828c4be2adea5994c47c8cfa82b"
RFM_FEATURES = (
    "days_since_last_qualifying_purchase",
    "qualifying_purchase_occasions_365d",
    "qualifying_gross_merchandise_365d",
)
LABEL_COLUMN = "outcome_label"
CUSTOMER_COLUMN = "customer_id"
MONTH_COLUMN = "snapshot_month"
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261112
MODEL_SETTINGS = {
    "solver": "lbfgs",
    "penalty": "l2",
    "C": 1.0,
    "fit_intercept": True,
    "class_weight": None,
    "tol": 1e-8,
    "max_iter": 5000,
    "random_state": 20261112,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class FittedPreprocessor:
    features: tuple[str, ...]
    log_medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    constant_columns: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if tuple(frame.columns) != self.features:
            raise ValueError("Predictor columns/order differ from the fitted allowlist.")
        raw = _numeric_matrix(frame, self.features)
        logged = np.log1p(raw)
        for index, median in enumerate(self.log_medians):
            missing = np.isnan(logged[:, index])
            logged[missing, index] = median
        return (logged - self.means) / self.scales

    def as_dict(self) -> dict[str, Any]:
        return {
            "features": list(self.features),
            "transformation": "log1p",
            "imputation": "training median after log1p; no missing indicators",
            "log_medians": self.log_medians.tolist(),
            "training_log_means": self.means.tolist(),
            "training_log_population_sd": self.scales.tolist(),
            "constant_training_columns": list(self.constant_columns),
            "standardisation_ddof": 0,
        }


@dataclass
class FittedModel:
    name: str
    features: tuple[str, ...]
    preprocessor: FittedPreprocessor
    estimator: LogisticRegression

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "features": list(self.features),
            "settings": MODEL_SETTINGS,
            "preprocessing": self.preprocessor.as_dict(),
            "intercept": float(self.estimator.intercept_[0]),
            "coefficients_standardized_log1p": self.estimator.coef_[0].astype(float).tolist(),
            "iterations": int(self.estimator.n_iter_[0]),
            "converged": bool(self.estimator.n_iter_[0] < MODEL_SETTINGS["max_iter"]),
        }


def _numeric_matrix(frame: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    if tuple(frame.columns) != features:
        raise ValueError("Predictor columns/order differ from the prescribed allowlist.")
    try:
        values = frame.to_numpy(dtype=float, na_value=np.nan, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("All predictors must be numeric.") from exc
    observed = values[~np.isnan(values)]
    if not np.isfinite(observed).all():
        raise ValueError("Observed predictors must be finite.")
    if (observed < 0).any():
        raise ValueError("All predeclared predictors must be nonnegative for log1p.")
    if np.isinf(values).any():
        raise ValueError("Predictors cannot contain infinite values.")
    return values


def fit_preprocessor(train_frame: pd.DataFrame, features: Iterable[str]) -> tuple[FittedPreprocessor, np.ndarray]:
    """Fit log1p imputation and population standardisation on training only."""
    ordered = tuple(features)
    raw = _numeric_matrix(train_frame, ordered)
    logged = np.log1p(raw)
    if np.isnan(logged).all(axis=0).any():
        raise ValueError("A training predictor is entirely missing; stop without changing the protocol.")
    medians = np.nanmedian(logged, axis=0)
    imputed = logged.copy()
    for index, median in enumerate(medians):
        imputed[np.isnan(imputed[:, index]), index] = median
    means = imputed.mean(axis=0)
    raw_scales = imputed.std(axis=0, ddof=0)
    constant = tuple(ordered[i] for i, scale in enumerate(raw_scales) if scale == 0.0)
    scales = np.where(raw_scales == 0.0, 1.0, raw_scales)
    prep = FittedPreprocessor(ordered, medians, means, scales, constant)
    return prep, (imputed - means) / scales


def fit_models(training: pd.DataFrame) -> tuple[float, dict[str, FittedModel], dict[str, np.ndarray]]:
    """Fit the two fixed logistic models using training rows only."""
    if training.empty or training[LABEL_COLUMN].isna().any():
        raise ValueError("Training must contain mature labelled snapshots.")
    y = training[LABEL_COLUMN].to_numpy(dtype=int)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Training labels must contain both classes 0 and 1.")
    prevalence = float(y.mean())
    fitted: dict[str, FittedModel] = {}
    train_probabilities: dict[str, np.ndarray] = {
        "A_constant": np.full(len(training), prevalence, dtype=float)
    }
    for name, features in (("B_rfm", RFM_FEATURES), ("C_full_11", tuple(FEATURE_COLUMNS))):
        train_frame = training.loc[:, list(features)]
        preprocessor, x_train = fit_preprocessor(train_frame, features)
        estimator = LogisticRegression(**MODEL_SETTINGS)
        estimator.fit(x_train, y)
        if estimator.n_iter_[0] >= MODEL_SETTINGS["max_iter"]:
            raise RuntimeError(f"{name} failed to converge within the predeclared iteration limit.")
        if not np.isfinite(estimator.coef_).all() or not np.isfinite(estimator.intercept_).all():
            raise RuntimeError(f"{name} produced non-finite parameters.")
        fitted[name] = FittedModel(name, tuple(features), preprocessor, estimator)
        train_probabilities[name] = estimator.predict_proba(x_train)[:, 1]
    return prevalence, fitted, train_probabilities


def predict_models(
    prevalence: float,
    fitted: dict[str, FittedModel],
    test: pd.DataFrame,
) -> dict[str, np.ndarray]:
    """Generate each fixed model's test probability once."""
    predictions: dict[str, np.ndarray] = {
        "A_constant": np.full(len(test), prevalence, dtype=float)
    }
    for name in ("B_rfm", "C_full_11"):
        model = fitted[name]
        x_test = model.preprocessor.transform(test.loc[:, list(model.features)])
        predictions[name] = model.estimator.predict_proba(x_test)[:, 1]
    return predictions


def _weighted_auc_for_cluster_draw(
    y: np.ndarray,
    score: np.ndarray,
    cluster_codes: np.ndarray,
    selected_clusters: np.ndarray,
    n_clusters: int,
) -> float | None:
    multiplicities = np.bincount(selected_clusters, minlength=n_clusters)
    weights = multiplicities[cluster_codes]
    active = weights > 0
    if np.unique(y[active]).size < 2:
        return None
    return float(roc_auc_score(y[active], score[active], sample_weight=weights[active]))


def customer_cluster_bootstrap_auc(
    y_true: Iterable[int],
    score: Iterable[float],
    customer_ids: Iterable[Any],
    *,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Customer-cluster percentile CI; omit one-class resamples without redraw."""
    y = np.asarray(list(y_true), dtype=int)
    probability = np.asarray(list(score), dtype=float)
    customers = np.asarray(list(customer_ids), dtype=str)
    if not (len(y) == len(probability) == len(customers)) or len(y) == 0:
        raise ValueError("Bootstrap inputs must be nonempty and aligned.")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(probability).all():
        raise ValueError("Bootstrap labels/scores are invalid.")
    clusters = np.unique(customers)
    if len(clusters) < 2:
        raise ValueError("At least two customer clusters are required.")
    lookup = {cluster: index for index, cluster in enumerate(clusters)}
    codes = np.fromiter((lookup[customer] for customer in customers), dtype=int, count=len(customers))
    rng = np.random.Generator(np.random.PCG64(seed))
    aucs: list[float] = []
    omitted = 0
    for _ in range(n_resamples):
        draws = rng.integers(0, len(clusters), size=len(clusters))
        auc = _weighted_auc_for_cluster_draw(y, probability, codes, draws, len(clusters))
        if auc is None:
            omitted += 1
        else:
            aucs.append(auc)
    if not aucs:
        return {
            "lower_95": None,
            "upper_95": None,
            "valid_resamples": 0,
            "omitted_single_class_resamples": omitted,
            "requested_resamples": n_resamples,
            "seed": seed,
            "method": "two-sided percentile interval over valid customer-cluster resamples",
        }
    low, high = np.percentile(np.asarray(aucs), [2.5, 97.5])
    return {
        "lower_95": float(low),
        "upper_95": float(high),
        "valid_resamples": len(aucs),
        "omitted_single_class_resamples": omitted,
        "requested_resamples": n_resamples,
        "seed": seed,
        "method": "two-sided percentile interval over valid customer-cluster resamples",
    }


def _safe_auc(y: np.ndarray, prediction: np.ndarray) -> float | None:
    return float(roc_auc_score(y, prediction)) if np.unique(y).size == 2 else None


def _basic_metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float | None]:
    return {
        "roc_auc": _safe_auc(y, probability),
        "average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)),
    }


def evaluate_predictions(
    test: pd.DataFrame,
    predictions: dict[str, np.ndarray],
) -> dict[str, Any]:
    """Calculate only the metrics declared in M2-007."""
    y = test[LABEL_COLUMN].to_numpy(dtype=int)
    prevalence = float(y.mean())
    summary: dict[str, Any] = {"test_prevalence": prevalence, "models": {}}
    for name in ("A_constant", "B_rfm", "C_full_11"):
        probability = np.asarray(predictions[name], dtype=float)
        if len(probability) != len(y) or not np.isfinite(probability).all():
            raise ValueError(f"Invalid prediction vector for {name}.")
        summary["models"][name] = {
            **_basic_metrics(y, probability),
            "mean_predicted_probability": float(probability.mean()),
            "observed_prevalence": prevalence,
            "calibration": (
                calibration_diagnostic(y, probability)
                if name != "A_constant"
                else {
                    "intercept": float(np.log(prevalence / (1 - prevalence)) - np.log(probability[0] / (1 - probability[0]))),
                    "slope": None,
                    "status": "intercept_only_calibration_in_large; slope_not_identifiable",
                }
            ),
            "calibration_bands": _calibration_bands(y, probability),
            "targeting_capacities": _targeting_metrics(y, probability, prevalence, ranked=name != "A_constant"),
        }
    summary["monthly"] = _monthly_metrics(test, predictions)
    summary["predictor_distributions"] = None
    summary["probability_distributions"] = _probability_distributions(test, predictions)
    summary["model_c_customer_clustered_auc_95"] = customer_cluster_bootstrap_auc(
        y, predictions["C_full_11"], test[CUSTOMER_COLUMN].astype(str)
    )
    return summary


def _calibration_bands(y: np.ndarray, p: np.ndarray) -> list[dict[str, Any]]:
    edges = np.linspace(0.0, 1.0, 11)
    band = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
    result = []
    for index in range(10):
        selected = band == index
        result.append({
            "lower": float(edges[index]),
            "upper": float(edges[index + 1]),
            "upper_inclusive": index == 9,
            "n": int(selected.sum()),
            "mean_predicted": float(p[selected].mean()) if selected.any() else None,
            "observed_prevalence": float(y[selected].mean()) if selected.any() else None,
        })
    return result


def _targeting_metrics(y: np.ndarray, p: np.ndarray, prevalence: float, *, ranked: bool) -> list[dict[str, Any]]:
    result = []
    for fraction in (0.05, 0.10, 0.20):
        nominal = int(np.ceil(fraction * len(y)))
        if not ranked:
            result.append({
                "nominal_capacity": fraction,
                "nominal_rows": nominal,
                "actual_rows": nominal,
                "actual_capacity": nominal / len(y),
                "precision": prevalence,
                "lift": 1.0,
                "interpretation": "random selection expectation; constant model has no ranking",
            })
            continue
        threshold = np.sort(p)[::-1][nominal - 1]
        selected = p >= threshold
        precision = float(y[selected].mean())
        result.append({
            "nominal_capacity": fraction,
            "nominal_rows": nominal,
            "actual_rows": int(selected.sum()),
            "actual_capacity": float(selected.mean()),
            "boundary_probability": float(threshold),
            "precision": precision,
            "lift": precision / prevalence,
            "interpretation": "all probability ties at the capacity boundary included",
        })
    return result


def _monthly_metrics(test: pd.DataFrame, predictions: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    rows = []
    for month, indices in test.groupby(MONTH_COLUMN, sort=True).groups.items():
        idx = np.asarray(list(indices), dtype=int)
        y = test.loc[idx, LABEL_COLUMN].to_numpy(dtype=int)
        row: dict[str, Any] = {
            "snapshot_month": str(month),
            "snapshots": len(idx),
            "unique_customers": int(test.loc[idx, CUSTOMER_COLUMN].nunique()),
            "positive": int(y.sum()),
            "negative": int(len(y) - y.sum()),
            "prevalence": float(y.mean()),
            "roc_auc": {},
        }
        for name, probability in predictions.items():
            row["roc_auc"][name] = _safe_auc(y, probability[idx])
        rows.append(row)
    return rows


def _predictor_distributions(training: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for name in FEATURE_COLUMNS:
        result[name] = {}
        for partition, frame in (("train", training), ("test", test)):
            values = pd.to_numeric(frame[name], errors="coerce")
            result[name][partition] = {
                "missing_share": float(values.isna().mean()),
                "median": float(values.median()) if values.notna().any() else None,
                "q25": float(values.quantile(0.25)) if values.notna().any() else None,
                "q75": float(values.quantile(0.75)) if values.notna().any() else None,
            }
    return result


def _probability_distributions(
    test: pd.DataFrame,
    predictions: dict[str, np.ndarray],
    training_probabilities: dict[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, p in predictions.items():
        values: dict[str, Any] = {"test": _quantiles(p), "test_by_month": {}}
        if training_probabilities and name in training_probabilities:
            values["training_in_sample_resubstitution"] = _quantiles(training_probabilities[name])
        for month, indices in test.groupby(MONTH_COLUMN, sort=True).groups.items():
            idx = np.asarray(list(indices), dtype=int)
            values["test_by_month"][str(month)] = _quantiles(p[idx])
        result[name] = values
    return result


def _quantiles(values: Iterable[float]) -> dict[str, float]:
    p = np.asarray(list(values), dtype=float)
    q25, median, q75 = np.quantile(p, [0.25, 0.5, 0.75])
    return {"mean": float(p.mean()), "q25": float(q25), "median": float(median), "q75": float(q75)}


def _select_partitions(cohort: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {CUSTOMER_COLUMN, "decision_time", "outcome_window_mature", LABEL_COLUMN, "evaluation_partition", MONTH_COLUMN, *FEATURE_COLUMNS}
    missing = required - set(cohort.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
    if cohort.duplicated([CUSTOMER_COLUMN, "decision_time"]).any():
        raise ValueError("Duplicate customer-month keys found.")
    selected = cohort.loc[cohort.evaluation_partition.isin(["train", "test"])].copy()
    if not selected.outcome_window_mature.all() or selected[LABEL_COLUMN].isna().any():
        raise ValueError("Train/test rows must have mature, observed labels.")
    if not selected[LABEL_COLUMN].isin([0, 1]).all():
        raise ValueError("Train/test labels must be binary.")
    train = selected.loc[selected.evaluation_partition == "train"].sort_values([CUSTOMER_COLUMN, "decision_time"]).reset_index(drop=True)
    test = selected.loc[selected.evaluation_partition == "test"].sort_values([CUSTOMER_COLUMN, "decision_time"]).reset_index(drop=True)
    if train.empty or test.empty:
        raise ValueError("Approved training or test partition is empty.")
    cutoff = pd.Timestamp("2011-07-01 00:00:00")
    if not (train.decision_time < cutoff).all() or not (train.outcome_window_end_exclusive <= cutoff).all():
        raise ValueError("Training rows violate the approved as-of cutoff.")
    if not (test.decision_time >= cutoff).all():
        raise ValueError("Test decisions are not later than the training population.")
    if not test.outcome_window_mature.all():
        raise ValueError("Test outcomes are not mature.")
    return train, test


def verify_frozen_inputs(dataset_path: Path, manifest_path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    if sha256_file(PROTOCOL_PATH) != EXPECTED_PROTOCOL_SHA256:
        raise ValueError("Frozen M2-007 protocol SHA-256 mismatch; stop before fitting.")
    if sha256_file(dataset_path) != EXPECTED_DATASET_SHA256:
        raise ValueError("M2-004 dataset SHA-256 mismatch; stop before fitting.")
    if sha256_file(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("M2-004 manifest SHA-256 mismatch; stop before fitting.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("output_sha256") != EXPECTED_DATASET_SHA256:
        raise ValueError("Manifest dataset checksum does not match the frozen dataset.")
    if manifest.get("builder_sha256") != EXPECTED_BUILDER_SHA256:
        raise ValueError("M2-004 builder hash differs from the frozen manifest.")
    if tuple(manifest.get("feature_columns", [])) != tuple(FEATURE_COLUMNS):
        raise ValueError("Manifest feature order differs from FEATURE_COLUMNS.")
    if sha256_file(REPO_ROOT / "src/monthly_customer_snapshots.py") != EXPECTED_BUILDER_SHA256:
        raise ValueError("Current snapshot builder differs from the verified feature implementation.")
    cohort = pd.read_parquet(dataset_path)
    if len(cohort) != 51612:
        raise ValueError("Unexpected M2-004 row count; stop before fitting.")
    return manifest, cohort


def verify_expected_partitions(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    actual = {
        "training_snapshots": len(train),
        "training_unique_customers": int(train[CUSTOMER_COLUMN].nunique()),
        "training_positive": int(train[LABEL_COLUMN].sum()),
        "test_snapshots": len(test),
        "test_unique_customers": int(test[CUSTOMER_COLUMN].nunique()),
        "test_positive": int(test[LABEL_COLUMN].sum()),
        "customer_overlap": len(set(train[CUSTOMER_COLUMN]) & set(test[CUSTOMER_COLUMN])),
    }
    expected = {
        "training_snapshots": 25647,
        "training_unique_customers": 4808,
        "training_positive": 4573,
        "test_snapshots": 21672,
        "test_unique_customers": 4999,
        "test_positive": 5092,
        "customer_overlap": 4265,
    }
    actual["training_negative"] = actual["training_snapshots"] - actual["training_positive"]
    actual["test_negative"] = actual["test_snapshots"] - actual["test_positive"]
    expected["training_negative"] = 21074
    expected["test_negative"] = 16580
    if actual != expected:
        raise ValueError(f"Partition counts differ from M2-007 expectations: {actual}")
    return actual


def run_experiment(dataset_path: Path, manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    try:
        output_dir.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Model artifacts and row-level predictions must remain outside the repository.")
    prediction_path = output_dir / "monthly_purchase_baselines_m2_008_test_predictions.parquet"
    models_path = output_dir / "monthly_purchase_baselines_m2_008_models.json"
    run_manifest_path = output_dir / "monthly_purchase_baselines_m2_008_run_manifest.json"
    if any(path.exists() for path in (prediction_path, models_path, run_manifest_path)):
        raise FileExistsError("Refusing to overwrite an existing M2-008 output artifact.")
    manifest, cohort = verify_frozen_inputs(dataset_path, manifest_path)
    train, test = _select_partitions(cohort)
    partition_counts = verify_expected_partitions(train, test)
    if tuple(FEATURE_COLUMNS) != tuple(manifest["feature_columns"]):
        raise ValueError("Approved predictor order mismatch.")

    # The fitting call receives training only. Test data is first passed to
    # prediction/evaluation after all preprocessing and model parameters are frozen.
    prevalence, fitted, train_probabilities = fit_models(train)
    predictions = predict_models(prevalence, fitted, test)
    results = evaluate_predictions(test, predictions)
    results["predictor_distributions"] = _predictor_distributions(train, test)
    results["probability_distributions"] = _probability_distributions(test, predictions, train_probabilities)
    results["auc_difference_C_minus_B_descriptive"] = (
        results["models"]["C_full_11"]["roc_auc"] - results["models"]["B_rfm"]["roc_auc"]
    )
    results["primary_success_criterion_met"] = bool(
        results["model_c_customer_clustered_auc_95"]["lower_95"] is not None
        and results["model_c_customer_clustered_auc_95"]["lower_95"] > 0.50
    )
    results["partition_counts"] = partition_counts
    results["models"]["A_constant"]["training_prevalence"] = prevalence
    results["models"]["B_rfm"]["fit"] = fitted["B_rfm"].as_dict()
    results["models"]["C_full_11"]["fit"] = fitted["C_full_11"].as_dict()

    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_frame = test[[CUSTOMER_COLUMN, "decision_time", MONTH_COLUMN, LABEL_COLUMN]].copy()
    for name, probability in predictions.items():
        prediction_frame[f"probability_{name}"] = probability
    prediction_frame.to_parquet(prediction_path, index=False)
    models_doc = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "feature_order": list(FEATURE_COLUMNS),
        "model_A": {"type": "constant", "probability": prevalence},
        "model_B": fitted["B_rfm"].as_dict(),
        "model_C": fitted["C_full_11"].as_dict(),
    }
    models_path.write_text(json.dumps(models_doc, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    run_manifest = {
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "source_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "builder_sha256": EXPECTED_BUILDER_SHA256,
        "feature_order": list(FEATURE_COLUMNS),
        "partition_counts": partition_counts,
        "software": _software_versions(),
        "bootstrap": results["model_c_customer_clustered_auc_95"],
        "results": results,
        "predictions_artifact": prediction_path.name,
        "predictions_sha256": sha256_file(prediction_path),
        "models_artifact": models_path.name,
        "models_sha256": sha256_file(models_path),
        "training_prediction_note": "in-sample/resubstitution; descriptive only",
    }
    run_manifest_path.write_text(json.dumps(run_manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return {
        "results": results,
        "artifacts": {
            "predictions": str(prediction_path),
            "models": str(models_path),
            "run_manifest": str(run_manifest_path),
        },
    }


def _software_versions() -> dict[str, str]:
    import scipy
    import sklearn
    import pyarrow

    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "pyarrow": pyarrow.__version__,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New local directory outside the Git repository")
    args = parser.parse_args()
    result = run_experiment(args.dataset, args.manifest, args.output_dir)
    print(json.dumps({"results": result["results"], "artifacts": result["artifacts"]}, sort_keys=True))


if __name__ == "__main__":
    main()

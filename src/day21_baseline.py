"""Run the frozen M1-009 Day-21 baseline once on its chronological holdout."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "docs" / "research" / "COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md"
FROZEN_PROTOCOL_SHA256 = "d5be6bfefbbbddf8e5f7dfe8a81202cc04c1d18e7480c698aec5211b3c92c3ac"
CUTOFF = pd.Timestamp("2011-07-01 00:00:00")
BOOTSTRAP_SEED = 20261112
BOOTSTRAP_RESAMPLES = 2_000
MODEL_B_FEATURES = ("first_day_qualifying_gross",)
MODEL_C_FEATURES = (
    "first_day_qualifying_gross",
    "first_day_item_quantity",
    "first_day_product_diversity",
)
LABEL_COLUMN = "outcome_label"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_protocol(path: Path = PROTOCOL_PATH) -> str:
    digest = sha256_file(path)
    if digest != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Baseline protocol hash differs from the frozen pre-fit protocol.")
    return digest


def select_approved_partitions(
    cohort: pd.DataFrame, *, validate_protocol_counts: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select only as-of mature training labels and fully mature test rows."""
    required = {
        "evaluation_partition", "outcome_label", "complete_horizon_observed",
        "training_label_available_at_cutoff", "day21_decision_timestamp",
        "day111_outcome_deadline", *MODEL_C_FEATURES,
    }
    missing = required - set(cohort.columns)
    if missing:
        raise ValueError(f"Cohort missing required baseline columns: {sorted(missing)}")
    train = cohort.loc[cohort["evaluation_partition"].eq("train")].copy()
    test = cohort.loc[cohort["evaluation_partition"].eq("test")].copy()
    if train.empty or test.empty:
        raise ValueError("Approved train or test partition is empty.")
    if train[LABEL_COLUMN].isna().any() or test[LABEL_COLUMN].isna().any():
        raise ValueError("Training and test partitions must have known labels.")
    if not train["complete_horizon_observed"].all() or not test["complete_horizon_observed"].all():
        raise ValueError("Training and test labels must have complete outcome horizons.")
    if not train["training_label_available_at_cutoff"].all():
        raise ValueError("Training includes labels unavailable at the evaluation cutoff.")
    if not (train["day111_outcome_deadline"] <= CUTOFF).all():
        raise ValueError("Training outcome deadline exceeds the approved cutoff.")
    if not (train["day21_decision_timestamp"] < CUTOFF).all():
        raise ValueError("Training decisions are not strictly before the cutoff.")
    if not (test["day21_decision_timestamp"] >= CUTOFF).all():
        raise ValueError("Test decisions are not at/after the cutoff.")
    if not train[LABEL_COLUMN].isin([0, 1]).all() or not test[LABEL_COLUMN].isin([0, 1]).all():
        raise ValueError("Labels must be binary in approved partitions.")
    if validate_protocol_counts:
        train_counts = train[LABEL_COLUMN].value_counts().to_dict()
        test_counts = test[LABEL_COLUMN].value_counts().to_dict()
        if (len(train), train_counts.get(1, 0), train_counts.get(0, 0)) != (304, 90, 214):
            raise ValueError("Training partition does not match the frozen 304 / 90 / 214 counts.")
        if (len(test), test_counts.get(1, 0), test_counts.get(0, 0)) != (208, 97, 111):
            raise ValueError("Test partition does not match the frozen 208 / 97 / 111 counts.")
    return train, test


def _log1p_features(frame: pd.DataFrame, features: tuple[str, ...]) -> np.ndarray:
    values = frame.loc[:, list(features)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Allowlisted features must be finite and nonnegative.")
    return np.log1p(values)


def standardize_train_test(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, dict[str, dict[str, float]]]:
    """Apply log1p and training-only population standardisation."""
    train_log = _log1p_features(train, features)
    test_log = _log1p_features(test, features)
    means = train_log.mean(axis=0)
    scales = train_log.std(axis=0, ddof=0)
    if not np.isfinite(scales).all() or (scales <= 0).any():
        raise ValueError("A training predictor has zero or invalid variance.")
    stats = {
        feature: {"log1p_mean": float(mean), "log1p_population_sd": float(scale)}
        for feature, mean, scale in zip(features, means, scales)
    }
    return (train_log - means) / scales, (test_log - means) / scales, stats


def percentile_bootstrap_auc(
    y_true: np.ndarray,
    prediction: np.ndarray,
    *,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired customer bootstrap; omit, do not redraw, single-class samples."""
    y_true = np.asarray(y_true, dtype=int)
    prediction = np.asarray(prediction, dtype=float)
    if len(y_true) != len(prediction) or len(y_true) == 0:
        raise ValueError("Bootstrap inputs must be nonempty and aligned.")
    rng = np.random.default_rng(seed)
    aucs: list[float] = []
    omitted = 0
    for _ in range(n_resamples):
        indices = rng.integers(0, len(y_true), size=len(y_true))
        sample_y = y_true[indices]
        if np.unique(sample_y).size < 2:
            omitted += 1
            continue
        aucs.append(float(roc_auc_score(sample_y, prediction[indices])))
    if not aucs:
        raise ValueError("All bootstrap resamples were single-class; no interval is estimable.")
    low, high = np.percentile(aucs, [2.5, 97.5])
    return {
        "lower_95": float(low), "upper_95": float(high),
        "valid_resamples": len(aucs), "omitted_single_class_resamples": omitted,
        "requested_resamples": n_resamples, "seed": seed,
    }


def calibration_diagnostic(y_true: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    """Estimate joint calibration intercept/slope without adjusting predictions."""
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probability, dtype=float), 1e-12, 1 - 1e-12)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or len(y) == 0:
        return {"intercept": None, "slope": None, "status": "invalid_inputs"}
    if not np.isfinite(y).all() or not np.isfinite(p).all() or not np.isin(y, [0, 1]).all():
        return {"intercept": None, "slope": None, "status": "invalid_inputs"}
    logits = np.log(p / (1 - p))
    if len(np.unique(logits)) < 2:
        return {"intercept": None, "slope": None, "status": "slope_not_identifiable_constant_predictions"}

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        eta = beta[0] + beta[1] * logits
        loss = np.logaddexp(0.0, eta) - y * eta
        residual = 1.0 / (1.0 + np.exp(-np.clip(eta, -700, 700))) - y
        gradient = np.array([residual.sum(), np.dot(residual, logits)])
        return float(loss.sum()), gradient

    fit = minimize(objective, np.array([0.0, 1.0]), jac=True, method="BFGS", options={"gtol": 1e-8, "maxiter": 2000})
    beta = np.asarray(fit.x, dtype=float)
    if not np.isfinite(beta).all() or np.max(np.abs(beta)) > 30:
        return {"intercept": None, "slope": None, "status": "not_estimable_or_unstable"}
    eta = beta[0] + beta[1] * logits
    fitted_probability = 1.0 / (1.0 + np.exp(-np.clip(eta, -700, 700)))
    residual = fitted_probability - y
    design = np.column_stack((np.ones(len(logits)), logits))
    gradient = design.T @ residual
    weights = fitted_probability * (1.0 - fitted_probability)
    information = design.T @ (weights[:, None] * design)
    try:
        eigenvalues = np.linalg.eigvalsh(information)
    except np.linalg.LinAlgError:
        return {"intercept": None, "slope": None, "status": "not_estimable_or_unstable"}
    well_conditioned = (
        np.isfinite(eigenvalues).all()
        and eigenvalues[0] > 1e-10
        and eigenvalues[-1] / eigenvalues[0] < 1e10
    )
    # BFGS can report precision loss at a valid stationary point. Accept that
    # case only when the score is small and the observed information is finite,
    # positive definite and well-conditioned. A success flag alone is also
    # insufficient if these numerical checks fail.
    stationary = np.linalg.norm(gradient, ord=np.inf) <= 1e-7
    if not stationary or not well_conditioned:
        return {"intercept": None, "slope": None, "status": "not_estimable_or_unstable"}
    status = "diagnostic_only" if fit.success else "stationary_optimum_after_optimizer_warning"
    return {"intercept": float(beta[0]), "slope": float(beta[1]), "status": status}


def _metric_summary(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    result = {"brier_score": float(brier_score_loss(y, probability)), "mean_predicted_prevalence": float(np.mean(probability)),
              "observed_prevalence": float(np.mean(y))}
    result["roc_auc"] = float(roc_auc_score(y, probability)) if np.unique(y).size == 2 else None
    return result


def run_experiment(cohort: pd.DataFrame, *, protocol_sha256: str) -> dict[str, Any]:
    """Fit exactly two logistic models and evaluate all three predictions once."""
    if protocol_sha256 != FROZEN_PROTOCOL_SHA256:
        raise ValueError("Expected protocol hash does not match the frozen protocol.")
    train, test = select_approved_partitions(cohort)
    y_train = train[LABEL_COLUMN].to_numpy(dtype=int)
    y_test = test[LABEL_COLUMN].to_numpy(dtype=int)
    train_prevalence = float(y_train.mean())
    predictions: dict[str, np.ndarray] = {
        "A_constant": np.full(len(test), train_prevalence, dtype=float)
    }
    coefficients: dict[str, Any] = {}
    scaling: dict[str, Any] = {}

    for model_name, features in (("B_gross_only", MODEL_B_FEATURES), ("C_three_feature", MODEL_C_FEATURES)):
        x_train, x_test, stats = standardize_train_test(train, test, features)
        model = LogisticRegression(
            penalty=None, solver="lbfgs", fit_intercept=True, tol=1e-10,
            max_iter=5000, random_state=BOOTSTRAP_SEED,
        )
        model.fit(x_train, y_train)
        predictions[model_name] = model.predict_proba(x_test)[:, 1]
        coefficients[model_name] = {
            "intercept": float(model.intercept_[0]),
            "standardised_log1p_coefficients": {
                feature: float(coef) for feature, coef in zip(features, model.coef_[0])
            },
            "converged_iterations": int(model.n_iter_[0]),
        }
        scaling[model_name] = stats

    metrics: dict[str, Any] = {}
    for model_name, probability in predictions.items():
        metrics[model_name] = _metric_summary(y_test, probability)
        metrics[model_name]["calibration"] = (
            {"intercept": None, "slope": None, "status": "slope_not_identifiable_constant_predictions"}
            if model_name == "A_constant" else calibration_diagnostic(y_test, probability)
        )
    metrics["C_three_feature"]["roc_auc_percentile_bootstrap_95"] = percentile_bootstrap_auc(
        y_test, predictions["C_three_feature"]
    )

    monthly: dict[str, Any] = {}
    decision_month = pd.to_datetime(test["day21_decision_timestamp"]).dt.month.to_numpy()
    for month, name in ((7, "July"), (8, "August"), (9, "September")):
        mask = decision_month == month
        monthly[name] = {"n": int(mask.sum()), "positive": int(y_test[mask].sum()),
                         "negative": int(mask.sum() - y_test[mask].sum())}
        for model_name, probability in predictions.items():
            monthly[name][model_name] = _metric_summary(y_test[mask], probability[mask]) if mask.any() else None

    return {
        "protocol_sha256": protocol_sha256,
        "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "software_versions": {"python": __import__("sys").version.split()[0], "pandas": pd.__version__,
                              "scikit_learn": sklearn.__version__, "scipy": scipy.__version__},
        "partition_counts": {
            "training": {"n": len(train), "positive": int(y_train.sum()), "negative": int(len(y_train) - y_train.sum())},
            "test": {"n": len(test), "positive": int(y_test.sum()), "negative": int(len(y_test) - y_test.sum())},
        },
        "training_positive_prevalence": train_prevalence,
        "test_observed_prevalence": float(y_test.mean()),
        "test_minus_train_prevalence": float(y_test.mean() - train_prevalence),
        "metrics": metrics,
        "auc_difference_C_minus_B": float(metrics["C_three_feature"]["roc_auc"] - metrics["B_gross_only"]["roc_auc"]),
        "coefficients": coefficients,
        "training_scaling_statistics": scaling,
        "monthly_test_descriptives": monthly,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True, help="External M1-007 cohort Parquet")
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    args = parser.parse_args()
    digest = verify_frozen_protocol(args.protocol)
    cohort = pd.read_parquet(args.cohort)
    results = run_experiment(cohort, protocol_sha256=digest)
    print(json.dumps(results, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

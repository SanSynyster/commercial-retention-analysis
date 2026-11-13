"""Small, maturity-aware P3 benchmark for the frozen corrected-M2 cohort."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256,
    LABEL_COLUMN, CUSTOMER_COLUMN, MONTH_COLUMN, MODEL_SETTINGS, fit_preprocessor,
    sha256_file,
)
from monthly_targeting_policies import (  # noqa: E402
    FREQUENCY, MODEL_C, select_ranked,
)

LABEL = LABEL_COLUMN
CUSTOMER = CUSTOMER_COLUMN
MONTH = MONTH_COLUMN
DECISION = "decision_time"
FREQ = FREQUENCY
CAPACITIES = (0.05, 0.10, 0.20)
BOOT_REPS = 1000
SEED = 20261113
EXPECTED_PREDICTIONS_SHA256 = "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1"
EXPECTED_PROTOCOL_SHA256 = "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4"

# Predeclared compact search. Same candidate count and same folds per family.
RF_GRID = [
    {"n_estimators": 200, "max_depth": 8, "min_samples_leaf": 20, "max_features": "sqrt", "class_weight": None},
    {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 50, "max_features": 0.8, "class_weight": None},
    {"n_estimators": 300, "max_depth": 8, "min_samples_leaf": 50, "max_features": 0.8, "class_weight": "balanced_subsample"},
]
HGB_GRID = [
    {"learning_rate": 0.05, "max_leaf_nodes": 7, "max_iter": 100, "min_samples_leaf": 50, "l2_regularization": 1.0, "early_stopping": False},
    {"learning_rate": 0.05, "max_leaf_nodes": 15, "max_iter": 150, "min_samples_leaf": 50, "l2_regularization": 1.0, "early_stopping": False},
    {"learning_rate": 0.10, "max_leaf_nodes": 7, "max_iter": 100, "min_samples_leaf": 100, "l2_regularization": 5.0, "early_stopping": False},
]


def make_folds(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Jan–Apr expanding origins; label end must be strictly before validation T."""
    eligible = frame.loc[frame.evaluation_partition.eq("train")].copy()
    eligible[DECISION] = pd.to_datetime(eligible[DECISION])
    eligible["outcome_window_end_exclusive"] = pd.to_datetime(eligible["outcome_window_end_exclusive"])
    folds = []
    for month in ("2011-03", "2011-04", "2011-05", "2011-06"):
        validation = eligible.loc[eligible[MONTH].eq(month)].copy()
        if validation.empty:
            continue
        boundary = validation[DECISION].min()
        training = eligible.loc[
            eligible[DECISION].lt(boundary)
            & eligible["outcome_window_end_exclusive"].lt(boundary)
            & eligible.outcome_window_mature.eq(True)
            & eligible.outcome_coverage_status.eq("complete")
            & eligible[LABEL].isin([0, 1])
        ].copy()
        # Validation labels are used only after the whole 30-day window has matured.
        if not (training["outcome_window_end_exclusive"] < boundary).all():
            raise ValueError(f"Maturity violation in training for {month}.")
        if not validation.outcome_window_mature.all() or not validation.outcome_coverage_status.eq("complete").all():
            raise ValueError(f"Validation labels are not complete for {month}.")
        if validation[LABEL].isna().any() or not validation[LABEL].isin([0, 1]).all():
            raise ValueError(f"Validation includes unknown outcomes for {month}.")
        if training.empty or training[LABEL].nunique() != 2:
            raise ValueError(f"Insufficient mature two-class training labels for {month}.")
        folds.append({"month": month, "boundary": boundary, "train": training, "validation": validation})
    return folds


def tree_pipeline(estimator: Any) -> Pipeline:
    # All fitting (including imputation) occurs inside each fold's pipeline.
    return Pipeline([
        ("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
        ("imputer", SimpleImputer(strategy="median")),
        ("model", estimator),
    ])


def logistic_fit_predict(train: pd.DataFrame, scored: pd.DataFrame) -> np.ndarray:
    preprocessor, x_train = fit_preprocessor(train.loc[:, list(FEATURE_COLUMNS)], FEATURE_COLUMNS)
    model = LogisticRegression(**MODEL_SETTINGS)
    model.fit(x_train, train[LABEL].to_numpy(int))
    if model.n_iter_[0] >= MODEL_SETTINGS["max_iter"]:
        raise RuntimeError("Fold logistic model did not converge under frozen settings.")
    return model.predict_proba(preprocessor.transform(scored.loc[:, list(FEATURE_COLUMNS)]))[:, 1]


def _metrics(y: np.ndarray, score: np.ndarray, *, probability: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "roc_auc": float(roc_auc_score(y, score)) if np.unique(y).size == 2 else None,
        "average_precision": float(average_precision_score(y, score)),
    }
    if probability:
        result.update({
            "brier_score": float(brier_score_loss(y, score)),
            "log_loss": float(log_loss(y, np.clip(score, 1e-15, 1 - 1e-15), labels=[0, 1])),
            "calibration": p3_calibration_diagnostic(y, score),
            "mean_predicted_probability": float(np.mean(score)),
            "calibration_in_the_large_risk_difference": float(np.mean(y) - np.mean(score)),
        })
    else:
        result.update({"brier_score": None, "log_loss": None, "calibration": {"status": "not_applicable_raw_rank"},
                       "mean_predicted_probability": None, "calibration_in_the_large_risk_difference": None})
    return result


def p3_calibration_diagnostic(y_true: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    """P3-only joint logistic calibration diagnostic with explicit tolerance checks.

    This does not change the frozen M1/M2 diagnostic or adjust probabilities.
    A stationary, well-conditioned optimum is reported even if BFGS stops with
    a precision-loss flag; a nonstationary or ill-conditioned result is a fit
    failure, not a calibration estimate.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or not len(y):
        return {"intercept": None, "slope": None, "status": "failed_invalid_inputs"}
    if not np.isfinite(y).all() or not np.isfinite(p).all() or not np.isin(y, [0, 1]).all() or ((p < 0) | (p > 1)).any():
        return {"intercept": None, "slope": None, "status": "failed_invalid_inputs"}
    eps = 1e-12
    logits = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
    if np.unique(logits).size < 2:
        return {"intercept": None, "slope": None, "status": "not_identifiable_constant_scores"}

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        eta = beta[0] + beta[1] * logits
        fitted = scipy.special.expit(eta)
        loss = np.logaddexp(0.0, eta) - y * eta
        residual = fitted - y
        return float(loss.sum()), np.array([residual.sum(), np.dot(residual, logits)])

    fit = minimize(objective, np.array([0.0, 1.0]), jac=True, method="BFGS",
                   options={"gtol": 1e-6, "maxiter": 5000})
    beta = np.asarray(fit.x, dtype=float)
    if not np.isfinite(beta).all() or np.max(np.abs(beta)) > 30:
        return {"intercept": None, "slope": None, "status": "failed_nonfinite_or_unbounded", "optimizer_success": bool(fit.success)}
    fitted = scipy.special.expit(beta[0] + beta[1] * logits)
    design = np.column_stack((np.ones(len(logits)), logits))
    gradient = design.T @ (fitted - y)
    information = design.T @ ((fitted * (1 - fitted))[:, None] * design)
    try:
        eigen = np.linalg.eigvalsh(information)
    except np.linalg.LinAlgError:
        eigen = np.array([np.nan, np.nan])
    grad_inf = float(np.linalg.norm(gradient, ord=np.inf))
    condition = float(eigen[-1] / eigen[0]) if np.isfinite(eigen).all() and eigen[0] > 0 else None
    stationary = grad_inf <= 1e-5
    well_conditioned = condition is not None and eigen[0] > 1e-10 and condition < 1e10
    if not stationary or not well_conditioned:
        return {"intercept": None, "slope": None, "status": "failed_nonstationary_or_ill_conditioned",
                "optimizer_success": bool(fit.success), "gradient_inf_norm": grad_inf,
                "gradient_tolerance": 1e-5, "information_condition_number": condition}
    return {"intercept": float(beta[0]), "slope": float(beta[1]),
            "status": "estimated" if fit.success else "estimated_stationary_with_optimizer_tolerance_warning",
            "optimizer_success": bool(fit.success), "gradient_inf_norm": grad_inf,
            "gradient_tolerance": 1e-5, "information_condition_number": condition,
            "optimizer_message": str(fit.message)}


def paired_ranking_bootstrap(frame: pd.DataFrame, scores: dict[str, np.ndarray], *, reps: int = BOOT_REPS, seed: int = SEED) -> dict[str, Any]:
    """Paired cluster intervals for tree-minus-logistic AUC/AP, conditional on scores."""
    ids, codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    y = frame[LABEL].to_numpy(int)
    grouped_scores = {}
    for name, score in scores.items():
        _, inverse = np.unique(score, return_inverse=True)
        n_groups = int(inverse.max()) + 1
        grouped_scores[name] = (n_groups - 1 - inverse, n_groups)
    rng = np.random.Generator(np.random.PCG64(seed))
    comparisons = [(tree, "Logistic C") for tree in ("Random Forest", "HistGradientBoosting")]
    point = {}
    samples = {f"{a} - {b}": {"roc_auc": [], "average_precision": []} for a, b in comparisons}
    for a, b in comparisons:
        point[f"{a} - {b}"] = {
            metric: float(metric_fn(y, scores[a]) - metric_fn(y, scores[b]))
            for metric, metric_fn in (("roc_auc", roc_auc_score), ("average_precision", average_precision_score))
        }
    for _ in range(reps):
        draws = rng.integers(0, len(ids), size=len(ids))
        weights = np.bincount(draws, minlength=len(ids))[codes]
        active = weights > 0
        if np.unique(y[active]).size < 2:
            continue
        for a, b in comparisons:
            key = f"{a} - {b}"
            va = _grouped_weighted_ranking_metrics(y, weights, *grouped_scores[a])
            vb = _grouped_weighted_ranking_metrics(y, weights, *grouped_scores[b])
            for metric in ("roc_auc", "average_precision"):
                samples[key][metric].append(float(va[metric] - vb[metric]))
    intervals = {}
    for comparison, metric_samples in samples.items():
        intervals[comparison] = {}
        for metric, values in metric_samples.items():
            lo, hi = np.percentile(values, [2.5, 97.5])
            intervals[comparison][metric] = {"point_difference": point[comparison][metric],
                                             "ci95": [float(lo), float(hi)], "valid_resamples": len(values)}
    return {"method": "paired customer-trajectory percentile bootstrap with customer multiplicity weights",
            "requested_resamples": reps, "seed": seed, "comparisons": intervals,
            "interpretation": "Conditional on fitted model scores and selected configurations; excludes hyperparameter-selection uncertainty and future-period uncertainty."}


def _weighted_ranking_metrics(y: np.ndarray, score: np.ndarray, weights: np.ndarray) -> dict[str, float]:
    active = weights > 0
    return {"roc_auc": float(roc_auc_score(y[active], score[active], sample_weight=weights[active])),
            "average_precision": float(average_precision_score(y[active], score[active], sample_weight=weights[active]))}


def _grouped_weighted_ranking_metrics(y: np.ndarray, weights: np.ndarray, group_code_desc: np.ndarray,
                                      n_groups: int) -> dict[str, float]:
    """Exact weighted AUC/AP from descending score tie groups, without re-sorting."""
    total_by_group = np.bincount(group_code_desc, weights=weights, minlength=n_groups)
    positive_by_group = np.bincount(group_code_desc, weights=weights * y, minlength=n_groups)
    total_positive = float(positive_by_group.sum())
    total_negative = float(total_by_group.sum() - total_positive)
    if total_positive <= 0 or total_negative <= 0:
        raise ValueError("Ranking metrics require both weighted outcome classes.")
    cumulative_positive = np.cumsum(positive_by_group)
    cumulative_total = np.cumsum(total_by_group)
    precision = np.divide(cumulative_positive, cumulative_total, out=np.zeros_like(cumulative_positive), where=cumulative_total > 0)
    ap = float(np.sum(positive_by_group / total_positive * precision))
    negative_by_group = total_by_group - positive_by_group
    negatives_below = total_negative - np.cumsum(negative_by_group)
    auc = float(np.sum(positive_by_group * (negatives_below + .5 * negative_by_group)) / (total_positive * total_negative))
    return {"roc_auc": auc, "average_precision": ap}


def _crm(frame: pd.DataFrame, score: np.ndarray, *, descending: bool = True) -> dict[str, Any]:
    ranked = frame[[CUSTOMER, LABEL] + ([MONTH] if MONTH in frame else [])].copy().reset_index(drop=True)
    ranked["_score"] = score
    # Capacity is applied independently within each snapshot month.
    n, positives = len(ranked), int(ranked[LABEL].sum())
    out = {}
    for capacity in CAPACITIES:
        selected_parts = []
        for indices in (ranked.groupby(MONTH, sort=True).groups.values() if MONTH in ranked else [ranked.index]):
            group = ranked.loc[list(indices)]
            selected_parts.append(select_ranked(group.rename(columns={"_score": "score"}), "score", capacity, descending=descending))
        selected = pd.concat(selected_parts, ignore_index=True)
        tp = int(selected[LABEL].sum())
        precision = tp / len(selected)
        out[str(int(capacity * 100))] = {
            "selected": len(selected), "true_positive": tp, "precision": precision,
            "capture_recall": tp / positives, "lift": precision / (positives / n),
            "capacity_requested": capacity, "capacity_actual": len(selected) / n,
        }
    return out


def evaluate_frame(frame: pd.DataFrame, predictions: dict[str, np.ndarray]) -> dict[str, Any]:
    y = frame[LABEL].to_numpy(int)
    result = {"snapshots": len(frame), "customers": int(frame[CUSTOMER].nunique()),
              "positives": int(y.sum()), "prevalence": float(y.mean()), "models": {}}
    for name, score in predictions.items():
        prob = name != "Frequency"
        result["models"][name] = {**_metrics(y, score, probability=prob),
                                  "crm": _crm(frame, score)}
    return result


def paired_cluster_bootstrap(frame: pd.DataFrame, scores: dict[str, np.ndarray], *, reps: int = BOOT_REPS, seed: int = SEED) -> dict[str, Any]:
    """Paired customer trajectory bootstrap using multiplicity weighted top-k."""
    ids, customer_codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    labels = frame[LABEL].to_numpy(int)
    months = frame[MONTH].astype(str).to_numpy()
    month_indices = {m: np.flatnonzero(months == m) for m in np.unique(months)}
    ordered = {}
    for name, score in scores.items():
        for month, ix in month_indices.items():
            keys = frame.iloc[ix][CUSTOMER].astype(str).to_numpy()
            ordered[(name, month)] = ix[np.lexsort((keys, -score[ix]))]
    rng = np.random.Generator(np.random.PCG64(seed))
    comparisons = [(m, b) for m in ("Random Forest", "HistGradientBoosting") for b in ("Logistic C", "Frequency")]
    draws = {f"{a} - {b}": {f"{int(c*100)}_{metric}": [] for c in CAPACITIES for metric in ("precision", "capture_recall")} for a,b in comparisons}
    for _ in range(reps):
        sampled = rng.integers(0, len(ids), size=len(ids))
        row_weights = np.bincount(sampled, minlength=len(ids))[customer_codes]
        summaries = {name: {cap: {"selected": 0.0, "tp": 0.0} for cap in CAPACITIES} for name in scores}
        totals = {cap: {"n": 0.0, "positive": 0.0} for cap in CAPACITIES}
        for month, ix in month_indices.items():
            wm = row_weights[ix]
            n_month = float(wm.sum()); pos_month = float(np.dot(wm, labels[ix]))
            if n_month <= 0: continue
            for cap in CAPACITIES:
                k = int(np.ceil(cap * n_month)); totals[cap]["n"] += n_month; totals[cap]["positive"] += pos_month
                for name in scores:
                    order = ordered[(name, month)]
                    weights = row_weights[order]
                    before = np.cumsum(weights) - weights
                    selected_weights = np.minimum(weights, np.maximum(0.0, k - before))
                    summaries[name][cap]["selected"] += k
                    summaries[name][cap]["tp"] += float(np.dot(selected_weights, labels[order]))
        for (a,b) in comparisons:
            key = f"{a} - {b}"
            for cap in CAPACITIES:
                tag = str(int(cap*100))
                va = summaries[a][cap]; vb = summaries[b][cap]
                pa, pb = va["tp"] / va["selected"], vb["tp"] / vb["selected"]
                ca = va["tp"] / totals[cap]["positive"]
                cb = vb["tp"] / totals[cap]["positive"]
                for metric in ("precision", "capture_recall"):
                    draws[key][f"{tag}_{metric}"].append((pa - pb) if metric == "precision" else (ca - cb))
    result = {}
    for key, metrics in draws.items():
        result[key] = {}
        for metric, vals in metrics.items():
            lo, hi = np.percentile(vals, [2.5, 97.5])
            result[key][metric] = {"estimate": float(np.mean(vals)), "ci95": [float(lo), float(hi)]}
    return {"method": f"paired customer-trajectory percentile bootstrap; {reps} reps", "seed": seed, "comparisons": result,
            "warning": "Intervals condition on evaluated periods and the deterministic customer-key tie policy."}


def _estimator(family: str, params: dict[str, Any], seed: int) -> Pipeline:
    if family == "Random Forest":
        estimator = RandomForestClassifier(**params, random_state=seed, n_jobs=1)
    else:
        estimator = HistGradientBoostingClassifier(**{**params, "early_stopping": False}, random_state=seed)
    return tree_pipeline(estimator)


def run(dataset_path: Path, manifest_path: Path, models_path: Path, run_manifest_path: Path,
        predictions_path: Path, output_dir: Path) -> dict[str, Any]:
    from monthly_purchase_baselines import verify_frozen_inputs
    # Verify all frozen artifacts before reading cohort/predictions.
    if sha256_file(models_path) != "e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f":
        raise ValueError("Frozen model artifact hash mismatch.")
    if sha256_file(run_manifest_path) != "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a":
        raise ValueError("Frozen run manifest hash mismatch.")
    if sha256_file(predictions_path) != EXPECTED_PREDICTIONS_SHA256:
        raise ValueError("Frozen prediction artifact hash mismatch.")
    _, cohort = verify_frozen_inputs(dataset_path, manifest_path)
    predictions = pd.read_parquet(predictions_path)
    for f in (cohort, predictions): f[DECISION] = pd.to_datetime(f[DECISION])
    if cohort.duplicated([CUSTOMER, DECISION]).any(): raise ValueError("Duplicate cohort snapshot keys.")
    if tuple(json.loads(manifest_path.read_text())["feature_columns"]) != tuple(FEATURE_COLUMNS): raise ValueError("Feature allowlist mismatch.")
    if any(x in FEATURE_COLUMNS for x in (CUSTOMER, LABEL, DECISION, MONTH, "evaluation_partition")): raise ValueError("Leakage column in feature contract.")
    test = cohort.loc[cohort.evaluation_partition.eq("test")].copy()
    frozen = predictions[[CUSTOMER, DECISION, LABEL, MODEL_C]].copy()
    test = test.merge(frozen, on=[CUSTOMER, DECISION], how="left", validate="one_to_one", suffixes=("", "_frozen"))
    if len(test) != 21672 or not test[LABEL].eq(test[f"{LABEL}_frozen"]).all(): raise ValueError("Frozen holdout predictions misaligned.")
    test = test.reset_index(drop=True)
    test["_frozen_c"] = test[MODEL_C]
    test.drop(columns=[f"{LABEL}_frozen", MODEL_C], inplace=True)
    folds = make_folds(cohort)
    if len(folds) != 4: raise ValueError(f"Expected four feasible pre-holdout origins, found {len(folds)}.")
    search = {"Random Forest": RF_GRID, "HistGradientBoosting": HGB_GRID}
    fold_scores: dict[str, dict[str, dict[str, np.ndarray]]] = {name: {} for name in [*search]}
    config_rows = []
    timings = []
    start_all = time.perf_counter()
    for fold in folds:
        tr, va, month = fold["train"], fold["validation"], fold["month"]
        if tr[DECISION].max() >= fold["boundary"] or tr["outcome_window_end_exclusive"].max() >= fold["boundary"]:
            raise ValueError("Actual timestamp maturity check failed.")
        base = {"Logistic C": logistic_fit_predict(tr, va), "Frequency": va[FREQ].to_numpy(float)}
        fold_scores.setdefault("base", {})[month] = base
        for family, grid in search.items():
            for config_no, params in enumerate(grid):
                model = _estimator(family, params, SEED)
                t0 = time.perf_counter()
                model.fit(tr.loc[:, list(FEATURE_COLUMNS)], tr[LABEL].to_numpy(int))
                score = model.predict_proba(va.loc[:, list(FEATURE_COLUMNS)])[:, 1]
                elapsed = time.perf_counter() - t0
                name = f"{family}#{config_no}"
                fold_scores.setdefault(name, {})[month] = {"score": score}
                timings.append({"family": family, "config": config_no, "fold": month, "seconds": elapsed})
                config_rows.append({"family": family, "config": config_no, "parameters": params,
                                    "fold": month, "n_train": len(tr), "n_train_customers": int(tr[CUSTOMER].nunique()),
                                    "n_validation": len(va), "score": _metrics(va[LABEL].to_numpy(int), score, probability=True)})
    # Select by mean fold AP only; selection uses development outcomes exclusively.
    selected = {}
    for family in search:
        candidates = [r for r in config_rows if r["family"] == family]
        means = {r["config"]: float(np.mean([x["score"]["average_precision"] for x in candidates if x["config"] == r["config"]])) for r in candidates}
        chosen = max(means, key=lambda c: (means[c], -c))
        selected[family] = {"config_index": chosen, "parameters": search[family][chosen], "mean_fold_average_precision": means[chosen]}
    # Development fold reports: baseline and each family’s selected configuration.
    fold_results = []
    for fold in folds:
        month, va = fold["month"], fold["validation"]
        scores = {"Logistic C": fold_scores["base"][month]["Logistic C"],
                  "Frequency": fold_scores["base"][month]["Frequency"]}
        for family in search:
            scores[family] = fold_scores[f"{family}#{selected[family]['config_index']}"][month]["score"]
        fold_results.append({"month": month, "train_snapshots": len(fold["train"]),
                             "train_customers": int(fold["train"][CUSTOMER].nunique()),
                             "train_months": sorted(fold["train"][MONTH].unique().tolist()),
                             "training_max_decision": str(fold["train"][DECISION].max()),
                             "training_max_label_end": str(fold["train"]["outcome_window_end_exclusive"].max()),
                             "validation": evaluate_frame(va, scores)})
    # Concatenate four out-of-fold months for pooled developmental summaries.
    combined_frames = [f["validation"] for f in folds]
    combined = pd.concat(combined_frames, ignore_index=True)
    combined_scores = {}
    for name in ("Logistic C", "Frequency", *search.keys()):
        parts = []
        for fold in folds:
            month = fold["month"]
            if name in ("Logistic C", "Frequency"):
                parts.append(fold_scores["base"][month][name])
            else:
                parts.append(fold_scores[f"{name}#{selected[name]['config_index']}"][month]["score"])
        combined_scores[name] = np.concatenate(parts)
    dev_summary = evaluate_frame(combined, combined_scores)
    dev_bootstrap = paired_cluster_bootstrap(combined, combined_scores, reps=BOOT_REPS, seed=SEED)
    dev_ranking_bootstrap = paired_ranking_bootstrap(combined, combined_scores, reps=BOOT_REPS, seed=SEED)
    for name in ("Random Forest", "HistGradientBoosting"):
        for baseline in ("Logistic C", "Frequency"):
            comparison = dev_bootstrap["comparisons"][f"{name} - {baseline}"]
            comparison["observed_point_differences"] = {
                f"{cap}_{metric}": dev_summary["models"][name]["crm"][cap][metric]
                - dev_summary["models"][baseline]["crm"][cap][metric]
                for cap in ("5", "10", "20") for metric in ("precision", "capture_recall")
            }
    # Exploratory holdout: fit selected estimators once on frozen Jan-Jun training.
    train = cohort.loc[cohort.evaluation_partition.eq("train")].copy()
    if not (pd.to_datetime(train.outcome_window_end_exclusive) <= pd.Timestamp("2011-07-01")).all(): raise ValueError("M2 training maturity cutoff violated.")
    exploratory = {"Logistic C": test["_frozen_c"].to_numpy(float), "Frequency": test[FREQ].to_numpy(float)}
    for family in search:
        model = _estimator(family, selected[family]["parameters"], SEED)
        t0 = time.perf_counter(); model.fit(train.loc[:, list(FEATURE_COLUMNS)], train[LABEL].to_numpy(int)); elapsed = time.perf_counter()-t0
        exploratory[family] = model.predict_proba(test.loc[:, list(FEATURE_COLUMNS)])[:, 1]
        timings.append({"family": family, "config": selected[family]["config_index"], "fold": "holdout_fit", "seconds": elapsed})
    holdout_eval = evaluate_frame(test, exploratory)
    # Verify the frozen Model C probabilities still reproduce the published M2-008 result.
    frozen_metrics = holdout_eval["models"]["Logistic C"]
    expected = {"roc_auc": 0.7659859786206419, "average_precision": 0.5659489004, "brier_score": 0.1474375620}
    for metric, target in expected.items():
        if not np.isclose(frozen_metrics[metric], target, atol=1e-9, rtol=0):
            raise ValueError(f"Frozen Model C {metric} no longer reproduces M2-008.")
    holdout_eval["monthly"] = []
    for month, idx in test.groupby(MONTH, sort=True).groups.items():
        subset = test.loc[list(idx)].reset_index(drop=True)
        scores = {name: score[np.asarray(list(idx), dtype=int)] for name, score in exploratory.items()}
        holdout_eval["monthly"].append({"month": str(month), "evaluation": evaluate_frame(subset, scores)})
    # Bootstrap key paired CRM differences over customer trajectories.
    bootstrap = paired_cluster_bootstrap(test, exploratory, reps=BOOT_REPS, seed=SEED)
    holdout_ranking_bootstrap = paired_ranking_bootstrap(test, exploratory, reps=BOOT_REPS, seed=SEED)
    for name in ("Random Forest", "HistGradientBoosting"):
        bootstrap["comparisons"][f"{name} - Logistic C"]["observed_point_differences"] = {
            f"{cap}_{metric}": holdout_eval["models"][name]["crm"][cap][metric] - holdout_eval["models"]["Logistic C"]["crm"][cap][metric]
            for cap in ("5", "10", "20") for metric in ("precision", "capture_recall")
        }
        bootstrap["comparisons"][f"{name} - Frequency"]["observed_point_differences"] = {
            f"{cap}_{metric}": holdout_eval["models"][name]["crm"][cap][metric] - holdout_eval["models"]["Frequency"]["crm"][cap][metric]
            for cap in ("5", "10", "20") for metric in ("precision", "capture_recall")
        }
    total_seconds = time.perf_counter() - start_all
    result = {
        "experiment": "COMMERCIAL_DS_P3_002", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed; published holdout comparison is exploratory",
        "provenance": {"dataset_sha256": sha256_file(dataset_path), "source_manifest_sha256": sha256_file(manifest_path),
                       "frozen_predictions_sha256": sha256_file(predictions_path),
                       "frozen_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
                       "feature_columns": list(FEATURE_COLUMNS)},
        "definition": {"target": "any qualifying purchase in [decision_time, decision_time + 30 days)",
                       "features": "11 corrected-M2 point-in-time features over prior 365 days",
                       "frequency": "qualifying_purchase_dates_365d; score only; no probability metrics",
                       "preprocessing": "log1p and training-fold median imputation; logistic uses frozen train-only standardization"},
        "folds": fold_results, "development_pooled_oof": dev_summary,
        "development_cluster_bootstrap": dev_bootstrap,
        "development_ranking_bootstrap": dev_ranking_bootstrap,
        "search": {"selection_metric": "unweighted mean fold average precision; no holdout outcomes used",
                   "configuration_count": {"Random Forest": len(RF_GRID), "HistGradientBoosting": len(HGB_GRID)},
                   "selected": selected, "all_configuration_fold_results": config_rows},
        "exploratory_published_holdout": holdout_eval,
        "exploratory_customer_cluster_bootstrap": bootstrap,
        "exploratory_ranking_bootstrap": holdout_ranking_bootstrap,
        "runtime": {"total_seconds": total_seconds, "fit_seconds_by_run": timings,
                    "number_of_candidate_fold_fits": sum(len(v)*len(folds) for v in search.values()),
                    "estimator_fit_counts": {"logistic_fold_reference": len(folds),
                                             "random_forest_candidate_cv": len(RF_GRID)*len(folds),
                                             "hist_gradient_boosting_candidate_cv": len(HGB_GRID)*len(folds),
                                             "selected_tree_final_fits": len(search),
                                             "total_estimator_fit_calls": len(folds) + sum(len(v)*len(folds) for v in search.values()) + len(search)},
                    "note": "Wall-clock timings are environment-specific; measured process peak memory is recorded separately in the research report."},
        "training_settings": {"seed": SEED, "random_forest_n_jobs": 1,
                              "hist_gradient_boosting_early_stopping": False,
                              "tree_preprocessing": "log1p; fold-local median imputation; no scaling",
                              "logistic_settings": MODEL_SETTINGS},
        "reproducibility": {"seed": SEED, "crm_bootstrap_replicates": BOOT_REPS,
                            "ranking_bootstrap_replicates": BOOT_REPS,
                            "python": sys.version.split()[0], "sklearn": __import__("sklearn").__version__,
                            "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__},
        "limitations": ["Four development origins only; one historical retail dataset and season.",
                        "Repeated customers and overlapping outcome windows; cluster bootstrap does not create new time origins.",
                        "July-November holdout has been inspected and is exploratory, not confirmatory.",
                        "Tuning over four origins may overfit the small set of periods."]
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_path = output_dir / "p3_002_aggregate_results.json"
    aggregate_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    result["artifact_sha256"] = {aggregate_path.name: sha256_file(aggregate_path)}
    (output_dir / "p3_002_manifest.json").write_text(json.dumps({"experiment": "P3-002", "aggregate": aggregate_path.name,
        "aggregate_sha256": result["artifact_sha256"][aggregate_path.name], "dataset_sha256": result["provenance"]["dataset_sha256"],
        "predictions_sha256": result["provenance"]["frozen_predictions_sha256"]}, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if ROOT in args.output_dir.resolve().parents or args.output_dir.resolve() == ROOT:
        raise ValueError("P3 aggregate/model outputs must remain outside the Git repository.")
    result = run(args.dataset, args.manifest, args.models, args.run_manifest, args.predictions, args.output_dir)
    print(json.dumps({"selected": result["search"]["selected"], "development": result["development_pooled_oof"],
                      "holdout": result["exploratory_published_holdout"], "runtime": result["runtime"]["total_seconds"]}, indent=2))


if __name__ == "__main__": main()

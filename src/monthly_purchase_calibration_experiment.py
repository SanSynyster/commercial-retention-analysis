"""Maturity-aware calibration and CRM uncertainty experiment for M2/P3."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.optimize import brentq, root
from scipy.special import expit, logit
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             log_loss, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import monthly_purchase_advanced_benchmark as p3  # noqa: E402
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256,
    LABEL_COLUMN, CUSTOMER_COLUMN,
    MONTH_COLUMN, sha256_file, verify_frozen_inputs,
)
from monthly_targeting_policies import select_ranked  # noqa: E402

LABEL, CUSTOMER, MONTH = LABEL_COLUMN, CUSTOMER_COLUMN, MONTH_COLUMN
DECISION = "decision_time"
END = "outcome_window_end_exclusive"
SEED = 20261113
GRADIENT_TOLERANCE = 1e-8  # mean negative-log-likelihood score equation
EXPECTED_PREDICTIONS_SHA256 = "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1"
EXPECTED_MODELS_SHA256 = "e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f"
EXPECTED_RUN_MANIFEST_SHA256 = "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a"
EPS = 1e-6
CAPACITIES = (0.05, 0.10, 0.20)
MODEL_NAMES = ("Random Forest", "Logistic C", "HistGradientBoosting")
METHODS = ("uncalibrated", "intercept_only", "intercept_slope", "isotonic")
DEV_MONTHS = ("2011-03", "2011-04", "2011-05", "2011-06")
EVAL_MONTHS = ("2011-04", "2011-05", "2011-06")


def clip_probability(probability: np.ndarray, eps: float = EPS) -> np.ndarray:
    p = np.asarray(probability, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Probabilities must be a finite one-dimensional vector in [0, 1].")
    return np.clip(p, eps, 1 - eps)


def positive_class_probability(estimator: Any, features: pd.DataFrame) -> np.ndarray:
    """Select probability for label 1 by class identity, not column assumption."""
    classes = np.asarray(estimator.classes_)
    match = np.flatnonzero(classes == 1)
    if len(match) != 1:
        raise ValueError("Fitted estimator must expose exactly one positive class labelled 1.")
    return estimator.predict_proba(features)[:, int(match[0])]


def fit_calibrator(kind: str, y: np.ndarray, probability: np.ndarray) -> dict[str, Any]:
    """Fit the stated map; inputs must be earlier out-of-fold predictions."""
    y = np.asarray(y, dtype=int)
    p = clip_probability(probability)
    if len(y) != len(p) or len(y) == 0 or not np.isin(y, [0, 1]).all() or np.unique(y).size != 2:
        raise ValueError("Calibration requires aligned, nonempty binary labels with both classes.")
    x = logit(p)
    if kind == "intercept_only":
        prevalence = float(y.mean())
        shift = brentq(lambda a: float(expit(x + a).mean() - prevalence), -40, 40)
        return {"kind": kind, "intercept": float(shift), "slope": 1.0, "n": len(y),
                "positives": int(y.sum()), "clip_epsilon": EPS}
    if kind == "intercept_slope":
        design = np.column_stack((np.ones(len(x)), x))
        def score(beta: np.ndarray) -> np.ndarray:
            eta = design @ beta
            return design.T @ (expit(eta) - y) / len(y)
        def jacobian(beta: np.ndarray) -> np.ndarray:
            fitted = expit(design @ beta)
            return design.T @ ((fitted*(1-fitted))[:, None] * design) / len(y)
        result = root(score, np.array([0.0, 1.0]), jac=jacobian, method="hybr", options={"xtol": 1e-10})
        beta = np.asarray(result.x, dtype=float)
        grad_norm = float(np.linalg.norm(score(beta), ord=np.inf))
        if not np.isfinite(beta).all() or np.max(np.abs(beta)) > 30 or grad_norm > GRADIENT_TOLERANCE:
            raise ValueError("Intercept-and-slope calibration failed to converge to a finite estimate.")
        return {"kind": kind, "intercept": float(beta[0]), "slope": float(beta[1]), "n": len(y),
                "positives": int(y.sum()), "clip_epsilon": EPS,
                "optimizer_success": bool(result.success), "mean_score_inf_norm": grad_norm,
                "gradient_tolerance": GRADIENT_TOLERANCE}
    if kind == "isotonic":
        if len(y) < 1000 or min(int(y.sum()), int((1-y).sum())) < 100:
            raise ValueError("Isotonic calibration requires >=1000 rows and >=100 examples per class.")
        model = IsotonicRegression(y_min=EPS, y_max=1-EPS, out_of_bounds="clip")
        model.fit(p, y)
        return {"kind": kind, "model": model, "n": len(y), "positives": int(y.sum()),
                "clip_epsilon": EPS, "threshold_count": int(len(model.X_thresholds_))}
    raise ValueError(f"Unknown calibration method: {kind}")


def apply_calibrator(calibrator: dict[str, Any], probability: np.ndarray) -> np.ndarray:
    p = clip_probability(probability)
    kind = calibrator["kind"]
    if kind == "intercept_only":
        result = expit(logit(p) + float(calibrator["intercept"]))
    elif kind == "intercept_slope":
        result = expit(float(calibrator["intercept"]) + float(calibrator["slope"]) * logit(p))
    elif kind == "isotonic":
        result = calibrator["model"].predict(p)
    else:
        raise ValueError(f"Unknown fitted calibration map: {kind}")
    return np.clip(np.asarray(result, dtype=float), EPS, 1-EPS)


def calibration_pool(prior_predictions: pd.DataFrame, boundary: pd.Timestamp) -> pd.DataFrame:
    """Earlier OOF scores with labels complete strictly before the evaluation time."""
    boundary = pd.Timestamp(boundary)
    eligible = prior_predictions.loc[
        (pd.to_datetime(prior_predictions[DECISION]) < boundary)
        & (pd.to_datetime(prior_predictions[END]) < boundary)
        & prior_predictions["outcome_window_mature"].eq(True)
        & prior_predictions["outcome_coverage_status"].eq("complete")
        & prior_predictions[LABEL].isin([0, 1])
    ].copy()
    if not (pd.to_datetime(eligible[END]) < boundary).all():
        raise ValueError("Calibration pool contains a label not mature before the evaluation boundary.")
    return eligible


def calibration_diagnostic(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=int)
    q = clip_probability(p)
    x = logit(q)
    design = np.column_stack((np.ones(len(x)), x))
    if np.unique(y).size < 2 or np.ptp(x) < 1e-12:
        return {"intercept": None, "slope": None, "status": "not_identifiable"}
    def score(beta: np.ndarray) -> np.ndarray:
        eta = design @ beta
        return design.T @ (expit(eta)-y) / len(y)
    def jacobian(beta: np.ndarray) -> np.ndarray:
        fitted = expit(design @ beta)
        return design.T @ ((fitted*(1-fitted))[:, None] * design) / len(y)
    fit = root(score, np.array([0.0, 1.0]), jac=jacobian, method="hybr", options={"xtol": 1e-10})
    beta = np.asarray(fit.x)
    score_norm = float(np.linalg.norm(score(beta), ord=np.inf))
    information = jacobian(beta)
    eig = np.linalg.eigvalsh(information)
    condition = float(eig[-1]/eig[0]) if eig[0] > 0 else None
    if (not np.isfinite(beta).all() or np.max(np.abs(beta)) > 30 or score_norm > GRADIENT_TOLERANCE
            or condition is None or condition >= 1e10 or eig[0] < 1e-10):
        return {"intercept": None, "slope": None, "status": "failed_nonstationary_or_ill_conditioned",
                "mean_score_inf_norm": score_norm, "gradient_tolerance": GRADIENT_TOLERANCE,
                "information_condition_number": condition, "optimizer_success": bool(fit.success)}
    return {"intercept": float(beta[0]), "slope": float(beta[1]),
            "status": "estimated" if fit.success else "estimated_stationary_optimizer_warning",
            "mean_score_inf_norm": score_norm, "gradient_tolerance": GRADIENT_TOLERANCE,
            "information_condition_number": condition, "optimizer_success": bool(fit.success)}


def probability_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    y, p = np.asarray(y, dtype=int), clip_probability(p)
    return {"n": len(y), "positives": int(y.sum()), "prevalence": float(y.mean()),
            "roc_auc": float(roc_auc_score(y, p)), "average_precision": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, p)), "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "mean_predicted": float(p.mean()), "calibration": calibration_diagnostic(y, p)}


def reliability_bins(frame: pd.DataFrame, prediction: str, bins: np.ndarray | None = None) -> list[dict[str, Any]]:
    edges = np.linspace(0, 1, 11) if bins is None else bins
    p = clip_probability(frame[prediction].to_numpy(float))
    index = np.minimum(np.digitize(p, edges, right=False)-1, len(edges)-2)
    result = []
    for j in range(len(edges)-1):
        rows = index == j
        if rows.any():
            result.append({"bin_lower": float(edges[j]), "bin_upper": float(edges[j+1]), "n": int(rows.sum()),
                           "mean_predicted": float(p[rows].mean()),
                           "observed_rate": float(frame[LABEL].to_numpy(int)[rows].mean())})
        else:
            result.append({"bin_lower": float(edges[j]), "bin_upper": float(edges[j+1]), "n": 0,
                           "mean_predicted": None, "observed_rate": None})
    return result


def crm_metrics(frame: pd.DataFrame, prediction: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for month, group in frame.groupby(MONTH, sort=True):
        result[str(month)] = {}
        prevalence = float(group[LABEL].mean())
        for cap in CAPACITIES:
            selected = select_ranked(group, prediction, cap, descending=True)
            precision = float(selected[LABEL].mean())
            result[str(month)][str(int(cap*100))] = {
                "selected": len(selected), "actual_capacity": len(selected)/len(group),
                "precision": precision, "capture": float(selected[LABEL].sum()/group[LABEL].sum()),
                "lift": precision/prevalence,
            }
    return result


def paired_cluster_loss_bootstrap(frame: pd.DataFrame, predictions: dict[str, np.ndarray],
                                  *, reps: int = 1000, seed: int = SEED) -> dict[str, Any]:
    ids, code = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    y = frame[LABEL].to_numpy(int)
    losses = {}
    for name, p in predictions.items():
        q = clip_probability(p)
        losses[name] = {"brier": (q-y)**2,
                        "log_loss": -(y*np.log(q)+(1-y)*np.log1p(-q))}
    rng = np.random.Generator(np.random.PCG64(seed))
    output = {}
    base = "uncalibrated"
    for model_name, values in predictions.items():
        if model_name == base:
            continue
        output[model_name] = {}
        for metric in ("brier", "log_loss"):
            diffs = np.empty(reps, dtype=float)
            for r in range(reps):
                draws = rng.integers(0, len(ids), size=len(ids))
                weights = np.bincount(draws, minlength=len(ids))[code]
                denom = weights.sum()
                diffs[r] = np.dot(weights, losses[model_name][metric]-losses[base][metric])/denom
            output[model_name][metric] = {"delta_vs_uncalibrated": float(np.mean(losses[model_name][metric]-losses[base][metric])),
                                          "ci95": [float(x) for x in np.percentile(diffs, [2.5, 97.5])],
                                          "valid_resamples": reps}
    return {"method": "paired customer-cluster percentile bootstrap on fixed predictions; 1000 draws",
            "seed": seed, "comparisons": output,
            "scope": "Conditional on fixed fitted models and temporal evaluation observations; does not represent future-period uncertainty."}


def paired_cluster_crm_bootstrap(frame: pd.DataFrame, scores: dict[str, np.ndarray],
                                 *, reps: int = 1000, seed: int = SEED) -> dict[str, Any]:
    """Paired customer resampling for monthly fixed-capacity precision and capture."""
    ids, customer_codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    y = frame[LABEL].to_numpy(int)
    months = frame[MONTH].astype(str).to_numpy()
    month_rows = {m: np.flatnonzero(months == m) for m in sorted(set(months))}
    ordered: dict[tuple[str, str], np.ndarray] = {}
    for name, score in scores.items():
        for month, ix in month_rows.items():
            customers = frame.iloc[ix][CUSTOMER].astype(str).to_numpy()
            ordered[(name, month)] = ix[np.lexsort((customers, -np.asarray(score)[ix]))]
    comparisons = [(name, "uncalibrated") for name in scores if name != "uncalibrated"]
    metrics = ("precision", "capture")
    samples = {f"{new} - uncalibrated": {f"{int(cap*100)}_{metric}": [] for cap in CAPACITIES for metric in metrics}
               for new, _ in comparisons}
    point = {}
    for new, _ in comparisons:
        point[f"{new} - uncalibrated"] = {}
        for cap in CAPACITIES:
            base_tp = new_tp = total_selected = total_positive = 0.0
            for month, ix in month_rows.items():
                k = int(np.ceil(cap*len(ix)))
                total_selected += k
                total_positive += float(y[ix].sum())
                for name, accumulator in (("uncalibrated", "base"), (new, "new")):
                    chosen = ordered[(name, month)][:k]
                    tp = float(y[chosen].sum())
                    if accumulator == "base": base_tp += tp
                    else: new_tp += tp
            point[f"{new} - uncalibrated"][f"{int(cap*100)}_precision"] = new_tp/total_selected-base_tp/total_selected
            point[f"{new} - uncalibrated"][f"{int(cap*100)}_capture"] = new_tp/total_positive-base_tp/total_positive
    rng = np.random.Generator(np.random.PCG64(seed))
    for _ in range(reps):
        draw = rng.integers(0, len(ids), size=len(ids))
        weights = np.bincount(draw, minlength=len(ids))[customer_codes]
        totals = {cap: {"selected": 0.0, "positive": 0.0} for cap in CAPACITIES}
        selected_tp = {name: {cap: 0.0 for cap in CAPACITIES} for name in scores}
        for month, ix in month_rows.items():
            for cap in CAPACITIES:
                k = int(np.ceil(cap*weights[ix].sum()))
                totals[cap]["selected"] += k
                totals[cap]["positive"] += float(np.dot(weights[ix], y[ix]))
                for name in scores:
                    order = ordered[(name, month)]
                    row_weights = weights[order]
                    before = np.cumsum(row_weights)-row_weights
                    selected_weights = np.minimum(row_weights, np.maximum(0, k-before))
                    selected_tp[name][cap] += float(np.dot(selected_weights, y[order]))
        for new, _ in comparisons:
            key = f"{new} - uncalibrated"
            for cap in CAPACITIES:
                delta_precision = (selected_tp[new][cap]-selected_tp["uncalibrated"][cap])/totals[cap]["selected"]
                delta_capture = (selected_tp[new][cap]-selected_tp["uncalibrated"][cap])/totals[cap]["positive"]
                samples[key][f"{int(cap*100)}_precision"].append(float(delta_precision))
                samples[key][f"{int(cap*100)}_capture"].append(float(delta_capture))
    intervals = {}
    for key, values in samples.items():
        intervals[key] = {}
        for metric, draws in values.items():
            intervals[key][metric] = {"point_difference": point[key][metric],
                                      "ci95": [float(v) for v in np.percentile(draws, [2.5, 97.5])],
                                      "valid_resamples": len(draws)}
    return {"method": "paired customer-cluster bootstrap; per-month capacity maintained; deterministic customer-key ties",
            "requested_resamples": reps, "seed": seed, "comparisons": intervals,
            "scope": "Conditional on fitted scores and calibration maps; does not include calibrator-estimation or future-period uncertainty."}


def _fit_model_predictions(cohort: pd.DataFrame, frozen_predictions: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    folds = p3.make_folds(cohort)
    if tuple(f["month"] for f in folds) != DEV_MONTHS:
        raise ValueError("Expected the four frozen March–June validation folds.")
    oof_parts, fit_log = [], []
    model_params = {"Random Forest": p3.RF_GRID[0], "HistGradientBoosting": p3.HGB_GRID[0]}
    started = time.perf_counter()
    for fold in folds:
        train, valid, month = fold["train"], fold["validation"], fold["month"]
        row = valid[[CUSTOMER, MONTH, DECISION, END, "outcome_window_mature", "outcome_coverage_status", LABEL]].copy()
        row["probability_Logistic C"] = p3.logistic_fit_predict(train, valid)
        fit_log.append({"model": "Logistic C", "period": month, "n_train": len(train), "n_eval": len(valid)})
        for model_name in ("Random Forest", "HistGradientBoosting"):
            model = p3._estimator(model_name, model_params[model_name], p3.SEED)
            t0 = time.perf_counter()
            model.fit(train.loc[:, list(FEATURE_COLUMNS)], train[LABEL].to_numpy(int))
            row[f"probability_{model_name}"] = positive_class_probability(model, valid.loc[:, list(FEATURE_COLUMNS)])
            fit_log.append({"model": model_name, "period": month, "fit_seconds": time.perf_counter()-t0,
                            "n_train": len(train), "n_eval": len(valid)})
        oof_parts.append(row)
    oof = pd.concat(oof_parts, ignore_index=True)
    # Fit exact accepted tree settings on the frozen January–June training partition.
    train = cohort.loc[cohort.evaluation_partition.eq("train")].copy()
    test = cohort.loc[cohort.evaluation_partition.eq("test")].copy()
    if not (pd.to_datetime(train[END]) <= pd.Timestamp("2011-07-01")).all():
        raise ValueError("Frozen M2 training population exceeds its approved as-of maturity cutoff.")
    frozen = frozen_predictions[[CUSTOMER, DECISION, LABEL, "probability_C_full_11"]].copy()
    test = test.merge(frozen, on=[CUSTOMER, DECISION], how="inner", validate="one_to_one", suffixes=("", "_saved"))
    if len(test) != 21672 or not test[LABEL].eq(test[f"{LABEL}_saved"]).all():
        raise ValueError("Frozen Logistic C predictions fail one-to-one holdout alignment.")
    test = test.drop(columns=[f"{LABEL}_saved"])
    test["probability_Logistic C"] = test["probability_C_full_11"]
    for model_name in ("Random Forest", "HistGradientBoosting"):
        model = p3._estimator(model_name, model_params[model_name], p3.SEED)
        t0 = time.perf_counter()
        model.fit(train.loc[:, list(FEATURE_COLUMNS)], train[LABEL].to_numpy(int))
        test[f"probability_{model_name}"] = positive_class_probability(model, test.loc[:, list(FEATURE_COLUMNS)])
        fit_log.append({"model": model_name, "period": "exploratory_holdout_fit", "fit_seconds": time.perf_counter()-t0,
                        "n_train": len(train), "n_eval": len(test)})
    fit_log.append({"model": "Logistic C", "period": "exploratory_holdout", "source": "frozen M2-008 predictions",
                    "n_train": len(train), "n_eval": len(test)})
    test = test[[CUSTOMER, MONTH, DECISION, END, "outcome_window_mature", "outcome_coverage_status", LABEL,
                 *[f"probability_{name}" for name in MODEL_NAMES]]].copy()
    return oof, fit_log, {"test": test, "runtime_seconds": time.perf_counter()-started,
                          "model_parameters": model_params, "folds": folds}


def _records_for_period(frame: pd.DataFrame, models: tuple[str, ...] = MODEL_NAMES) -> dict[str, Any]:
    out = {}
    for model in models:
        pcol = f"probability_{model}"
        out[model] = {"metrics": probability_metrics(frame[LABEL].to_numpy(int), frame[pcol].to_numpy(float)),
                      "calibration_bins": reliability_bins(frame, pcol),
                      "crm": crm_metrics(frame, pcol)}
    return out


def threshold_diagnostic(frame: pd.DataFrame, score_col: str, threshold: float = 0.20) -> dict[str, Any]:
    result = {}
    for month, part in frame.groupby(MONTH, sort=True):
        chosen = part[score_col].to_numpy(float) >= threshold
        result[str(month)] = {"threshold": threshold, "selected_n": int(chosen.sum()),
                              "selected_share": float(chosen.mean()),
                              "precision": float(part[LABEL].to_numpy(int)[chosen].mean()) if chosen.any() else None,
                              "capture": float(part[LABEL].to_numpy(int)[chosen].sum()/part[LABEL].sum()) if chosen.any() else 0.0}
    return result


def run_experiment(cohort: pd.DataFrame, frozen_predictions: pd.DataFrame,
                   output_dir: Path, *, bootstrap_reps: int = 1000) -> dict[str, Any]:
    started = time.perf_counter()
    oof, fit_log, full = _fit_model_predictions(cohort, frozen_predictions)
    holdout = full["test"]
    prediction_frames: list[pd.DataFrame] = []
    eval_frames: dict[str, list[pd.DataFrame]] = {model: [] for model in MODEL_NAMES}
    selected_calibration: dict[str, Any] = {}
    fold_schedule = []
    calibration_audit = []
    for month in EVAL_MONTHS:
        val = oof.loc[oof[MONTH].eq(month)].copy()
        boundary = pd.to_datetime(val[DECISION]).min()
        pool = calibration_pool(oof.loc[oof[MONTH].ne(month)], boundary)
        if pool.empty or pool[MONTH].astype(str).max() >= month:
            raise ValueError("Calibration pool is empty or not strictly earlier than evaluation month.")
        if val[LABEL].isna().any() or not val["outcome_window_mature"].all():
            raise ValueError("Evaluation labels are not fully mature binary outcomes.")
        fold_schedule.append({"evaluation_month": month, "evaluation_boundary": str(boundary),
                              "calibration_months": sorted(pool[MONTH].astype(str).unique().tolist()),
                              "calibration_n": len(pool), "calibration_positive": int(pool[LABEL].sum()),
                              "calibration_customers": int(pool[CUSTOMER].nunique()),
                              "latest_calibration_label_end": str(pd.to_datetime(pool[END]).max()),
                              "evaluation_n": len(val), "evaluation_positive": int(val[LABEL].sum()),
                              "maturity_rule": "strict outcome_window_end_exclusive < evaluation decision time"})
        for model in MODEL_NAMES:
            pred_col = f"probability_{model}"
            pool_y = pool[LABEL].to_numpy(int)
            pool_p = pool[pred_col].to_numpy(float)
            calibs = {"uncalibrated": None}
            for method in METHODS[1:]:
                fitted = fit_calibrator(method, pool_y, pool_p)
                if method == "isotonic" and fitted["n"] < 1000:
                    raise AssertionError("Isotonic feasibility rule violated.")
                calibs[method] = fitted
                calibration_audit.append({"evaluation_month": month, "model": model, "method": method,
                                          **{k:v for k,v in fitted.items() if k != "model"}})
            for method, cal in calibs.items():
                scored = val[[CUSTOMER, MONTH, DECISION, END, "outcome_window_mature", "outcome_coverage_status", LABEL]].copy()
                base_p = val[pred_col].to_numpy(float)
                scored["probability_uncalibrated"] = clip_probability(base_p)
                scored[f"probability_{method}"] = (clip_probability(base_p) if cal is None else apply_calibrator(cal, base_p))
                scored["model"] = model
                scored["calibration_method"] = method
                eval_frames[model].append(scored)
                prediction_frames.append(scored)
        # store calibration and validation row counts, never use this eval outcome here.
    dev_eval = pd.concat([f for model in MODEL_NAMES for f in eval_frames[model]], ignore_index=True)
    # Fit final dev-only calibrators on March-May OOF observations for the strictly later July holdout.
    july_boundary = pd.Timestamp("2011-07-01")
    dev_pool = calibration_pool(oof, july_boundary)
    if set(dev_pool[MONTH].astype(str).unique()) != {"2011-03", "2011-04", "2011-05"}:
        raise ValueError("Expected only March-May OOF labels to mature strictly before July 1.")
    exploratory_rows = []
    holdout_calibration = {}
    for model in MODEL_NAMES:
        pcol = f"probability_{model}"
        for method in METHODS:
            if method == "uncalibrated":
                cal = None
            else:
                cal = fit_calibrator(method, dev_pool[LABEL].to_numpy(int), dev_pool[pcol].to_numpy(float))
            p = holdout[pcol].to_numpy(float) if cal is None else apply_calibrator(cal, holdout[pcol].to_numpy(float))
            score_frame = holdout[[CUSTOMER, MONTH, DECISION, END, "outcome_window_mature", "outcome_coverage_status", LABEL]].copy()
            score_frame[f"probability_{method}"] = clip_probability(p)
            score_frame["model"] = model
            score_frame["calibration_method"] = method
            exploratory_rows.append(score_frame)
            holdout_calibration[f"{model}|{method}"] = {"calibration_n": len(dev_pool), "calibration_positive": int(dev_pool[LABEL].sum()),
                                                         "calibration_months": ["2011-03", "2011-04", "2011-05"],
                                                         "parameters": {k:v for k,v in (cal or {}).items() if k != "model"}}
    exploratory = pd.concat(exploratory_rows, ignore_index=True)

    # Summary values are generated from the saved prediction rows below.
    def summarize(data: pd.DataFrame, score_col: str) -> dict[str, Any]:
        result = {"pooled": probability_metrics(data[LABEL].to_numpy(int), data[score_col].to_numpy(float)),
                  "calibration_bins": reliability_bins(data, score_col),
                  "monthly": {}, "monthly_calibration_bins": {}, "crm_monthly": {},
                  "monthly_score_distribution": {}, "threshold_0_20": threshold_diagnostic(data, score_col)}
        for month, part in data.groupby(MONTH, sort=True):
            result["monthly"][str(month)] = probability_metrics(part[LABEL].to_numpy(int), part[score_col].to_numpy(float))
            result["monthly_calibration_bins"][str(month)] = reliability_bins(part, score_col)
            result["crm_monthly"][str(month)] = crm_metrics(part, score_col)[str(month)]
            result["monthly_score_distribution"][str(month)] = {
                str(q): float(part[score_col].quantile(q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
        result["crm_pooled_equal_month_mean"] = {
            str(int(cap*100)): {metric: float(np.mean([result["crm_monthly"][m][str(int(cap*100))][metric] for m in result["crm_monthly"]]))
                               for metric in ("precision", "capture", "lift")}
            for cap in CAPACITIES}
        return result

    dev_summary: dict[str, Any] = {}
    for model in MODEL_NAMES:
        for method in METHODS:
            rows = dev_eval.loc[(dev_eval.model.eq(model)) & (dev_eval.calibration_method.eq(method))].copy()
            dev_summary[f"{model}|{method}"] = summarize(rows, f"probability_{method}")
    holdout_summary: dict[str, Any] = {}
    for model in MODEL_NAMES:
        for method in METHODS:
            rows = exploratory.loc[(exploratory.model.eq(model)) & (exploratory.calibration_method.eq(method))].copy()
            holdout_summary[f"{model}|{method}"] = summarize(rows, f"probability_{method}")
    bootstrap: dict[str, Any] = {}
    crm_bootstrap: dict[str, Any] = {}
    for model in MODEL_NAMES:
        rows = dev_eval.loc[(dev_eval.model.eq(model)) & (dev_eval.calibration_method.eq("uncalibrated"))].copy()
        pred = {"uncalibrated": rows["probability_uncalibrated"].to_numpy(float)}
        for method in METHODS[1:]:
            calibrated = dev_eval.loc[(dev_eval.model.eq(model)) & (dev_eval.calibration_method.eq(method))].copy()
            # All per-method rows retain the same month/customer ordering.
            calibrated = calibrated.set_index([MONTH, CUSTOMER]).loc[rows.set_index([MONTH, CUSTOMER]).index].reset_index()
            pred[method] = calibrated[f"probability_{method}"].to_numpy(float)
        bootstrap[model] = paired_cluster_loss_bootstrap(rows, pred, reps=bootstrap_reps, seed=SEED)
        crm_bootstrap[model] = paired_cluster_crm_bootstrap(rows, pred, reps=bootstrap_reps, seed=SEED)

    # Predeclared 20% probability cutoff as descriptive volume/yield diagnostic; not cost-optimal.
    dev_threshold = {f"{model}|{method}": threshold_diagnostic(
        dev_eval.loc[(dev_eval.model.eq(model)) & (dev_eval.calibration_method.eq(method))],
        f"probability_{method}") for model in MODEL_NAMES for method in METHODS}
    holdout_threshold = {f"{model}|{method}": threshold_diagnostic(
        exploratory.loc[(exploratory.model.eq(model)) & (exploratory.calibration_method.eq(method))],
        f"probability_{method}") for model in MODEL_NAMES for method in METHODS}

    result = {
        "experiment": "COMMERCIAL_DS_P3_005", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed; development is limited chronological validation; July-November is exploratory",
        "definition": {"target": "qualifying purchase in [decision_time, decision_time + 30 days)",
                       "history": "existing 365-day point-in-time window and frozen 11-feature M2 contract",
                       "calibration_clip_epsilon": EPS,
                       "methods": {"uncalibrated": "accepted classifier probability", "intercept_only": "fit additive logit shift to earlier prediction labels",
                                   "intercept_slope": "unpenalized logistic recalibration of logit(clipped base probability)",
                                   "isotonic": "monotone isotonic regression; eligible at n>=1000 and >=100 per class"},
                       "tie_rule": "exact monthly capacity; descending score then customer identifier ascending",
                       "threshold_diagnostic": "fixed P>=0.20 descriptive rule; not selected from outcomes or asserted utility-optimal"},
        "development_schedule": fold_schedule,
        "development_evaluation": {"observation_unit": "mature OOF snapshots from April-June; calibration periods are strictly earlier",
                                   "calibration_pool_for_july": {"n": len(dev_pool), "positives": int(dev_pool[LABEL].sum()),
                                       "customers": int(dev_pool[CUSTOMER].nunique()), "months": sorted(dev_pool[MONTH].astype(str).unique().tolist()),
                                       "latest_label_end": str(pd.to_datetime(dev_pool[END]).max()),
                                       "rule": "strict label_end < 2011-07-01"},
                                   "models": dev_summary, "paired_customer_bootstrap": bootstrap,
                                   "paired_crm_customer_bootstrap": crm_bootstrap,
                                   "threshold_diagnostic": {"rule": "fixed P>=0.20; descriptive only, not a utility-optimal threshold", "monthly": dev_threshold}},
        "exploratory_published_holdout": {"warning": "July-November outcomes were examined previously; no holdout labels were used to fit calibration maps, select methods, thresholds, or models.",
                                          "calibration": holdout_calibration, "models": holdout_summary,
                                          "threshold_diagnostic": {"rule": "fixed P>=0.20; descriptive only", "monthly": holdout_threshold}},
        "calibration_fit_audit": calibration_audit,
        "fit_log": fit_log,
        "runtime": {"experiment_seconds": time.perf_counter()-started, "model_prediction_seconds": full["runtime_seconds"],
                    "estimator_fit_calls": 14, "fit_audit_rows": len(fit_log),
                    "fit_count_note": "14 classifier fits: 12 fold fits (3 models x 4 folds) plus 2 Jan-Jun tree fits; Logistic C holdout reused frozen M2 prediction.",
                    "peak_rss_bytes": None, "rss_note": "Peak process RSS must be captured by the invoking shell/time utility."},
        "provenance": {"dataset_sha256": EXPECTED_DATASET_SHA256, "manifest_sha256": EXPECTED_MANIFEST_SHA256,
                       "frozen_predictions_sha256": EXPECTED_PREDICTIONS_SHA256, "frozen_models_sha256": EXPECTED_MODELS_SHA256,
                       "frozen_run_manifest_sha256": EXPECTED_RUN_MANIFEST_SHA256,
                       "feature_columns": list(FEATURE_COLUMNS), "seed": SEED,
                       "accepted_tree_configs": {k: v for k,v in {"Random Forest": p3.RF_GRID[0], "HistGradientBoosting": p3.HGB_GRID[0]}.items()},
                       "packages": {"numpy": np.__version__, "pandas": pd.__version__,
                                    "scipy": scipy.__version__, "scikit_learn": sklearn.__version__}},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("p3_005_aggregate_results.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    private = output_dir / "private"
    private.mkdir(parents=True, exist_ok=True)
    # Save only to external source_data. Customer IDs and predictions never enter Git.
    pd.concat(prediction_frames, ignore_index=True).to_parquet(private / "p3_005_development_calibration_predictions.parquet", index=False)
    exploratory.to_parquet(private / "p3_005_exploratory_holdout_predictions.parquet", index=False)
    pd.concat([oof, holdout], ignore_index=True).to_parquet(private / "p3_005_base_oof_and_holdout_scores.parquet", index=False)
    plot_reliability(dev_summary, holdout_summary, output_dir)
    manifest = {"experiment": "P3-005", "aggregate_sha256": sha256_file(output_dir / "p3_005_aggregate_results.json"),
                "private_prediction_files": ["private/p3_005_development_calibration_predictions.parquet",
                                             "private/p3_005_exploratory_holdout_predictions.parquet",
                                             "private/p3_005_base_oof_and_holdout_scores.parquet"],
                "dataset_sha256": EXPECTED_DATASET_SHA256, "seed": SEED}
    output_dir.joinpath("p3_005_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return result


def plot_reliability(dev_summary: dict[str, Any], holdout_summary: dict[str, Any], output_dir: Path) -> None:
    colors = {"uncalibrated": "#333333", "intercept_only": "#0072B2", "intercept_slope": "#D55E00", "isotonic": "#009E73"}
    for model in MODEL_NAMES:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
        for ax, summary, title in ((axes[0], dev_summary, "Development: April–June"),
                                   (axes[1], holdout_summary, "Exploratory July–November")):
            for method in METHODS:
                item = summary[f"{model}|{method}"]["calibration_bins"]
                pts = [(b["mean_predicted"], b["observed_rate"]) for b in item if b["n"] > 0]
                if pts:
                    ax.plot([x[0] for x in pts], [x[1] for x in pts], marker="o", label=method.replace("_", " "), color=colors[method])
            ax.plot([0,1],[0,1], linestyle="--", color="0.6", linewidth=1)
            ax.set(xlim=(0,1), ylim=(0,1), xlabel="Mean predicted probability", ylabel="Observed purchase rate", title=title)
            ax.grid(alpha=.2)
        axes[0].legend(fontsize=7)
        fig.suptitle(f"{model}: calibration comparison")
        fig.savefig(ROOT / "docs/research/figures" / f"p3_005_calibration_{model.lower().replace(' ', '_')}.png", dpi=160)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    data_root = ROOT.parent / "source_data/uci_online_retail_ii"
    parser.add_argument("--dataset", type=Path, default=data_root / "monthly_customer_snapshots_m2_004.parquet")
    parser.add_argument("--manifest", type=Path, default=data_root / "monthly_customer_snapshots_m2_004.parquet.manifest.json")
    parser.add_argument("--predictions", type=Path, default=data_root / "m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_test_predictions.parquet")
    parser.add_argument("--models", type=Path, default=data_root / "m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_models.json")
    parser.add_argument("--run-manifest", type=Path, default=data_root / "m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json")
    parser.add_argument("--output-dir", type=Path, default=data_root / "p3_005_outputs")
    parser.add_argument("--bootstrap-reps", type=int, default=1000)
    args = parser.parse_args()
    if ROOT in args.output_dir.resolve().parents or args.output_dir.resolve() == ROOT:
        raise ValueError("P3-005 outputs must remain outside the Git repository.")
    if sha256_file(args.predictions) != EXPECTED_PREDICTIONS_SHA256 or sha256_file(args.models) != EXPECTED_MODELS_SHA256 or sha256_file(args.run_manifest) != EXPECTED_RUN_MANIFEST_SHA256:
        raise ValueError("Frozen M2-008 prediction/model artifacts do not match accepted hashes.")
    _, cohort = verify_frozen_inputs(args.dataset, args.manifest)
    frozen_predictions = pd.read_parquet(args.predictions)
    frozen_predictions[DECISION] = pd.to_datetime(frozen_predictions[DECISION])
    result = run_experiment(cohort, frozen_predictions, args.output_dir, bootstrap_reps=args.bootstrap_reps)
    print(json.dumps({"status": result["status"], "runtime": result["runtime"],
                      "development_schedule": result["development_schedule"]}, indent=2))


if __name__ == "__main__":
    main()

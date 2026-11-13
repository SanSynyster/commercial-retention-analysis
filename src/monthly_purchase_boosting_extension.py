"""Bounded XGBoost/LightGBM extension to the frozen P3-002 M2 benchmark."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

import lightgbm
import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import monthly_purchase_advanced_benchmark as p3  # noqa: E402
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256, LABEL_COLUMN,
    CUSTOMER_COLUMN, MONTH_COLUMN, sha256_file,
)
from monthly_targeting_policies import (  # noqa: E402
    FREQUENCY, MODEL_C,
)

LABEL = LABEL_COLUMN
CUSTOMER = CUSTOMER_COLUMN
MONTH = MONTH_COLUMN
DECISION = "decision_time"
FREQ = FREQUENCY
SEED = 20261113
BOOT_REPS = 1000
CAPACITIES = (0.05, 0.10, 0.20)
EXPECTED_M2_PREDICTIONS = "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1"
EXPECTED_M2_MODELS = "e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f"
EXPECTED_M2_RUN_MANIFEST = "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a"
EXPECTED_P3_AGGREGATE = "f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb"

# Predeclared before fitting: three small, CPU-only configurations per family.
XGB_GRID = [
    {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 150, "min_child_weight": 5,
     "subsample": 0.80, "colsample_bytree": 0.80, "reg_alpha": 0.0, "reg_lambda": 2.0},
    {"learning_rate": 0.03, "max_depth": 4, "n_estimators": 250, "min_child_weight": 10,
     "subsample": 0.85, "colsample_bytree": 0.80, "reg_alpha": 0.1, "reg_lambda": 5.0},
    {"learning_rate": 0.10, "max_depth": 2, "n_estimators": 100, "min_child_weight": 1,
     "subsample": 0.80, "colsample_bytree": 0.90, "reg_alpha": 0.0, "reg_lambda": 1.0},
]
LGB_GRID = [
    {"learning_rate": 0.05, "num_leaves": 7, "n_estimators": 100, "min_child_samples": 50,
     "colsample_bytree": 0.80, "subsample": 0.80, "subsample_freq": 1,
     "reg_alpha": 0.0, "reg_lambda": 2.0},
    {"learning_rate": 0.03, "num_leaves": 15, "n_estimators": 200, "min_child_samples": 50,
     "colsample_bytree": 0.90, "subsample": 0.90, "subsample_freq": 1,
     "reg_alpha": 0.1, "reg_lambda": 5.0},
    {"learning_rate": 0.10, "num_leaves": 7, "n_estimators": 100, "min_child_samples": 100,
     "colsample_bytree": 0.80, "subsample": 0.80, "subsample_freq": 1,
     "reg_alpha": 0.0, "reg_lambda": 1.0},
]


def select_by_development_ap(records: list[dict[str, Any]], family: str, n_configs: int) -> dict[str, Any]:
    """Select by mean validation-month AP only; this function accepts no holdout data."""
    expected_folds = {"2011-03", "2011-04", "2011-05", "2011-06"}
    means: dict[int, float] = {}
    for config in range(n_configs):
        matching = [r for r in records if r["family"] == family and r["config_index"] == config]
        if len(matching) != 4 or {r["fold"] for r in matching} != expected_folds:
            raise ValueError("Each configuration must have one AP result for each of four development folds.")
        values = [r["average_precision"] for r in matching]
        means[config] = float(np.mean(values))
    selected = max(means, key=lambda index: (means[index], -index))
    return {"config_index": selected, "mean_fold_average_precision": means[selected],
            "all_config_mean_average_precision": {str(i): means[i] for i in range(n_configs)}}


def _model(family: str, config: dict[str, Any], seed: int = SEED) -> Pipeline:
    if family == "XGBoost":
        estimator = XGBClassifier(
            **config, objective="binary:logistic", eval_metric="logloss", tree_method="hist",
            device="cpu", n_jobs=1, random_state=seed, verbosity=0,
            early_stopping_rounds=None,
        )
    elif family == "LightGBM":
        estimator = LGBMClassifier(
            **config, objective="binary", n_jobs=1, random_state=seed, deterministic=True,
            force_col_wise=True, verbosity=-1,
        )
    elif family in ("Random Forest", "HistGradientBoosting"):
        return p3._estimator(family, config, seed)
    else:
        raise ValueError(f"Unknown classifier family: {family}")
    return p3.tree_pipeline(estimator)


def _fit_predict(family: str, config: dict[str, Any], train: pd.DataFrame,
                 scored: pd.DataFrame) -> tuple[np.ndarray, dict[str, float]]:
    estimator = _model(family, config)
    x_train = train.loc[:, list(FEATURE_COLUMNS)]
    y_train = train[LABEL].to_numpy(int)
    x_score = scored.loc[:, list(FEATURE_COLUMNS)]
    fit_start = time.perf_counter()
    estimator.fit(x_train, y_train)
    fit_s = time.perf_counter() - fit_start
    predict_start = time.perf_counter()
    probability = estimator.predict_proba(x_score)[:, 1]
    predict_s = time.perf_counter() - predict_start
    return probability, {"fit_seconds": fit_s, "predict_seconds": predict_s}


def _pairwise_cluster_bootstrap(frame: pd.DataFrame, scores: dict[str, np.ndarray], pairs: list[tuple[str, str]],
                                *, reps: int = BOOT_REPS, seed: int = SEED) -> dict[str, Any]:
    ids, customer_codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    y = frame[LABEL].to_numpy(int)
    unique_groups: dict[str, tuple[np.ndarray, int]] = {}
    for model, score in scores.items():
        _, ascending = np.unique(score, return_inverse=True)
        count = int(ascending.max()) + 1
        unique_groups[model] = (count - 1 - ascending, count)
    point = {}
    samples = {f"{model} - {baseline}": {metric: [] for metric in ("roc_auc", "average_precision")}
               for model, baseline in pairs}
    for model, baseline in pairs:
        point[f"{model} - {baseline}"] = {
            "roc_auc": float(roc_auc_score(y, scores[model]) - roc_auc_score(y, scores[baseline])),
            "average_precision": float(average_precision_score(y, scores[model]) - average_precision_score(y, scores[baseline])),
        }
    rng = np.random.Generator(np.random.PCG64(seed))
    valid = 0
    for _ in range(reps):
        draws = rng.integers(0, len(ids), size=len(ids))
        weights = np.bincount(draws, minlength=len(ids))[customer_codes]
        active = weights > 0
        if np.unique(y[active]).size < 2:
            continue
        valid += 1
        for model, baseline in pairs:
            a = p3._grouped_weighted_ranking_metrics(y, weights, *unique_groups[model])
            b = p3._grouped_weighted_ranking_metrics(y, weights, *unique_groups[baseline])
            key = f"{model} - {baseline}"
            for metric in samples[key]:
                samples[key][metric].append(a[metric] - b[metric])
    result = {}
    for pair, metrics in samples.items():
        result[pair] = {}
        for metric, values in metrics.items():
            low, high = np.percentile(values, [2.5, 97.5])
            result[pair][metric] = {"point_difference": point[pair][metric],
                                    "ci95": [float(low), float(high)], "valid_resamples": len(values)}
    return {"method": "paired customer-trajectory percentile bootstrap with customer multiplicity weights",
            "requested_resamples": reps, "valid_resamples": valid, "seed": seed,
            "comparisons": result,
            "scope": "Conditional on fitted scores and selected configurations; no hyperparameter-selection or future-period uncertainty."}


def _crm_bootstrap(frame: pd.DataFrame, scores: dict[str, np.ndarray], pairs: list[tuple[str, str]],
                   *, reps: int = BOOT_REPS, seed: int = SEED) -> dict[str, Any]:
    ids, customer_codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    labels = frame[LABEL].to_numpy(int)
    months = frame[MONTH].astype(str).to_numpy()
    month_indices = {m: np.flatnonzero(months == m) for m in np.unique(months)}
    ordered = {}
    for model, score in scores.items():
        for month, idx in month_indices.items():
            customers = frame.iloc[idx][CUSTOMER].astype(str).to_numpy()
            ordered[(model, month)] = idx[np.lexsort((customers, -score[idx]))]
    measures = ("precision", "capture_recall")
    samples = {f"{model} - {base}": {f"{int(c*100)}_{m}": [] for c in CAPACITIES for m in measures}
               for model, base in pairs}
    rng = np.random.Generator(np.random.PCG64(seed))
    for _ in range(reps):
        draws = rng.integers(0, len(ids), size=len(ids))
        weights = np.bincount(draws, minlength=len(ids))[customer_codes]
        summary = {name: {c: {"selected": 0.0, "tp": 0.0} for c in CAPACITIES} for name in scores}
        totals = {c: {"n": 0.0, "positive": 0.0} for c in CAPACITIES}
        for month, idx in month_indices.items():
            month_weights = weights[idx]
            n_month = float(month_weights.sum())
            if not n_month:
                continue
            pos_month = float(np.dot(month_weights, labels[idx]))
            for cap in CAPACITIES:
                k = int(np.ceil(cap * n_month))
                totals[cap]["n"] += n_month
                totals[cap]["positive"] += pos_month
                for name in scores:
                    order = ordered[(name, month)]
                    w_order = weights[order]
                    before = np.cumsum(w_order) - w_order
                    chosen_weight = np.minimum(w_order, np.maximum(0.0, k - before))
                    summary[name][cap]["selected"] += k
                    summary[name][cap]["tp"] += float(np.dot(chosen_weight, labels[order]))
        for model, baseline in pairs:
            pair = f"{model} - {baseline}"
            for cap in CAPACITIES:
                tag = str(int(cap * 100))
                a, b = summary[model][cap], summary[baseline][cap]
                aprec, bprec = a["tp"] / a["selected"], b["tp"] / b["selected"]
                arecall = a["tp"] / totals[cap]["positive"]
                brecall = b["tp"] / totals[cap]["positive"]
                samples[pair][f"{tag}_precision"].append(aprec - bprec)
                samples[pair][f"{tag}_capture_recall"].append(arecall - brecall)
    results = {}
    for pair, metrics in samples.items():
        results[pair] = {}
        for key, values in metrics.items():
            low, high = np.percentile(values, [2.5, 97.5])
            results[pair][key] = {"ci95": [float(low), float(high)]}
    return {"method": "paired monthly customer-trajectory percentile bootstrap; capacities recomputed each draw",
            "requested_resamples": reps, "seed": seed, "comparisons": results,
            "scope": "Conditional on fitted scores and selected configurations; intervals do not account for model selection or new periods."}


def run(dataset_path: Path, source_manifest_path: Path, models_path: Path, run_manifest_path: Path,
        predictions_path: Path, p3_aggregate_path: Path, p3_manifest_path: Path,
        output_dir: Path) -> dict[str, Any]:
    from monthly_purchase_baselines import verify_frozen_inputs

    expected_hashes = {
        "models": (models_path, EXPECTED_M2_MODELS),
        "run_manifest": (run_manifest_path, EXPECTED_M2_RUN_MANIFEST),
        "predictions": (predictions_path, EXPECTED_M2_PREDICTIONS),
        "p3_aggregate": (p3_aggregate_path, EXPECTED_P3_AGGREGATE),
    }
    for name, (path, digest) in expected_hashes.items():
        if sha256_file(path) != digest:
            raise ValueError(f"Frozen {name} artifact hash mismatch.")
    p3_manifest = json.loads(p3_manifest_path.read_text(encoding="utf-8"))
    if p3_manifest["aggregate_sha256"] != EXPECTED_P3_AGGREGATE:
        raise ValueError("P3-002 aggregate manifest does not pin expected aggregate.")
    p3_aggregate = json.loads(p3_aggregate_path.read_text(encoding="utf-8"))
    if p3_aggregate["search"]["selected"]["Random Forest"]["parameters"] != p3.RF_GRID[0]:
        raise ValueError("P3-002 RF selected settings differ from frozen extension reference.")
    if p3_aggregate["search"]["selected"]["HistGradientBoosting"]["parameters"] != p3.HGB_GRID[0]:
        raise ValueError("P3-002 HGB selected settings differ from frozen extension reference.")

    _, cohort = verify_frozen_inputs(dataset_path, source_manifest_path)
    predictions = pd.read_parquet(predictions_path)
    for frame in (cohort, predictions):
        frame[DECISION] = pd.to_datetime(frame[DECISION])
    if cohort.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Duplicate customer-decision snapshots.")
    if tuple(json.loads(source_manifest_path.read_text())["feature_columns"]) != tuple(FEATURE_COLUMNS):
        raise ValueError("M2 feature order differs from frozen contract.")
    if any(c in FEATURE_COLUMNS for c in (CUSTOMER, LABEL, DECISION, MONTH, "evaluation_partition")):
        raise ValueError("Identifier, label, timestamp or partition leaked into feature allowlist.")
    test = cohort.loc[cohort.evaluation_partition.eq("test")].copy()
    if predictions.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Duplicate frozen prediction keys.")
    frozen = predictions[[CUSTOMER, DECISION, LABEL, MODEL_C]].copy()
    test = test.merge(frozen, on=[CUSTOMER, DECISION], how="left", validate="one_to_one", suffixes=("", "_prediction"))
    if len(test) != 21672 or not test[LABEL].eq(test[f"{LABEL}_prediction"]).all():
        raise ValueError("M2-008 prediction/label alignment failed.")
    test = test.reset_index(drop=True)
    test["_frozen_c"] = test[MODEL_C]
    test.drop(columns=[f"{LABEL}_prediction", MODEL_C], inplace=True)
    folds = p3.make_folds(cohort)
    if [f["month"] for f in folds] != ["2011-03", "2011-04", "2011-05", "2011-06"]:
        raise ValueError("P3-002 development fold months changed.")
    if [len(f["validation"]) for f in folds] != [x["validation"]["snapshots"] for x in p3_aggregate["folds"]]:
        raise ValueError("Development fold sample sizes differ from P3-002 frozen fold definition.")

    grids = {"XGBoost": XGB_GRID, "LightGBM": LGB_GRID}
    records: list[dict[str, Any]] = []
    candidate_scores: dict[str, dict[str, np.ndarray]] = {}
    runtimes: dict[str, dict[str, float]] = {name: {"fit_seconds": 0.0, "predict_seconds": 0.0} for name in grids}
    baseline_dev: dict[str, list[np.ndarray]] = {"Logistic C": [], "Frequency": [],
                                                 "Random Forest": [], "HistGradientBoosting": []}
    fold_fit_times: list[dict[str, Any]] = []
    started = time.perf_counter()

    for fold in folds:
        train, validation, month = fold["train"], fold["validation"], fold["month"]
        boundary = fold["boundary"]
        if not (pd.to_datetime(train["outcome_window_end_exclusive"]) < boundary).all():
            raise ValueError(f"Maturity cutoff failed at {month}.")
        baseline_dev["Logistic C"].append(p3.logistic_fit_predict(train, validation))
        baseline_dev["Frequency"].append(validation[FREQ].to_numpy(float))
        for family, grid in (("Random Forest", [p3.RF_GRID[0]]), ("HistGradientBoosting", [p3.HGB_GRID[0]])):
            start = time.perf_counter()
            score, timing = _fit_predict(family, grid[0], train, validation)
            baseline_dev[family].append(score)
            fold_fit_times.append({"family": family, "fold": month, **timing})
        for family, grid in grids.items():
            for config_index, config in enumerate(grid):
                score, timing = _fit_predict(family, config, train, validation)
                candidate_scores.setdefault(f"{family}#{config_index}", {})[month] = score
                runtimes[family]["fit_seconds"] += timing["fit_seconds"]
                runtimes[family]["predict_seconds"] += timing["predict_seconds"]
                metrics = p3._metrics(validation[LABEL].to_numpy(int), score, probability=True)
                records.append({"family": family, "config_index": config_index, "fold": month,
                                "n_train": len(train), "n_train_customers": int(train[CUSTOMER].nunique()),
                                "n_validation": len(validation), "roc_auc": metrics["roc_auc"],
                                "average_precision": metrics["average_precision"],
                                "brier_score": metrics["brier_score"], "log_loss": metrics["log_loss"]})

    # This selection API only receives development-fold AP records. Holdout is not loaded into it.
    selected: dict[str, dict[str, Any]] = {}
    for family, grid in grids.items():
        chosen = select_by_development_ap(records, family, len(grid))
        chosen["parameters"] = grid[chosen["config_index"]]
        selected[family] = chosen

    development = pd.concat([fold["validation"] for fold in folds], ignore_index=True)
    base_scores = {name: np.concatenate(values) for name, values in baseline_dev.items()}
    for family in grids:
        base_scores[family] = np.concatenate([
            candidate_scores[f"{family}#{selected[family]['config_index']}"][fold["month"]]
            for fold in folds
        ])
    dev_eval = p3.evaluate_frame(development, base_scores)
    # Confirm the P3-002 RF/HGB reference refits reproduce the previously published metrics.
    baseline_expected_dev = p3_aggregate["development_pooled_oof"]["models"]
    for family in ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting"):
        for metric in ("roc_auc", "average_precision", "brier_score", "log_loss"):
            actual = dev_eval["models"][family][metric]
            expected = baseline_expected_dev[family][metric]
            if actual is None and expected is None:
                continue
            if actual is None or expected is None or not np.isclose(actual, expected, atol=1e-12, rtol=0):
                raise ValueError(f"Development reference differs from P3-002: {family} {metric} {actual} != {expected}")

    train_all = cohort.loc[cohort.evaluation_partition.eq("train")].copy()
    train_all["outcome_window_end_exclusive"] = pd.to_datetime(train_all["outcome_window_end_exclusive"])
    if not (train_all["outcome_window_end_exclusive"] <= pd.Timestamp("2011-07-01")).all():
        raise ValueError("Frozen M2 holdout training cutoff failed.")
    holdout_scores: dict[str, np.ndarray] = {
        "Logistic C": test["_frozen_c"].to_numpy(float), "Frequency": test[FREQ].to_numpy(float),
    }
    final_model_times = []
    for family, config in (("Random Forest", p3.RF_GRID[0]),
                           ("HistGradientBoosting", p3.HGB_GRID[0]),
                           ("XGBoost", selected["XGBoost"]["parameters"]),
                           ("LightGBM", selected["LightGBM"]["parameters"])):
        score, timing = _fit_predict(family, config, train_all, test)
        holdout_scores[family] = score
        final_model_times.append({"family": family, **timing})
        if family in runtimes:
            runtimes[family]["final_fit_seconds"] = timing["fit_seconds"]
            runtimes[family]["holdout_predict_seconds"] = timing["predict_seconds"]
    holdout_eval = p3.evaluate_frame(test, holdout_scores)
    expected_holdout = p3_aggregate["exploratory_published_holdout"]["models"]
    for family in ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting"):
        for metric in ("roc_auc", "average_precision", "brier_score", "log_loss"):
            actual = holdout_eval["models"][family][metric]
            expected = expected_holdout[family][metric]
            if actual is None and expected is None:
                continue
            if actual is None or expected is None or not np.isclose(actual, expected, atol=1e-12, rtol=0):
                raise ValueError(f"Exploratory P3-002 replay changed: {family} {metric} {actual} != {expected}")
    holdout_eval["monthly"] = []
    for month, ix in test.groupby(MONTH, sort=True).groups.items():
        ix = np.asarray(list(ix), dtype=int)
        holdout_eval["monthly"].append({"month": str(month),
            "evaluation": p3.evaluate_frame(test.iloc[ix].reset_index(drop=True),
                                             {name: score[ix] for name, score in holdout_scores.items()})})

    model_names = ["Random Forest", "HistGradientBoosting", "XGBoost", "LightGBM"]
    ranking_dev = _pairwise_cluster_bootstrap(development, base_scores,
        [(name, base) for name in ("XGBoost", "LightGBM")
         for base in ("Random Forest", "HistGradientBoosting")])
    ranking_holdout = _pairwise_cluster_bootstrap(test, holdout_scores,
        [(name, base) for name in ("XGBoost", "LightGBM")
         for base in ("Random Forest", "HistGradientBoosting")])
    crm_pairs = [(name, base) for name in ("XGBoost", "LightGBM")
                 for base in ("Random Forest", "HistGradientBoosting")]
    crm_dev_bootstrap = _crm_bootstrap(development, base_scores, crm_pairs)
    crm_holdout_bootstrap = _crm_bootstrap(test, holdout_scores, crm_pairs)
    # Include observed selection-metric differences at each capacity for point-vs-interval context.
    for pair, (family, baseline) in zip(crm_dev_bootstrap["comparisons"], crm_pairs):
        crm_dev_bootstrap["comparisons"][pair]["point_differences"] = {
            f"{cap}_{metric}": dev_eval["models"][family]["crm"][cap][metric]
            - dev_eval["models"][baseline]["crm"][cap][metric]
            for cap in ("5", "10", "20") for metric in ("precision", "capture_recall")}
    for pair, (family, baseline) in zip(crm_holdout_bootstrap["comparisons"], crm_pairs):
        crm_holdout_bootstrap["comparisons"][pair]["point_differences"] = {
            f"{cap}_{metric}": holdout_eval["models"][family]["crm"][cap][metric]
            - holdout_eval["models"][baseline]["crm"][cap][metric]
            for cap in ("5", "10", "20") for metric in ("precision", "capture_recall")}

    selected_fold_results = {}
    for family in grids:
        index = selected[family]["config_index"]
        selected_fold_results[family] = [next(r for r in records if r["family"] == family and
            r["config_index"] == index and r["fold"] == fold["month"]) for fold in folds]
    development_monthly = []
    for fold_result in p3_aggregate["folds"]:
        month = fold_result["month"]
        models = fold_result["validation"]["models"]
        row = {"month": month, "models": {name: {metric: models[name][metric] for metric in
                ("roc_auc", "average_precision", "brier_score", "log_loss")}
                for name in ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting")}}
        for family in grids:
            chosen_record = next(r for r in records if r["family"] == family and
                                 r["config_index"] == selected[family]["config_index"] and r["fold"] == month)
            row["models"][family] = {metric: chosen_record[metric] for metric in
                                      ("roc_auc", "average_precision", "brier_score", "log_loss")}
        development_monthly.append(row)

    result = {
        "experiment": "COMMERCIAL_DS_P3_003",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed; July-November results exploratory only",
        "provenance": {"dataset_sha256": sha256_file(dataset_path),
                       "source_manifest_sha256": sha256_file(source_manifest_path),
                       "m2_predictions_sha256": sha256_file(predictions_path),
                       "p3_002_aggregate_sha256": sha256_file(p3_aggregate_path),
                       "feature_columns": list(FEATURE_COLUMNS)},
        "selection": {"criterion": "For each new family, select configuration with the highest unweighted mean AP across the four March-June development folds; ties prefer the lower config index.",
                      "holdout_used_for_selection": False,
                      "adoption_rule": "Advance a new model only if dev AP gain versus RF is positive with paired 95% lower bound > 0, calibration and CRM targeting do not materially worsen, and performance is consistent across folds; exploratory, not confirmatory.",
                      "selected": selected, "selected_configuration_fold_results": selected_fold_results,
                      "candidate_count_per_new_family": 3,
                      "all_candidate_development_results": records},
        "development": {"folds": p3_aggregate["folds"], "monthly": development_monthly, "pooled_oof": dev_eval,
                        "ranking_bootstrap_vs_random_forest": ranking_dev,
                        "crm_bootstrap_vs_rf_and_hgb": crm_dev_bootstrap},
        "exploratory_published_holdout": {"pooled": holdout_eval,
                                           "ranking_bootstrap_vs_rf_and_hgb": ranking_holdout,
                                           "crm_bootstrap_vs_rf_and_hgb": crm_holdout_bootstrap},
        "model_comparison": {"development": {name: dev_eval["models"][name] for name in
                             ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting", "XGBoost", "LightGBM")},
                             "exploratory_holdout": {name: holdout_eval["models"][name] for name in
                             ("Logistic C", "Frequency", "Random Forest", "HistGradientBoosting", "XGBoost", "LightGBM")}},
        "training": {"seed": SEED, "n_jobs": 1, "xgboost_device": "cpu", "xgboost_tree_method": "hist",
                     "xgboost_early_stopping_rounds": None,
                     "lightgbm_deterministic": True, "lightgbm_force_col_wise": True,
                     "lightgbm_subsample_freq": 1,
                     "lightgbm_early_stopping": False, "early_stopping_validation_set": None,
                     "preprocessing": "log1p and fold-local median imputation; no scaling",
                     "xgboost_grid": XGB_GRID, "lightgbm_grid": LGB_GRID,
                     "reference_configs": {"Random Forest": p3.RF_GRID[0], "HistGradientBoosting": p3.HGB_GRID[0]},
                     "estimator_fit_counts": {"new_family_candidate_fold_fits": 24,
                                               "fixed_rf_hgb_fold_fits": 8,
                                               "logistic_fold_reference_fits": 4,
                                               "selected_new_and_rf_hgb_final_fits": 4,
                                               "total_estimator_fit_calls": 40}},
        "runtime": {"new_family_candidate_fit_and_validation_predict_seconds": runtimes,
                    "fixed_reference_fold_fits": fold_fit_times,
                    "final_model_fit_and_holdout_predict_seconds": final_model_times,
                    "benchmark_computation_seconds_including_bootstraps": time.perf_counter() - started},
        "software": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
                     "xgboost": xgboost.__version__, "lightgbm": lightgbm.__version__,
                     "openmp_runtime": "required; macOS run used Homebrew libomp"},
        "limitations": ["Four development origins were also used to select settings; intervals condition on the selected fitted scores.",
                        "July-November 2011 was previously examined and is exploratory, not a fresh test.",
                        "UCI Online Retail II has no untouched later period; customer resampling does not establish future generalisation.",
                        "Repeated customers, overlapping 30-day outcomes, seasonality and prevalence drift remain.",
                        "Predicted purchasing is not incremental campaign effect or causal uplift."]
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_file = output_dir / "p3_003_aggregate_results.json"
    aggregate_file.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    digest = sha256_file(aggregate_file)
    (output_dir / "p3_003_manifest.json").write_text(json.dumps({
        "experiment": "P3-003", "aggregate": aggregate_file.name,
        "aggregate_sha256": digest, "dataset_sha256": result["provenance"]["dataset_sha256"],
        "source_manifest_sha256": result["provenance"]["source_manifest_sha256"],
        "p3_002_aggregate_sha256": result["provenance"]["p3_002_aggregate_sha256"],
        "holdout_used_for_selection": False,
    }, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--p3-002-aggregate", type=Path, required=True)
    parser.add_argument("--p3-002-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if ROOT in args.output_dir.resolve().parents or args.output_dir.resolve() == ROOT:
        raise ValueError("P3-003 aggregate outputs must remain outside the repository.")
    result = run(args.dataset, args.source_manifest, args.models, args.run_manifest,
                 args.predictions, args.p3_002_aggregate, args.p3_002_manifest, args.output_dir)
    print(json.dumps({"selected": result["selection"]["selected"],
                      "development": {k: {m: v[m] for m in ("roc_auc", "average_precision", "brier_score", "log_loss")}
                                      for k, v in result["development"]["pooled_oof"]["models"].items()},
                      "holdout": {k: {m: v[m] for m in ("roc_auc", "average_precision", "brier_score", "log_loss")}
                                  for k, v in result["exploratory_published_holdout"]["pooled"]["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()

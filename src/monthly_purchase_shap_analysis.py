"""Probability-space SHAP analysis for the selected P3-002 Random Forest."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import shap
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import monthly_purchase_advanced_benchmark as p3  # noqa: E402
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    CUSTOMER_COLUMN, EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256,
    LABEL_COLUMN, MONTH_COLUMN, MODEL_SETTINGS, fit_preprocessor,
    sha256_file, verify_frozen_inputs,
)

CUSTOMER = CUSTOMER_COLUMN
LABEL = LABEL_COLUMN
MONTH = MONTH_COLUMN
SEED = 20261113
BACKGROUND_SIZE = 100
EXPLAIN_PER_PERIOD = 1000
# Absolute probability-scale reconstruction tolerance; checked on every explained row.
ADD_TOLERANCE = 2e-4
CORRELATION_THRESHOLD = 0.80
RF_CONFIG = p3.RF_GRID[0]
EXPECTED_P3_002_AGGREGATE = "f2594cb0095ee769c65220996bfbbcc90ac2cc923cf7453c5eebb53d90df28cb"


def deterministic_sample_positions(n: int, sample_size: int, seed: int) -> np.ndarray:
    """Uniform sample without replacement, returned in source-row order."""
    if n < 0 or sample_size < 0:
        raise ValueError("Sample sizes must be nonnegative.")
    if sample_size >= n:
        return np.arange(n, dtype=int)
    if sample_size == 0:
        return np.array([], dtype=int)
    rng = np.random.Generator(np.random.PCG64(seed))
    return np.sort(rng.choice(n, size=sample_size, replace=False))


def transformed_feature_frame(pipeline: Any, rows: pd.DataFrame) -> pd.DataFrame:
    """Apply the fitted pipeline preprocessing and preserve its ordered names."""
    if tuple(rows.loc[:, list(FEATURE_COLUMNS)].columns) != tuple(FEATURE_COLUMNS):
        raise ValueError("Raw feature order differs from the frozen M2 feature contract.")
    transformed = pipeline[:-1].transform(rows.loc[:, list(FEATURE_COLUMNS)])
    result = pd.DataFrame(np.asarray(transformed, dtype=float), columns=FEATURE_COLUMNS,
                          index=rows.index)
    if result.isna().any().any() or not np.isfinite(result.to_numpy()).all():
        raise ValueError("Transformed explanation features must be finite after fitted imputation.")
    return result


def training_background(pipeline: Any, training_rows: pd.DataFrame, *, seed: int = SEED,
                        size: int = BACKGROUND_SIZE) -> pd.DataFrame:
    """Choose a reproducible background only from the fitted model's training rows."""
    positions = deterministic_sample_positions(len(training_rows), min(size, len(training_rows)), seed)
    selected = training_rows.iloc[positions]
    return transformed_feature_frame(pipeline, selected)


def select_positive_class(explanation: Any, classes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Select positive-class SHAP values and base values from a classifier output."""
    class_matches = np.flatnonzero(np.asarray(classes) == 1)
    if len(class_matches) != 1:
        raise ValueError("The fitted classifier must expose exactly one positive class label 1.")
    class_index = int(class_matches[0])
    values = np.asarray(explanation.values, dtype=float)
    base = np.asarray(explanation.base_values, dtype=float)
    if values.ndim == 3:
        if values.shape[-1] <= class_index:
            raise ValueError("SHAP output dimension does not contain the positive class.")
        values = values[:, :, class_index]
    elif values.ndim != 2:
        raise ValueError(f"Unexpected SHAP value shape: {values.shape}.")
    if base.ndim == 2:
        base = base[:, class_index]
    elif base.ndim == 0:
        base = np.repeat(float(base), len(values))
    elif base.ndim != 1:
        raise ValueError(f"Unexpected SHAP base-value shape: {base.shape}.")
    if len(base) != len(values):
        raise ValueError("SHAP base values are not aligned with explanation rows.")
    return values, base


def explain_positive_probability(model: RandomForestClassifier, background: pd.DataFrame,
                                 explained: pd.DataFrame, *, tolerance: float = ADD_TOLERANCE
                                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Return class-1 probability SHAP values with an explicit additivity audit."""
    if tuple(background.columns) != tuple(FEATURE_COLUMNS) or tuple(explained.columns) != tuple(FEATURE_COLUMNS):
        raise ValueError("SHAP feature names/order do not match the model input contract.")
    explainer = shap.TreeExplainer(
        model, data=background, model_output="probability",
        feature_perturbation="interventional", feature_names=list(FEATURE_COLUMNS),
    )
    explanation = explainer(explained, check_additivity=False)
    values, base = select_positive_class(explanation, model.classes_)
    positive_index = int(np.flatnonzero(model.classes_ == 1)[0])
    probability = model.predict_proba(explained.to_numpy())[:, positive_index]
    reconstructed = base + values.sum(axis=1)
    max_error = float(np.max(np.abs(reconstructed - probability))) if len(probability) else 0.0
    if max_error > tolerance:
        raise ValueError(f"SHAP additivity error {max_error:.3g} exceeds {tolerance:.3g} probability units.")
    return values, base, probability, max_error


def importance_summary(values: np.ndarray, feature_names: tuple[str, ...] = FEATURE_COLUMNS) -> list[dict[str, Any]]:
    """Aggregate probability contributions without retaining row-level outputs."""
    if values.ndim != 2 or values.shape[1] != len(feature_names):
        raise ValueError("Contribution matrix does not align with feature names.")
    records = []
    for j, name in enumerate(feature_names):
        col = values[:, j]
        records.append({
            "feature": name,
            "mean_abs_shap_probability": float(np.mean(np.abs(col))),
            "mean_signed_shap_probability": float(np.mean(col)),
            "mean_positive_shap_probability": float(np.mean(col[col > 0])) if np.any(col > 0) else 0.0,
            "mean_negative_shap_probability": float(np.mean(col[col < 0])) if np.any(col < 0) else 0.0,
            "fraction_positive": float(np.mean(col > 0)),
            "fraction_negative": float(np.mean(col < 0)),
        })
    return sorted(records, key=lambda r: (-r["mean_abs_shap_probability"], r["feature"]))


def _fit_logistic_coefficients(train: pd.DataFrame, validation: pd.DataFrame) -> dict[str, Any]:
    """Fit the already-prescribed fold-specific Logistic C once and return scores/coefs."""
    preprocessor, z_train = fit_preprocessor(train.loc[:, list(FEATURE_COLUMNS)], FEATURE_COLUMNS)
    model = LogisticRegression(**MODEL_SETTINGS)
    model.fit(z_train, train[LABEL].to_numpy(int))
    if model.n_iter_[0] >= MODEL_SETTINGS["max_iter"]:
        raise RuntimeError("Frozen fold Logistic C did not converge while recovering coefficients.")
    z_validation = preprocessor.transform(validation.loc[:, list(FEATURE_COLUMNS)])
    probabilities = model.predict_proba(z_validation)[:, int(np.flatnonzero(model.classes_ == 1)[0])]
    return {"probability": probabilities,
            "coefficients_standardized_log1p": model.coef_[0].astype(float).tolist(),
            "n_iter": int(model.n_iter_[0])}


def _spearman_components(frame: pd.DataFrame, threshold: float = CORRELATION_THRESHOLD) -> dict[str, Any]:
    corr = frame.loc[:, list(FEATURE_COLUMNS)].corr(method="spearman")
    pairs = []
    graph = {name: set() for name in FEATURE_COLUMNS}
    for i, a in enumerate(FEATURE_COLUMNS):
        for b in FEATURE_COLUMNS[i + 1:]:
            value = corr.loc[a, b]
            if pd.notna(value) and abs(float(value)) >= threshold:
                pairs.append({"feature_a": a, "feature_b": b, "spearman_rho": float(value)})
                graph[a].add(b)
                graph[b].add(a)
    components = []
    seen: set[str] = set()
    for feature in FEATURE_COLUMNS:
        if feature in seen or not graph[feature]:
            continue
        stack, component = [feature], []
        seen.add(feature)
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in graph[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if len(component) > 1:
            components.append(sorted(component))
    return {"method": "Spearman rank correlation on all development validation snapshots",
            "absolute_threshold": threshold, "pairs": sorted(pairs, key=lambda x: -abs(x["spearman_rho"])),
            "connected_feature_groups": components,
            "matrix": [[float(corr.loc[a, b]) if pd.notna(corr.loc[a, b]) else None for b in FEATURE_COLUMNS]
                       for a in FEATURE_COLUMNS]}


def _group_contribution_summary(values: np.ndarray, groups: list[list[str]]) -> list[dict[str, Any]]:
    out = []
    index = {name: i for i, name in enumerate(FEATURE_COLUMNS)}
    for group in groups:
        net = values[:, [index[n] for n in group]].sum(axis=1)
        out.append({"features": group, "mean_abs_net_group_shap_probability": float(np.mean(np.abs(net))),
                    "mean_signed_net_group_shap_probability": float(np.mean(net)),
                    "sum_of_member_mean_abs_shap_probability": float(np.abs(values[:, [index[n] for n in group]]).mean(axis=0).sum())})
    return sorted(out, key=lambda x: -x["mean_abs_net_group_shap_probability"])


def _dependence_profiles(raw: pd.DataFrame, values: np.ndarray,
                         features: list[str], bins: int = 6) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for name in features:
        raw_values = pd.to_numeric(raw[name], errors="coerce")
        contribution = values[:, FEATURE_COLUMNS.index(name)]
        valid = raw_values.notna().to_numpy()
        if valid.sum() < bins:
            continue
        try:
            bin_codes = pd.qcut(raw_values.loc[valid], q=bins, labels=False, duplicates="drop")
        except ValueError:
            continue
        local = pd.DataFrame({"value": raw_values.loc[valid].to_numpy(),
                              "shap": contribution[valid], "bin": np.asarray(bin_codes)})
        result[name] = []
        for code, group in local.groupby("bin", sort=True):
            result[name].append({"bin": int(code), "n": int(len(group)),
                                 "mean_feature_value": float(group.value.mean()),
                                 "median_feature_value": float(group.value.median()),
                                 "mean_shap_probability": float(group.shap.mean()),
                                 "mean_abs_shap_probability": float(group.shap.abs().mean())})
    return result


def _decile_profiles(probability: np.ndarray, values: np.ndarray, labels: np.ndarray,
                     selected_features: list[str]) -> list[dict[str, Any]]:
    ranks = pd.Series(probability).rank(method="first")
    decile = pd.qcut(ranks, 10, labels=False, duplicates="drop")
    rows = []
    for d in sorted(pd.Series(decile).dropna().unique()):
        mask = np.asarray(decile == d)
        rows.append({"prediction_decile": int(d) + 1, "n": int(mask.sum()),
                     "mean_predicted_probability": float(np.mean(probability[mask])),
                     "observed_prevalence": float(np.mean(labels[mask])),
                     "mean_signed_shap_probability": {
                         name: float(np.mean(values[mask, FEATURE_COLUMNS.index(name)]))
                         for name in selected_features}})
    return rows


def _make_figures(aggregate: dict[str, Any], output_dir: Path) -> list[str]:
    plot_dir = output_dir / "docs" / "research" / "figures"
    plot_dir.mkdir(parents=True, exist_ok=True)
    dev = aggregate["development"]
    global_summary = dev["overall_importance"]
    ranked = [x["feature"] for x in global_summary]
    fig, ax = plt.subplots(figsize=(9, 6))
    ordered = list(reversed(global_summary))
    ax.barh([x["feature"] for x in ordered], [x["mean_abs_shap_probability"] for x in ordered], color="#34699a")
    ax.set_xlabel("Mean absolute SHAP contribution to purchase probability")
    ax.set_title("Development Random Forest: global feature importance")
    ax.grid(axis="x", alpha=.2)
    fig.tight_layout()
    f1 = plot_dir / "p3_004_shap_global_importance.png"
    fig.savefig(f1, dpi=180)
    plt.close(fig)

    periods = dev["period_importance"] + aggregate["exploratory_holdout"]["month_importance"]
    matrix = np.array([[next(r["mean_abs_shap_probability"] for r in p["importance"] if r["feature"] == name)
                        for name in ranked] for p in periods])
    fig, ax = plt.subplots(figsize=(11, 4.2))
    im = ax.imshow(matrix, aspect="auto", cmap="viridis")
    ax.set_xticks(np.arange(len(ranked)), labels=ranked, rotation=60, ha="right")
    period_labels = [p["period"].replace("2011-", "Dev ") for p in periods[:4]] + [
        p["period"].replace("2011-", "Holdout ") for p in periods[4:]]
    short_labels = [name.replace("qualifying_purchase_", "purchase_")
                    .replace("qualifying_gross_merchandise_", "gross_")
                    .replace("qualifying_unique_product_count_", "unique_products_")
                    .replace("average_qualifying_", "avg_")
                    .replace("average_basket_", "avg_")
                    .replace("days_since_last_qualifying_purchase", "recency_days")
                    .replace("median_interpurchase_interval_days_365d", "median_interval_365d")
                    for name in ranked]
    ax.set_yticks(np.arange(len(periods)), labels=period_labels)
    ax.set_xticks(np.arange(len(ranked)), labels=short_labels, rotation=35, ha="right")
    ax.set_title("Mean absolute SHAP by development fold and exploratory holdout month")
    fig.colorbar(im, ax=ax, label="Probability contribution")
    fig.subplots_adjust(bottom=.34, right=.91, left=.20, top=.88)
    f2 = plot_dir / "p3_004_shap_temporal_stability.png"
    fig.savefig(f2, dpi=180)
    plt.close(fig)

    top_features = ranked[:6]
    profiles = dev["feature_value_shap_profiles"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for ax, name in zip(axes.flat, top_features):
        bins = profiles.get(name, [])
        ax.plot([x["mean_feature_value"] for x in bins], [x["mean_shap_probability"] for x in bins],
                marker="o", color="#b04a5a")
        ax.axhline(0, color="black", lw=.8, alpha=.65)
        ax.set_title(name, fontsize=9)
        ax.set_ylabel("Mean SHAP contribution to P(purchase)")
        ax.set_xlabel("Raw feature value (quantile bins)")
        ax.grid(alpha=.2)
        if name in {"qualifying_gross_merchandise_365d", "qualifying_gross_merchandise_90d",
                    "qualifying_unique_product_count_365d", "qualifying_purchase_occasions_365d",
                    "qualifying_purchase_dates_365d", "qualifying_purchase_occasions_90d"}:
            ax.set_xscale("log")
    fig.suptitle("Development feature values and average SHAP contributions", y=1.01)
    fig.tight_layout()
    f3 = plot_dir / "p3_004_shap_feature_profiles.png"
    fig.savefig(f3, dpi=180, bbox_inches="tight")
    plt.close(fig)

    decile = dev["prediction_decile_profiles"]
    fig, ax = plt.subplots(figsize=(10, 5))
    for name in top_features[:5]:
        ax.plot([x["prediction_decile"] for x in decile],
                [x["mean_signed_shap_probability"][name] for x in decile], marker="o", label=name)
    ax.axhline(0, color="black", lw=.8, alpha=.65)
    ax.set_xlabel("Prediction decile (1 = lowest, 10 = highest)")
    ax.set_ylabel("Mean signed SHAP contribution to P(purchase)")
    ax.set_title("Aggregate contribution profiles across predicted-risk deciles")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=.2)
    fig.tight_layout()
    f4 = plot_dir / "p3_004_shap_decile_profiles.png"
    fig.savefig(f4, dpi=180)
    plt.close(fig)
    return [str(p.relative_to(ROOT)) for p in (f1, f2, f3, f4)]


def run(dataset_path: Path, source_manifest_path: Path, p3_aggregate_path: Path,
        output_dir: Path, *, explain_per_period: int = EXPLAIN_PER_PERIOD,
        background_size: int = BACKGROUND_SIZE) -> dict[str, Any]:
    from monthly_purchase_baselines import verify_frozen_inputs

    if sha256_file(dataset_path) != EXPECTED_DATASET_SHA256:
        raise ValueError("Frozen M2 dataset hash mismatch.")
    if sha256_file(source_manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Frozen M2 source manifest hash mismatch.")
    if sha256_file(p3_aggregate_path) != EXPECTED_P3_002_AGGREGATE:
        raise ValueError("Accepted P3-002 aggregate hash mismatch.")
    p3_aggregate = json.loads(p3_aggregate_path.read_text(encoding="utf-8"))
    if p3_aggregate["search"]["selected"]["Random Forest"]["parameters"] != RF_CONFIG:
        raise ValueError("Selected P3-002 Random Forest configuration differs from the frozen model settings.")
    _, cohort = verify_frozen_inputs(dataset_path, source_manifest_path)
    cohort["decision_time"] = pd.to_datetime(cohort["decision_time"])
    if cohort.duplicated([CUSTOMER, "decision_time"]).any():
        raise ValueError("Duplicate M2 customer-decision snapshots.")
    if tuple(json.loads(source_manifest_path.read_text())["feature_columns"]) != tuple(FEATURE_COLUMNS):
        raise ValueError("M2 feature allowlist differs from its frozen ordered contract.")

    folds = p3.make_folds(cohort)
    if [x["month"] for x in folds] != ["2011-03", "2011-04", "2011-05", "2011-06"]:
        raise ValueError("Maturity-valid P3 development origins changed.")
    train_full = cohort.loc[cohort.evaluation_partition.eq("train")].copy()
    train_full["outcome_window_end_exclusive"] = pd.to_datetime(train_full["outcome_window_end_exclusive"])
    if not (train_full["outcome_window_end_exclusive"] <= pd.Timestamp("2011-07-01")).all():
        raise ValueError("Frozen January-June M2 training cutoff failed.")
    holdout = cohort.loc[cohort.evaluation_partition.eq("test")].copy().reset_index(drop=True)
    if len(train_full) != 25647 or len(holdout) != 21672:
        raise ValueError("Frozen M2 training or exploratory holdout size changed.")

    start_all = time.perf_counter()
    dev_raw_parts: list[pd.DataFrame] = []
    dev_value_parts: list[np.ndarray] = []
    dev_base_parts: list[np.ndarray] = []
    dev_probability_parts: list[np.ndarray] = []
    dev_label_parts: list[np.ndarray] = []
    dev_weight_parts: list[np.ndarray] = []
    period_importance: list[dict[str, Any]] = []
    model_metrics: list[dict[str, Any]] = []
    logistic_coefficients: list[dict[str, Any]] = []
    local_records: list[pd.DataFrame] = []
    fit_seconds: dict[str, float] = {}
    shap_seconds: dict[str, float] = {}
    additivity_errors: dict[str, float] = {}
    explained_counts: dict[str, int] = {}
    local_quantiles = (0.10, 0.50, 0.90)

    for fold_index, fold in enumerate(folds):
        period = fold["month"]
        train, validation = fold["train"], fold["validation"].reset_index(drop=True)
        if not (pd.to_datetime(train["outcome_window_end_exclusive"]) < fold["boundary"]).all():
            raise ValueError(f"Strict maturity cutoff failed for {period}.")
        pipeline = p3._estimator("Random Forest", RF_CONFIG, p3.SEED)
        fit_start = time.perf_counter()
        pipeline.fit(train.loc[:, list(FEATURE_COLUMNS)], train[LABEL].to_numpy(int))
        fit_seconds[period] = time.perf_counter() - fit_start
        raw_model = pipeline.named_steps["model"]
        if not isinstance(raw_model, RandomForestClassifier) or not np.array_equal(raw_model.classes_, [0, 1]):
            raise TypeError("Expected the accepted binary RandomForestClassifier with classes [0, 1].")
        probability_all = pipeline.predict_proba(validation.loc[:, list(FEATURE_COLUMNS)])[:, 1]
        expected = p3_aggregate["folds"][fold_index]["validation"]["models"]["Random Forest"]
        observed_auc = float(roc_auc_score(validation[LABEL], probability_all))
        observed_ap = float(average_precision_score(validation[LABEL], probability_all))
        observed_brier = float(brier_score_loss(validation[LABEL], probability_all))
        observed_logloss = float(log_loss(validation[LABEL], probability_all, labels=[0, 1]))
        for name, value in (("roc_auc", observed_auc), ("average_precision", observed_ap),
                            ("brier_score", observed_brier), ("log_loss", observed_logloss)):
            if not np.isclose(value, expected[name], atol=1e-12, rtol=0):
                raise ValueError(f"P3-002 {period} RF {name} did not reproduce: {value} vs {expected[name]}.")
        logistic_fit = _fit_logistic_coefficients(train, validation)
        logistic_score = logistic_fit.pop("probability")
        logistic_expected = p3_aggregate["folds"][fold_index]["validation"]["models"]["Logistic C"]
        for name, value in (("roc_auc", roc_auc_score(validation[LABEL], logistic_score)),
                            ("average_precision", average_precision_score(validation[LABEL], logistic_score)),
                            ("brier_score", brier_score_loss(validation[LABEL], logistic_score)),
                            ("log_loss", log_loss(validation[LABEL], logistic_score, labels=[0, 1]))):
            if not np.isclose(value, logistic_expected[name], atol=1e-12, rtol=0):
                raise ValueError(f"Frozen fold Logistic C {period} {name} did not reproduce P3-002.")
        logistic_coefficients.append({"period": period, **logistic_fit})

        positions = deterministic_sample_positions(len(validation), explain_per_period, SEED + fold_index)
        explained_rows = validation.iloc[positions].copy()
        background = training_background(pipeline, train, seed=SEED + 100 + fold_index, size=background_size)
        transformed_explained = transformed_feature_frame(pipeline, explained_rows)
        shap_start = time.perf_counter()
        values, base, probability, error = explain_positive_probability(raw_model, background,
                                                                         transformed_explained)
        shap_seconds[period] = time.perf_counter() - shap_start
        additivity_errors[period] = error
        explained_counts[period] = len(explained_rows)
        # Use full-fold predictions for quantile case selection and select explained rows nearest q10/q50/q90.
        sampled_prob = probability_all[positions]
        local_idx: dict[int, list[float]] = {}
        for q in local_quantiles:
            target = float(np.quantile(sampled_prob, q))
            chosen = int(np.argmin(np.abs(sampled_prob - target)))
            local_idx.setdefault(chosen, []).append(q)
        for local_number, idx in enumerate(sorted(local_idx), start=1):
            row = explained_rows.iloc[idx]
            private = {"period": period, "sample_role": "prediction_quantile_case", "case_number": local_number,
                       "target_prediction_quantiles": ",".join(f"{q:.2f}" for q in local_idx[idx]),
                       "customer_id": row[CUSTOMER], "prediction_probability": float(probability[idx]),
                       "base_probability": float(base[idx])}
            private.update({f"feature__{name}": row[name] for name in FEATURE_COLUMNS})
            private.update({f"shap__{name}": float(values[idx, j]) for j, name in enumerate(FEATURE_COLUMNS)})
            local_records.append(pd.DataFrame([private]))
        importance = importance_summary(values)
        period_importance.append({"period": period, "n_explained": len(explained_rows),
                                  "n_validation": len(validation),
                                  "observed_prevalence_full_validation": float(validation[LABEL].mean()),
                                  "mean_predicted_probability_full_validation": float(probability_all.mean()),
                                  "importance": importance,
                                  "additivity_max_abs_error_probability": error})
        model_metrics.append({"period": period, "n_validation": len(validation),
                              "auc": observed_auc, "average_precision": observed_ap,
                              "brier_score": observed_brier, "log_loss": observed_logloss,
                              "observed_prevalence": float(validation[LABEL].mean()),
                              "mean_predicted_probability": float(probability_all.mean())})
        dev_raw_parts.append(explained_rows.reset_index(drop=True))
        dev_value_parts.append(values)
        dev_base_parts.append(base)
        dev_probability_parts.append(probability)
        dev_label_parts.append(explained_rows[LABEL].to_numpy(int))
        dev_weight_parts.append(np.repeat(len(validation) / len(explained_rows), len(explained_rows)))
        # Private sampled row explanations, including identifiers, are kept outside Git.
        private_frame = explained_rows[[CUSTOMER, LABEL] + list(FEATURE_COLUMNS)].reset_index(drop=True).copy()
        private_frame.insert(0, "period", period)
        private_frame["sample_role"] = "global_uniform_explanation_sample"
        private_frame["prediction_probability"] = probability
        private_frame["base_probability"] = base
        for j, name in enumerate(FEATURE_COLUMNS):
            private_frame[f"shap__{name}"] = values[:, j]
        local_records.append(private_frame)

    dev_raw = pd.concat(dev_raw_parts, ignore_index=True)
    dev_values = np.concatenate(dev_value_parts, axis=0)
    dev_prob = np.concatenate(dev_probability_parts)
    dev_label = np.concatenate(dev_label_parts)
    dev_weights = np.concatenate(dev_weight_parts)
    total_weight = float(dev_weights.sum())
    weighted_overall = []
    for j, name in enumerate(FEATURE_COLUMNS):
        col = dev_values[:, j]
        weighted_overall.append({
            "feature": name,
            "mean_abs_shap_probability": float(np.average(np.abs(col), weights=dev_weights)),
            "mean_signed_shap_probability": float(np.average(col, weights=dev_weights)),
            "fraction_positive": float(np.average((col > 0).astype(float), weights=dev_weights)),
            "fraction_negative": float(np.average((col < 0).astype(float), weights=dev_weights)),
        })
    weighted_overall.sort(key=lambda x: (-x["mean_abs_shap_probability"], x["feature"]))
    correlations = _spearman_components(pd.concat([f["validation"] for f in folds], ignore_index=True))
    groups = correlations["connected_feature_groups"]
    group_summary = _group_contribution_summary(dev_values, groups)
    dev_selected = [x["feature"] for x in weighted_overall[:6]]
    dependence = _dependence_profiles(dev_raw, dev_values, dev_selected)
    deciles = _decile_profiles(dev_prob, dev_values, dev_label, dev_selected)
    rank_by_period = [{x["feature"]: rank + 1 for rank, x in enumerate(period["importance"])}
                      for period in period_importance]
    period_pairs = []
    for i in range(len(period_importance)):
        for j in range(i + 1, len(period_importance)):
            a, b = period_importance[i], period_importance[j]
            rho = float(pd.Series(rank_by_period[i]).corr(pd.Series(rank_by_period[j]), method="spearman"))
            top_a = set(list(rank_by_period[i])[:5])
            top_b = set(list(rank_by_period[j])[:5])
            period_pairs.append({"period_a": a["period"], "period_b": b["period"],
                                 "spearman_rank_correlation": rho,
                                 "top5_overlap_count": len(top_a & top_b),
                                 "top5_union_count": len(top_a | top_b)})
    direction_consistency = []
    for name in FEATURE_COLUMNS:
        means = [next(x["mean_signed_shap_probability"] for x in p["importance"] if x["feature"] == name)
                 for p in period_importance]
        nonzero_signs = [int(np.sign(x)) for x in means if abs(x) > 1e-12]
        direction_consistency.append({"feature": name, "period_mean_signed_shap_probability": means,
                                      "nonzero_direction_signs": nonzero_signs,
                                      "same_direction_fraction": (max(nonzero_signs.count(1), nonzero_signs.count(-1)) /
                                                                   len(nonzero_signs)) if nonzero_signs else None})
    temporal_stability = {"pairwise_period_rank_similarity": period_pairs,
                          "direction_consistency": direction_consistency,
                          "periods_are_separately_fitted_models": True}

    # Descriptive holdout replay only; the model and explanation configuration are unchanged.
    final_pipeline = p3._estimator("Random Forest", RF_CONFIG, p3.SEED)
    fit_start = time.perf_counter()
    final_pipeline.fit(train_full.loc[:, list(FEATURE_COLUMNS)], train_full[LABEL].to_numpy(int))
    fit_seconds["exploratory_july_november"] = time.perf_counter() - fit_start
    final_rf = final_pipeline.named_steps["model"]
    holdout_probability_all = final_pipeline.predict_proba(holdout.loc[:, list(FEATURE_COLUMNS)])[:, 1]
    hold_positions = deterministic_sample_positions(len(holdout), explain_per_period, SEED + 1000)
    hold_rows = holdout.iloc[hold_positions].copy()
    hold_background = training_background(final_pipeline, train_full,
                                         seed=SEED + 1100, size=background_size)
    hold_transformed = transformed_feature_frame(final_pipeline, hold_rows)
    shap_start = time.perf_counter()
    hold_values, hold_base, hold_probability, hold_error = explain_positive_probability(
        final_rf, hold_background, hold_transformed)
    shap_seconds["exploratory_july_november"] = time.perf_counter() - shap_start
    additivity_errors["exploratory_july_november"] = hold_error
    explained_counts["exploratory_july_november"] = len(hold_rows)
    hold_importance = importance_summary(hold_values)
    hold_selected = [x["feature"] for x in weighted_overall[:6]]
    hold_dependence = _dependence_profiles(hold_rows, hold_values, hold_selected)
    hold_local_idx: dict[int, list[float]] = {}
    for q in local_quantiles:
        target = float(np.quantile(hold_probability, q))
        chosen = int(np.argmin(np.abs(hold_probability - target)))
        hold_local_idx.setdefault(chosen, []).append(q)
    for local_number, idx in enumerate(sorted(hold_local_idx), start=1):
        row = hold_rows.iloc[idx]
        private = {"period": "exploratory_july_november", "sample_role": "prediction_quantile_case",
                   "case_number": local_number,
                   "target_prediction_quantiles": ",".join(f"{q:.2f}" for q in hold_local_idx[idx]),
                   "customer_id": row[CUSTOMER],
                   "prediction_probability": float(hold_probability[idx]), "base_probability": float(hold_base[idx])}
        private.update({f"feature__{name}": row[name] for name in FEATURE_COLUMNS})
        private.update({f"shap__{name}": float(hold_values[idx, j]) for j, name in enumerate(FEATURE_COLUMNS)})
        local_records.append(pd.DataFrame([private]))
    hold_private = hold_rows[[CUSTOMER, LABEL] + list(FEATURE_COLUMNS)].reset_index(drop=True).copy()
    hold_private.insert(0, "period", "exploratory_july_november")
    hold_private["sample_role"] = "global_uniform_explanation_sample"
    hold_private["prediction_probability"] = hold_probability
    hold_private["base_probability"] = hold_base
    for j, name in enumerate(FEATURE_COLUMNS):
        hold_private[f"shap__{name}"] = hold_values[:, j]
    local_records.append(hold_private)
    hold_month_importance = []
    sampled_months = hold_rows[MONTH].astype(str).to_numpy()
    for month in sorted(np.unique(sampled_months)):
        sample_mask = sampled_months == month
        population_mask = holdout[MONTH].astype(str).to_numpy() == month
        hold_month_importance.append({"period": month, "n_explained": int(sample_mask.sum()),
                                      "n_population": int(population_mask.sum()),
                                      "observed_prevalence_full": float(holdout.loc[population_mask, LABEL].mean()),
                                      "mean_predicted_probability_full": float(holdout_probability_all[population_mask].mean()),
                                      "importance": importance_summary(hold_values[sample_mask])})

    # Recover the established fold Logistic C coefficients and compare ranks/signs, not raw units.
    coef_matrix = np.array([row["coefficients_standardized_log1p"] for row in logistic_coefficients])
    logistic_summary = []
    for j, name in enumerate(FEATURE_COLUMNS):
        vals = coef_matrix[:, j]
        logistic_summary.append({"feature": name, "mean_standardized_log1p_coefficient": float(vals.mean()),
                                 "fold_signs": [int(np.sign(x)) for x in vals],
                                 "sign_consistency_fraction": float(max(np.mean(vals > 0), np.mean(vals < 0))),
                                 "mean_absolute_coefficient": float(np.mean(np.abs(vals)))})
    logistic_summary.sort(key=lambda x: (-x["mean_absolute_coefficient"], x["feature"]))
    shap_rank = {x["feature"]: rank + 1 for rank, x in enumerate(weighted_overall)}
    logistic_rank = {x["feature"]: rank + 1 for rank, x in enumerate(logistic_summary)}
    rank_rho = float(pd.Series(shap_rank).corr(pd.Series(logistic_rank), method="spearman"))

    private_dir = output_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=True)
    private_path = private_dir / "p3_004_individual_shap_explanations.parquet"
    pd.concat(local_records, ignore_index=True).to_parquet(private_path, index=False)
    aggregate = {
        "experiment": "COMMERCIAL_DS_P3_004",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed; July-November analysis is exploratory and descriptive",
        "provenance": {"dataset_sha256": sha256_file(dataset_path),
                       "source_manifest_sha256": sha256_file(source_manifest_path),
                       "p3_002_aggregate_sha256": sha256_file(p3_aggregate_path),
                       "features": list(FEATURE_COLUMNS)},
        "model": {"family": "sklearn RandomForestClassifier", "parameters": RF_CONFIG,
                  "random_state": p3.SEED, "n_jobs": 1,
                  "preprocessing": "P3-002 pipeline: log1p then training-fold median imputation; no scaling"},
        "explanation": {"library": "shap", "version": shap.__version__,
                        "explainer": "TreeExplainer", "model_output": "probability",
                        "explained_class": 1, "feature_perturbation": "interventional",
                        "background_size_per_fit": background_size,
                        "background_sampling": "uniform without replacement from that model fit's training rows only; PCG64",
                        "explanation_sampling": f"uniform without replacement up to {explain_per_period} rows per period; sorted source-row positions; PCG64",
                        "seed": SEED, "base_value": "expected positive-class purchase probability under the sampled training reference background",
                        "period_sampling_seeds": {**{f"{f['month']}_explanation": SEED + i for i, f in enumerate(folds)},
                                                  **{f"{f['month']}_background": SEED + 100 + i for i, f in enumerate(folds)},
                                                  "exploratory_holdout_explanation": SEED + 1000,
                                                  "exploratory_holdout_background": SEED + 1100},
                        "additivity_tolerance_probability": ADD_TOLERANCE,
                        "maximum_observed_additivity_error_probability": max(additivity_errors.values()),
                        "period_max_additivity_error_probability": additivity_errors,
                        "sampling_counts": explained_counts,
                        "development_explained_n": int(sum(explained_counts[m] for m in explained_counts if m.startswith("2011-"))),
                        "exploratory_holdout_explained_n": explained_counts["exploratory_july_november"]},
        "development": {"period_importance": period_importance,
                        "overall_importance": weighted_overall,
                        "temporal_stability": temporal_stability,
                        "group_contribution_summary": group_summary,
                        "feature_value_shap_profiles": dependence,
                        "prediction_decile_profiles": deciles,
                        "correlations": correlations,
                        "model_metrics_by_period": model_metrics,
                        "logistic_coefficient_summary": logistic_summary,
                        "spearman_correlation_of_abs_importance_ranks_rf_shap_vs_logistic_abs_coef": rank_rho},
        "exploratory_holdout": {"population": "previously examined July-November 2011 M2 holdout; descriptive only",
                                 "period_importance": hold_importance,
                                 "month_importance": hold_month_importance,
                                 "feature_value_shap_profiles": hold_dependence,
                                 "observed_prevalence_full": float(holdout[LABEL].mean()),
                                 "mean_predicted_probability_full": float(holdout_probability_all.mean()),
                                 "metrics_full": {"roc_auc": float(roc_auc_score(holdout[LABEL], holdout_probability_all)),
                                                  "average_precision": float(average_precision_score(holdout[LABEL], holdout_probability_all)),
                                                  "brier_score": float(brier_score_loss(holdout[LABEL], holdout_probability_all)),
                                                  "log_loss": float(log_loss(holdout[LABEL], holdout_probability_all, labels=[0, 1]))},
                                 "additivity_max_abs_error_probability": hold_error},
        "private_individual_explanations": {"path": str(private_path), "sha256": sha256_file(private_path),
                                            "contains_customer_ids": True,
                                            "sampled_global_rows": int(sum(explained_counts.values())),
                                            "quantile_cases_per_period": list(local_quantiles)},
        "runtime": {"fit_seconds_by_period": fit_seconds,
                    "shap_seconds_by_period": shap_seconds,
                    "elapsed_seconds_excluding_plotting": time.perf_counter() - start_all},
        "software": {"python": sys.version.split()[0], "numpy": np.__version__,
                     "scikit_learn": sklearn.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "shap": shap.__version__},
        "limitations": ["SHAP is a model attribution for fitted predictive probabilities, not a causal effect.",
                        "Interventional SHAP depends on the sampled background and can create unrealistic combinations among correlated predictors.",
                        "Four development folds use separately fitted RF models; differences mix temporal composition and model-fit variation.",
                        "The previously examined July-November holdout is exploratory and not independent future confirmation.",
                        "Only 1,000 observations per period are sampled for explanations; summaries have Monte Carlo sampling variation.",
                        "Logistic coefficients are standardized-log1p log-odds quantities and are not numerically comparable with probability-scale SHAP values."]
    }
    report_output_dir = ROOT
    figure_paths = _make_figures(aggregate, report_output_dir)
    aggregate["figures"] = figure_paths
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_path = output_dir / "p3_004_aggregate_results.json"
    aggregate_path.write_text(json.dumps(aggregate, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {"experiment": "P3-004", "aggregate": aggregate_path.name,
                "aggregate_sha256": sha256_file(aggregate_path),
                "dataset_sha256": aggregate["provenance"]["dataset_sha256"],
                "source_manifest_sha256": aggregate["provenance"]["source_manifest_sha256"],
                "p3_002_aggregate_sha256": aggregate["provenance"]["p3_002_aggregate_sha256"],
                "individual_explanations_path": str(private_path),
                "individual_explanations_sha256": sha256_file(private_path)}
    (output_dir / "p3_004_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--p3-002-aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    resolved_output = args.output_dir.resolve()
    if resolved_output == ROOT or ROOT in resolved_output.parents:
        raise ValueError("P3-004 aggregate and individual outputs must remain outside the repository.")
    aggregate = run(args.dataset, args.source_manifest, args.p3_002_aggregate, resolved_output)
    print(json.dumps({"explanation": aggregate["explanation"],
                      "development_top_features": aggregate["development"]["overall_importance"][:6],
                      "development_correlated_groups": aggregate["development"]["correlations"]["connected_feature_groups"],
                      "runtime": aggregate["runtime"], "figures": aggregate["figures"]}, indent=2))


if __name__ == "__main__":
    main()

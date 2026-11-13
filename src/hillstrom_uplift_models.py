"""P3-008B development-only causal learners for the Hillstrom email experiment.

The loader skips test rows before parsing outcomes. No function in this module
fits, scores, or reads test outcomes; locked evaluation belongs to P3-008C.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hillstrom_causal_audit import (  # noqa: E402
    ARMS, DEFAULT_DATA, DEFAULT_OUTPUT, FEATURES, SEED, sha256,
)

DATA_SHA256 = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
SPLIT_SHA256 = "0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce"
SPLIT_PATH = DEFAULT_OUTPUT / "hillstrom_row_split_private.csv"
OUTPUT_PATH = ROOT.parent / "source_data/hillstrom/p3_008b_outputs"
TRAIN_ARM_LABELS = ("Mens E-Mail", "No E-Mail")
NUMERIC = ("recency", "history", "mens", "womens", "newbie")
CATEGORICAL = ("history_segment", "zip_code", "channel")
OUTCOME = "visit"
TREATMENT = "treatment"
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 20261115
TIE_SEED = 20261116
N_FOLDS = 5
BUDGETS = (0.10, 0.20, 0.30)

SELECTION_ORDER = (
    "constant_ate",
    "t_logistic",
    "s_logistic",
    "x_logistic",
    "dr_logistic",
    "t_hgb",
    "s_hgb",
    "x_hgb",
    "dr_hgb",
)
# P3-008A deferred XGBoost from formal selection. Keep its fitted output as a
# supplementary descriptive benchmark, outside the promotion sequence.
SUPPLEMENTARY_ORDER = ("t_xgboost_optional",)
CANDIDATE_ORDER = ("constant_ate", "history_recency") + SELECTION_ORDER[1:] + SUPPLEMENTARY_ORDER


def _preprocessor(kind: str, include_treatment: bool = False) -> ColumnTransformer:
    numeric = list(NUMERIC) + ([TREATMENT] if include_treatment else [])
    if kind == "logistic":
        num_pipe = Pipeline([("impute", SimpleImputer(strategy="median")),
                             ("scale", StandardScaler())])
        cat_pipe = Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                             ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    else:
        num_pipe = Pipeline([("impute", SimpleImputer(strategy="median"))])
        cat_pipe = Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                             ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))])
    return ColumnTransformer([("numeric", num_pipe, numeric),
                              ("categorical", cat_pipe, list(CATEGORICAL))],
                             remainder="drop", verbose_feature_names_out=False)


def _classifier(kind: str, include_treatment: bool = False) -> Pipeline:
    if kind == "logistic":
        estimator = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000,
                                       random_state=SEED)
    elif kind == "hgb":
        estimator = HistGradientBoostingClassifier(learning_rate=0.05, max_leaf_nodes=7,
            max_iter=100, min_samples_leaf=50, l2_regularization=1.0,
            early_stopping=False, random_state=SEED)
    elif kind == "xgboost":
        from xgboost import XGBClassifier
        estimator = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05,
            min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.0, reg_lambda=1.0, objective="binary:logistic",
            eval_metric="logloss", tree_method="hist", n_jobs=1,
            random_state=SEED, verbosity=0)
    else:
        raise ValueError(f"Unknown learner kind: {kind}")
    return Pipeline([("preprocess", _preprocessor(kind, include_treatment)), ("model", estimator)])


def _regressor(kind: str) -> Pipeline:
    if kind == "logistic":
        estimator = Ridge(alpha=1.0)
    elif kind == "hgb":
        estimator = HistGradientBoostingRegressor(learning_rate=0.05, max_leaf_nodes=7,
            max_iter=100, min_samples_leaf=50, l2_regularization=1.0,
            early_stopping=False, random_state=SEED)
    elif kind == "xgboost":
        from xgboost import XGBRegressor
        estimator = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05,
            min_child_weight=10, subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.0, reg_lambda=1.0, objective="reg:squarederror",
            tree_method="hist", n_jobs=1, random_state=SEED, verbosity=0)
    else:
        raise ValueError(f"Unknown learner kind: {kind}")
    return Pipeline([("preprocess", _preprocessor(kind)), ("model", estimator)])


def map_binary_treatment(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep only Men's email/control and map Men's assignment to one."""
    out = frame.loc[frame.segment.isin(TRAIN_ARM_LABELS)].copy()
    out[TREATMENT] = out.segment.eq("Mens E-Mail").astype(np.int8)
    if set(out[TREATMENT].unique()) != {0, 1}:
        raise ValueError("Both Men's email and no-email assignments are required.")
    return out


def load_train_development(data_path: Path = DEFAULT_DATA,
                           split_path: Path = SPLIT_PATH,
                           check_hashes: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Read train/development rows only; test rows are skipped before CSV parsing."""
    if check_hashes:
        if sha256(data_path) != DATA_SHA256:
            raise ValueError("Hillstrom source checksum differs from the frozen P3-008A file.")
        if sha256(split_path) != SPLIT_SHA256:
            raise ValueError("Hillstrom split checksum differs from frozen P3-008A membership.")
    split = pd.read_csv(split_path)
    if list(split.columns) != ["row_index", "split"] or (check_hashes and len(split) != 64000):
        raise ValueError("Unexpected frozen split schema or row count.")
    if set(split.split.unique()) != {"train", "development", "test"}:
        raise ValueError("Frozen split labels are incomplete.")
    keep = set(split.loc[split.split.isin(["train", "development"]), "row_index"].astype(int))
    usecols = list(FEATURES) + ["segment", OUTCOME]
    # pandas skiprows line numbers include header at 0; source row index = line - 1.
    rows = pd.read_csv(data_path, usecols=usecols,
                       skiprows=lambda line: line > 0 and (line - 1) not in keep)
    expected = len(keep)
    if len(rows) != expected:
        raise ValueError(f"Expected {expected} train/development rows, read {len(rows)}.")
    row_ids = np.array(sorted(keep), dtype=np.int64)
    rows.insert(0, "row_index", row_ids)
    rows = rows.merge(split, on="row_index", validate="one_to_one")
    if not rows[OUTCOME].isin([0, 1]).all():
        raise ValueError("Visit outcome must be binary in train/development rows.")
    rows = map_binary_treatment(rows)
    train = rows.loc[rows.split.eq("train")].reset_index(drop=True)
    development = rows.loc[rows.split.eq("development")].reset_index(drop=True)
    metadata = {"source_sha256": sha256(data_path), "split_sha256": sha256(split_path),
                "source_rows": 64000, "rows_parsed_before_arm_filter": expected,
                "test_rows_parsed": 0, "test_outcomes_accessed": False,
                "training_n_pairwise": len(train), "development_n_pairwise": len(development),
                "training_arm_counts": train[TREATMENT].value_counts().sort_index().to_dict(),
                "development_arm_counts": development[TREATMENT].value_counts().sort_index().to_dict()}
    return train, development, metadata


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(FEATURES) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing pre-treatment features: {sorted(missing)}")
    return frame.loc[:, list(FEATURES)].copy()


def _prob(model: Pipeline, x: pd.DataFrame) -> np.ndarray:
    classes = model.named_steps["model"].classes_
    positive_index = int(np.flatnonzero(classes == 1)[0])
    p = model.predict_proba(x)[:, positive_index]
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Outcome model produced invalid probabilities.")
    return p


def counterfactual_probabilities(model: Pipeline, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return (mu0, mu1) from an S-learner without mutating caller features."""
    x0 = x.copy(); x0[TREATMENT] = 0
    x1 = x.copy(); x1[TREATMENT] = 1
    return _prob(model, x0), _prob(model, x1)


def x_learner_combine(tau_treated: np.ndarray, tau_control: np.ndarray,
                      propensity: float) -> np.ndarray:
    """X-learner combination: e*tau_control + (1-e)*tau_treated."""
    if not 0 < propensity < 1:
        raise ValueError("Treatment propensity must lie strictly between zero and one.")
    return propensity * np.asarray(tau_control) + (1 - propensity) * np.asarray(tau_treated)


def dr_pseudo_outcome(y: np.ndarray, treatment: np.ndarray, mu0: np.ndarray,
                      mu1: np.ndarray, propensity: float) -> np.ndarray:
    """Cross-fitted DR score for tau=E[Y(1)-Y(0)|X]. No clipping of effect scores."""
    if not 0 < propensity < 1:
        raise ValueError("Treatment propensity must lie strictly between zero and one.")
    y = np.asarray(y, dtype=float); a = np.asarray(treatment, dtype=float)
    m0 = np.asarray(mu0, dtype=float); m1 = np.asarray(mu1, dtype=float)
    if not (y.shape == a.shape == m0.shape == m1.shape):
        raise ValueError("DR pseudo-outcome inputs must be aligned vectors.")
    return ((m1 - m0) + a / propensity * (y - m1)
            - (1 - a) / (1 - propensity) * (y - m0))


def _fit_arm_models(x: pd.DataFrame, a: np.ndarray, y: np.ndarray,
                    kind: str) -> tuple[Pipeline, Pipeline]:
    control = _classifier(kind).fit(x.loc[a == 0], y[a == 0])
    treated = _classifier(kind).fit(x.loc[a == 1], y[a == 1])
    return control, treated


def crossfit_dr_scores(x: pd.DataFrame, a: np.ndarray, y: np.ndarray,
                       kind: str = "logistic", n_splits: int = N_FOLDS,
                       seed: int = SEED) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[list[int]]]:
    """Create OOF mu0/mu1 and DR scores; return nuisance training indices per fold."""
    a = np.asarray(a, dtype=int); y = np.asarray(y, dtype=int)
    mu0 = np.full(len(y), np.nan); mu1 = np.full(len(y), np.nan)
    folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fit_indices: list[list[int]] = []
    for fit_idx, held_idx in folds.split(np.zeros(len(y)), a):
        m0, m1 = _fit_arm_models(x.iloc[fit_idx], a[fit_idx], y[fit_idx], kind)
        mu0[held_idx] = _prob(m0, x.iloc[held_idx])
        mu1[held_idx] = _prob(m1, x.iloc[held_idx])
        fit_indices.append(fit_idx.tolist())
    if np.isnan(mu0).any() or np.isnan(mu1).any():
        raise RuntimeError("Cross-fitting left nuisance predictions missing.")
    e = float(a.mean())
    return mu0, mu1, dr_pseudo_outcome(y, a, mu0, mu1, e), fit_indices


def _fit_cate_models(train: pd.DataFrame, e: float) -> tuple[dict[str, object], dict[str, dict]]:
    x = _feature_frame(train); a = train[TREATMENT].to_numpy(int); y = train[OUTCOME].to_numpy(int)
    models: dict[str, object] = {}
    diagnostics: dict[str, dict] = {}

    # T-learners.
    for kind, name in [("logistic", "t_logistic"), ("hgb", "t_hgb")]:
        m0, m1 = _fit_arm_models(x, a, y, kind)
        models[name] = ("t", kind, m0, m1)

    # Optional XGBoost comparison: one fixed CPU T-learner configuration.
    m0, m1 = _fit_arm_models(x, a, y, "xgboost")
    models["t_xgboost_optional"] = ("t", "xgboost", m0, m1)

    # S-learners.
    for kind, name in [("logistic", "s_logistic"), ("hgb", "s_hgb")]:
        x_t = x.copy(); x_t[TREATMENT] = a
        model = _classifier(kind, include_treatment=True).fit(x_t, y)
        models[name] = ("s", kind, model)

    # X-learners: opposite-arm nuisance predictions impute effects; Ridge or
    # bounded HGB regression estimates tau separately in each randomized arm.
    for kind, name in [("logistic", "x_logistic"), ("hgb", "x_hgb")]:
        m0, m1 = _fit_arm_models(x, a, y, kind)
        mu0_train = _prob(m0, x); mu1_train = _prob(m1, x)
        tau_treated = y[a == 1] - mu0_train[a == 1]
        tau_control = mu1_train[a == 0] - y[a == 0]
        tau1_model = _regressor(kind).fit(x.loc[a == 1], tau_treated)
        tau0_model = _regressor(kind).fit(x.loc[a == 0], tau_control)
        models[name] = ("x", kind, m0, m1, tau1_model, tau0_model, e)

    # DR learners: all pseudo-outcomes are generated from five-fold OOF models.
    for kind, name in [("logistic", "dr_logistic"), ("hgb", "dr_hgb")]:
        mu0_oof, mu1_oof, psi, fit_indices = crossfit_dr_scores(x, a, y, kind, N_FOLDS, SEED)
        final_model = _regressor(kind).fit(x, psi)
        m0_full, m1_full = _fit_arm_models(x, a, y, kind)
        models[name] = ("dr", kind, final_model, m0_full, m1_full)
        diagnostics[name] = {"crossfit_folds": N_FOLDS,
            "oof_mu0_min_max": [float(mu0_oof.min()), float(mu0_oof.max())],
            "oof_mu1_min_max": [float(mu1_oof.min()), float(mu1_oof.max())],
            "dr_score_min_max": [float(psi.min()), float(psi.max())],
            "fold_fit_row_counts": [len(f) for f in fit_indices],
            "self_prediction_excluded": True}

    # S-learner predictions use probability-scale counterfactuals. X/DR CATE
    # regressions are intentionally not clipped to [0,1].
    return models, diagnostics


def predict_cate(model_spec: tuple, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tag = model_spec[0]
    if tag == "s":
        _, kind, model = model_spec
        mu0, mu1 = counterfactual_probabilities(model, x)
        return mu1 - mu0, mu0, mu1
    if tag == "t":
        _, kind, m0, m1 = model_spec
        mu0, mu1 = _prob(m0, x), _prob(m1, x)
        return mu1 - mu0, mu0, mu1
    if tag == "x":
        _, kind, m0, m1, tau1_model, tau0_model, e = model_spec
        mu0, mu1 = _prob(m0, x), _prob(m1, x)
        tau = x_learner_combine(tau1_model.predict(x), tau0_model.predict(x), e)
        return tau, mu0, mu1
    if tag == "dr":
        _, kind, final_model, m0, m1 = model_spec
        mu0, mu1 = _prob(m0, x), _prob(m1, x)
        return final_model.predict(x), mu0, mu1
    raise ValueError(f"Unsupported fitted model specification: {model_spec!r}")


def fit_s_learner(x: pd.DataFrame, a: np.ndarray, y: np.ndarray, kind: str) -> Pipeline:
    x_t = x.copy(); x_t[TREATMENT] = np.asarray(a, dtype=int)
    return _classifier(kind, include_treatment=True).fit(x_t, y)


def select_top_budget(scores: np.ndarray, tie_priority: np.ndarray,
                      budget: float) -> np.ndarray:
    """Select exactly ceil(budget*n), including negative-score rows if needed."""
    scores = np.asarray(scores, dtype=float); tie_priority = np.asarray(tie_priority)
    if scores.ndim != 1 or scores.shape != tie_priority.shape or not 0 < budget <= 1:
        raise ValueError("Invalid policy scores, tie priorities, or treatment budget.")
    n_select = int(np.ceil(budget * len(scores)))
    order = np.lexsort((tie_priority, -scores))
    selected = np.zeros(len(scores), dtype=bool); selected[order[:n_select]] = True
    return selected


def _policy_score(policy: np.ndarray, y: np.ndarray, a: np.ndarray,
                  propensity: float, mu0: np.ndarray, mu1: np.ndarray,
                  estimator: str) -> float:
    policy = np.asarray(policy, dtype=int); y = np.asarray(y, dtype=float); a = np.asarray(a, dtype=int)
    m_policy = np.where(policy == 1, mu1, mu0)
    if estimator == "dr":
        m_observed = np.where(a == 1, mu1, mu0)
        p_observed = np.where(a == 1, propensity, 1 - propensity)
        return float(np.mean(m_policy + (policy == a) * (y - m_observed) / p_observed))
    if estimator == "ipw":
        p_policy = np.where(policy == 1, propensity, 1 - propensity)
        return float(np.mean((policy == a) * y / p_policy))
    raise ValueError("estimator must be 'dr' or 'ipw'")


def policy_values(y: np.ndarray, a: np.ndarray, policy: np.ndarray,
                  propensity: float, mu0: np.ndarray, mu1: np.ndarray) -> dict[str, float]:
    control = np.zeros(len(y), dtype=int)
    return {"ipw_value": _policy_score(policy, y, a, propensity, mu0, mu1, "ipw"),
            "ipw_increment_vs_none": _policy_score(policy, y, a, propensity, mu0, mu1, "ipw")
                                     - _policy_score(control, y, a, propensity, mu0, mu1, "ipw"),
            "dr_value": _policy_score(policy, y, a, propensity, mu0, mu1, "dr"),
            "dr_increment_vs_none": _policy_score(policy, y, a, propensity, mu0, mu1, "dr")
                                    - _policy_score(control, y, a, propensity, mu0, mu1, "dr")}


def uplift_curve(scores: np.ndarray, y: np.ndarray, a: np.ndarray,
                 propensity: float, tie_priority: np.ndarray,
                 grid: np.ndarray | None = None) -> dict:
    """IPW Qini gain per 1,000 eligible rows and AUUC above random targeting."""
    scores = np.asarray(scores, dtype=float); y = np.asarray(y, dtype=float); a = np.asarray(a, dtype=int)
    n = len(y); order = np.lexsort((tie_priority, -scores))
    contribution = a * y / propensity - (1 - a) * y / (1 - propensity)
    cumulative = np.r_[0.0, np.cumsum(contribution[order])]
    q = np.arange(n + 1) / n
    gain = cumulative / n * 1000
    full_ate = float(contribution.mean())
    random = q * full_ate * 1000
    if grid is None:
        grid = np.unique(np.r_[np.linspace(0, 1, 101),
                               [min(1.0, np.ceil(b * n) / n) for b in BUDGETS]])
    idx = np.minimum(n, np.ceil(np.asarray(grid) * n).astype(int))
    curve_gain = cumulative[idx] / n * 1000
    curve_random = (idx / n) * full_ate * 1000
    auuc = float(np.trapezoid(curve_gain - curve_random, idx / n))
    uplift_at = {}
    for budget in BUDGETS:
        k = int(np.ceil(budget * n))
        uplift_at[f"{int(budget*100)}%"] = float(cumulative[k] / n * 1000)
    return {"grid_fraction": (idx / n).tolist(), "gain_per_1000": curve_gain.tolist(),
            "random_reference_per_1000": curve_random.tolist(), "auuc_per_1000": auuc,
            "full_population_ipw_ate": full_ate, "uplift_per_1000_population": uplift_at}


def _candidate_policy(scores: np.ndarray, tie: np.ndarray, budget: float) -> np.ndarray:
    return select_top_budget(scores, tie, budget).astype(int)


def paired_policy_bootstrap(scores_candidate: np.ndarray, scores_incumbent: np.ndarray,
                            tie_priority: np.ndarray, y: np.ndarray, a: np.ndarray,
                            propensity: float, mu0: np.ndarray, mu1: np.ndarray,
                            budget: float = 0.20, reps: int = BOOTSTRAP_REPS,
                            seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    """Paired row bootstrap of DR policy-value difference, holding scores fixed."""
    rng = np.random.default_rng(seed); n = len(y); deltas = np.empty(reps)
    for b in range(reps):
        idx = rng.integers(0, n, size=n)
        p_c = _candidate_policy(scores_candidate[idx], tie_priority[idx], budget)
        p_i = _candidate_policy(scores_incumbent[idx], tie_priority[idx], budget)
        v_c = _policy_score(p_c, y[idx], a[idx], propensity, mu0[idx], mu1[idx], "dr")
        v_i = _policy_score(p_i, y[idx], a[idx], propensity, mu0[idx], mu1[idx], "dr")
        deltas[b] = (v_c - v_i) * 1000
    return {"delta_point_per_1000": float(
                (_policy_score(_candidate_policy(scores_candidate, tie_priority, budget), y, a,
                               propensity, mu0, mu1, "dr")
                 - _policy_score(_candidate_policy(scores_incumbent, tie_priority, budget), y, a,
                                 propensity, mu0, mu1, "dr")) * 1000),
            "ci95_low": float(np.quantile(deltas, .025)),
            "ci95_high": float(np.quantile(deltas, .975)),
            "bootstrap_reps": reps, "seed": seed}


def dr_ate_increment(y: np.ndarray, a: np.ndarray, propensity: float,
                     mu0: np.ndarray, mu1: np.ndarray) -> float:
    """DR treat-all minus treat-none value, in outcome units per eligible row."""
    all_treated = np.ones(len(y), dtype=int)
    none = np.zeros(len(y), dtype=int)
    return (_policy_score(all_treated, y, a, propensity, mu0, mu1, "dr")
            - _policy_score(none, y, a, propensity, mu0, mu1, "dr"))


def expected_random_dr_increment(y: np.ndarray, a: np.ndarray, propensity: float,
                                 mu0: np.ndarray, mu1: np.ndarray,
                                 budget: float = 0.20) -> float:
    """Expected random-targeting gain: budget times full-population DR ATE."""
    return float(budget * dr_ate_increment(y, a, propensity, mu0, mu1))


def paired_expected_random_bootstrap(scores: np.ndarray, tie_priority: np.ndarray,
                                     y: np.ndarray, a: np.ndarray, propensity: float,
                                     mu0: np.ndarray, mu1: np.ndarray,
                                     budget: float = 0.20, reps: int = BOOTSTRAP_REPS,
                                     seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    """Paired score-minus-expected-random interval, recomputing ATE per resample."""
    point = ( _policy_score(_candidate_policy(scores, tie_priority, budget), y, a,
                            propensity, mu0, mu1, "dr")
              - _policy_score(np.zeros(len(y), dtype=int), y, a, propensity,
                              mu0, mu1, "dr")
              - expected_random_dr_increment(y, a, propensity, mu0, mu1, budget)) * 1000
    rng = np.random.default_rng(seed); n = len(y); deltas = np.empty(reps)
    for b in range(reps):
        idx = rng.integers(0, n, size=n)
        policy = _candidate_policy(scores[idx], tie_priority[idx], budget)
        candidate_inc = (_policy_score(policy, y[idx], a[idx], propensity,
                                       mu0[idx], mu1[idx], "dr")
                         - _policy_score(np.zeros(n, dtype=int), y[idx], a[idx],
                                         propensity, mu0[idx], mu1[idx], "dr"))
        # The expected-random reference is re-estimated inside this same paired
        # resample; a full-sample constant would understate its uncertainty.
        random_inc = expected_random_dr_increment(y[idx], a[idx], propensity,
                                                 mu0[idx], mu1[idx], budget)
        deltas[b] = (candidate_inc - random_inc) * 1000
    return {"delta_point_per_1000": float(point),
            "ci95_low": float(np.quantile(deltas, .025)),
            "ci95_high": float(np.quantile(deltas, .975)),
            "bootstrap_reps": reps, "seed": seed,
            "reference": "budget × DR ATE recomputed within each bootstrap resample"}


def promote_candidate(ci95_low: float) -> bool:
    """Frozen P3-008A rule: require a positive lower paired 95% bound."""
    return bool(np.isfinite(ci95_low) and ci95_low > 0)


def select_formal_policy(scores: dict[str, np.ndarray], tie_priority: np.ndarray,
                         y: np.ndarray, a: np.ndarray, propensity: float,
                         mu0: np.ndarray, mu1: np.ndarray,
                         reps: int = BOOTSTRAP_REPS) -> tuple[str, list[dict]]:
    """Apply the frozen sequential promotion rule to formal candidates only."""
    incumbent = "constant_ate"; comparisons = []
    for name in SELECTION_ORDER[1:]:
        comp = paired_policy_bootstrap(scores[name], scores[incumbent], tie_priority,
            y, a, propensity, mu0, mu1, budget=.20, reps=reps, seed=BOOTSTRAP_SEED)
        promoted = promote_candidate(comp["ci95_low"])
        comparisons.append({"candidate": name, "incumbent_before": incumbent,
                            **comp, "promoted": promoted,
                            "rule": "promote iff paired 95% lower bound > 0"})
        if promoted:
            incumbent = name
    return incumbent, comparisons


def _historical_scores(x: pd.DataFrame, tie: np.ndarray) -> np.ndarray:
    order = np.lexsort((tie, x.recency.to_numpy(float), -x.history.to_numpy(float)))
    rank = np.empty(len(order), dtype=float); rank[order] = np.arange(len(order))
    return -rank


def _metrics_for_candidate(name: str, scores: np.ndarray, mu0: np.ndarray, mu1: np.ndarray,
                           policy_mu0: np.ndarray, policy_mu1: np.ndarray,
                           dev: pd.DataFrame, propensity: float, tie: np.ndarray) -> tuple[dict, dict]:
    y = dev[OUTCOME].to_numpy(int); a = dev[TREATMENT].to_numpy(int)
    curve = uplift_curve(scores, y, a, propensity, tie)
    policies = {}
    for budget in BUDGETS:
        policy = _candidate_policy(scores, tie, budget)
        val = policy_values(y, a, policy, propensity, policy_mu0, policy_mu1)
        policies[f"{int(budget*100)}%"] = {k: float(v * 1000) for k, v in val.items()}
        policies[f"{int(budget*100)}%"].update({"selected_n": int(policy.sum()),
                                                  "eligible_n": int(len(policy))})
    score_is_constant = np.ptp(scores) < 1e-12
    rho = spearmanr(scores, mu1).statistic if not score_is_constant and np.std(mu1) > 0 else np.nan
    is_cate = name != "history_recency"
    summary = {"candidate": name,
        "score_type": "estimated_CATE" if is_cate else "historical_behavior_rank_only",
        "cate_mean": float(np.mean(scores)) if is_cate else None,
        "cate_sd": (0.0 if score_is_constant else float(np.std(scores, ddof=1))) if is_cate else None,
        "cate_median": float(np.median(scores)) if is_cate else None,
        "cate_p10": float(np.quantile(scores, .10)) if is_cate else None,
        "cate_p90": float(np.quantile(scores, .90)) if is_cate else None,
        "cate_negative_share": float(np.mean(scores < 0)) if is_cate else None,
        "cate_positive_share": float(np.mean(scores > 0)) if is_cate else None,
        "mu1_mean": float(np.mean(mu1)), "mu0_mean": float(np.mean(mu0)),
        "cate_visit_propensity_spearman": float(rho) if is_cate and np.isfinite(rho) else None,
        "score_visit_propensity_spearman": float(rho) if np.isfinite(rho) else None,
        "auuc_per_1000": curve["auuc_per_1000"],
        "uplift_per_1000_population": curve["uplift_per_1000_population"],
        "policies_per_1000": policies}
    return summary, curve


def run_experiment(data_path: Path = DEFAULT_DATA, split_path: Path = SPLIT_PATH,
                   output_dir: Path = OUTPUT_PATH, bootstrap_reps: int = BOOTSTRAP_REPS) -> dict:
    start = time.perf_counter()
    train, dev, input_meta = load_train_development(data_path, split_path, check_hashes=True)
    x_train = _feature_frame(train); x_dev = _feature_frame(dev)
    a_train = train[TREATMENT].to_numpy(int); y_train = train[OUTCOME].to_numpy(int)
    a_dev = dev[TREATMENT].to_numpy(int); y_dev = dev[OUTCOME].to_numpy(int)
    e_train = float(a_train.mean()); e_dev = float(a_dev.mean())
    if not 0 < e_train < 1 or not 0 < e_dev < 1:
        raise ValueError("Both treatment arms must be represented in every used split.")
    tie = np.random.default_rng(TIE_SEED).random(len(dev))
    with threadpool_limits(limits=1):
        models, dr_diag = _fit_cate_models(train, e_train)
        fitted: dict[str, dict] = {}
        for name, spec in models.items():
            cate, mu0, mu1 = predict_cate(spec, x_dev)
            fitted[name] = {"cate": np.asarray(cate, dtype=float),
                            "mu0": np.asarray(mu0, dtype=float),
                            "mu1": np.asarray(mu1, dtype=float)}

    # Constant-effect and behavior-ranking policies are predeclared baselines.
    train_means = {"control_visit_rate": float(y_train[a_train == 0].mean()),
                   "treated_visit_rate": float(y_train[a_train == 1].mean())}
    constant = train_means["treated_visit_rate"] - train_means["control_visit_rate"]
    score_specs: dict[str, np.ndarray] = {"constant_ate": np.full(len(dev), constant),
        "history_recency": _historical_scores(x_dev, tie)}
    score_specs.update({name: fitted[name]["cate"] for name in models})
    # Policy-value nuisances are the simple logistic T-learner fit on training
    # only; shared across all candidate policies for like-for-like DR scoring.
    logit_m0, logit_m1 = _fit_arm_models(x_train, a_train, y_train, "logistic")
    policy_mu0 = _prob(logit_m0, x_dev); policy_mu1 = _prob(logit_m1, x_dev)

    summaries: dict[str, dict] = {}; curves: dict[str, dict] = {}
    for name in CANDIDATE_ORDER:
        if name in ("constant_ate", "history_recency"):
            if name == "constant_ate":
                m0 = np.full(len(dev), train_means["control_visit_rate"])
                m1 = np.full(len(dev), train_means["treated_visit_rate"])
            else:
                m0, m1 = policy_mu0, policy_mu1
        else:
            m0, m1 = fitted[name]["mu0"], fitted[name]["mu1"]
        summaries[name], curves[name] = _metrics_for_candidate(
            name, score_specs[name], m0, m1, policy_mu0, policy_mu1, dev, e_dev, tie)

    cate_names = [name for name in CANDIDATE_ORDER
                  if name not in ("constant_ate", "history_recency")]
    rank_agreement = []
    for i, left in enumerate(cate_names):
        for right in cate_names[i + 1:]:
            left_top = _candidate_policy(score_specs[left], tie, .20).astype(bool)
            right_top = _candidate_policy(score_specs[right], tie, .20).astype(bool)
            union = int(np.sum(left_top | right_top))
            rank_agreement.append({"model_left": left, "model_right": right,
                "cate_spearman": float(spearmanr(score_specs[left], score_specs[right]).statistic),
                "top20_jaccard": float(np.sum(left_top & right_top) / union) if union else 1.0})

    # Paired uncertainty-aware complexity selection. A more complex policy
    # replaces the incumbent only when its paired 95% interval is wholly > 0.
    incumbent, selection = select_formal_policy(score_specs, tie, y_dev, a_dev,
        e_dev, policy_mu0, policy_mu1, reps=bootstrap_reps)
    history_comparison = paired_policy_bootstrap(score_specs["history_recency"],
        score_specs["constant_ate"], tie, y_dev, a_dev, e_dev,
        policy_mu0, policy_mu1, reps=bootstrap_reps, seed=BOOTSTRAP_SEED)
    expected_random = _expected_random_summary(dev, score_specs, tie, e_dev,
                                               policy_mu0, policy_mu1,
                                               bootstrap_reps)

    # Development ATE only; this is a model-development diagnostic, not the
    # confirmatory test estimand planned for P3-008C.
    dev_ate = float(y_dev[a_dev == 1].mean() - y_dev[a_dev == 0].mean())
    full_ipw_ate = float(np.mean(a_dev * y_dev / e_dev
                           - (1 - a_dev) * y_dev / (1 - e_dev)))
    n = len(dev); order_idx = np.arange(n)
    pred_rows = pd.DataFrame({"row_index": dev.row_index.to_numpy(),
        "treatment": a_dev, "visit": y_dev,
        **{f"cate_{name}": score_specs[name] for name in CANDIDATE_ORDER},
        **{f"mu1_{name}": fitted[name]["mu1"] for name in models},
        **{f"mu0_{name}": fitted[name]["mu0"] for name in models}})
    output_dir.mkdir(parents=True, exist_ok=True)
    pred_path = output_dir / "hillstrom_development_predictions_private.parquet"
    pred_rows.to_parquet(pred_path, index=False)
    elapsed = time.perf_counter() - start
    result = {
        "experiment": "COMMERCIAL_DS_P3_008B",
        "scope": "development only; test rows skipped before outcome parsing",
        "input": input_meta,
        "population": {"train_n": len(train), "development_n": len(dev),
            "train_treatment_counts": {"control": int((a_train == 0).sum()),
                                       "mens_email": int((a_train == 1).sum())},
            "development_treatment_counts": {"control": int((a_dev == 0).sum()),
                                              "mens_email": int((a_dev == 1).sum())},
            "treatment_propensity_train": e_train, "treatment_propensity_development": e_dev,
            "women_arm_excluded": True, "feature_names": list(FEATURES),
            "test_outcomes_accessed": False},
        "training_baseline": {**train_means, "constant_ate": constant,
            "training_visit_events": int(y_train.sum()),
            "development_observed_visit_difference_diagnostic": dev_ate,
            "development_ipw_ate_diagnostic": full_ipw_ate},
        "configurations": {
            "logistic": {"C": 1.0, "penalty": "l2", "solver": "lbfgs", "max_iter": 1000},
            "hgb": {"learning_rate": .05, "max_leaf_nodes": 7, "max_iter": 100,
                    "min_samples_leaf": 50, "l2_regularization": 1.0,
                    "early_stopping": False},
            "xgboost": {"n_estimators": 100, "max_depth": 3, "learning_rate": .05,
                        "min_child_weight": 10, "subsample": .8, "colsample_bytree": .8,
                        "reg_alpha": 0.0, "reg_lambda": 1.0, "tree_method": "hist", "n_jobs": 1},
            "x_learner_second_stage": {"logistic_base": "Ridge(alpha=1.0)",
                                        "hgb_base": "HistGradientBoostingRegressor; same fixed tree settings"},
            "dr_crossfit_folds": N_FOLDS,
            "selection_order": list(SELECTION_ORDER),
            "supplementary_models": list(SUPPLEMENTARY_ORDER),
            "candidate_order": list(CANDIDATE_ORDER),
            "policy_value_selection": "20% exactly ceil(n*budget), promote iff paired 95% lower bound > 0",
            "bootstrap_replicates": bootstrap_reps, "bootstrap_seed": BOOTSTRAP_SEED,
            "tie_seed": TIE_SEED, "random_state": SEED},
        "dr_crossfit_diagnostics": dr_diag,
        "development_metrics": summaries,
        "cate_rank_agreement": rank_agreement,
        "development_qini_curves": curves,
        "selection_comparisons": selection,
        "baseline_comparisons": [{"candidate": "history_recency",
            "reference": "constant_ate", **history_comparison,
            "eligible_for_model_selection": False}],
        "expected_random_reference": expected_random["reference"],
        "expected_random_comparisons": expected_random["comparisons"],
        "selected_policy": incumbent,
        "artifacts": {"development_predictions_private": str(pred_path),
                      "development_predictions_sha256": sha256(pred_path),
                      "aggregate_json": str(output_dir / "hillstrom_uplift_aggregate_private.json")},
        "runtime_seconds": elapsed,
        "estimator_fit_calls": 44,
        "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__, "pandas_version": pd.__version__,
        "scipy_version": scipy.__version__, "scikit_learn_version": sklearn.__version__,
        "xgboost_version": xgboost.__version__}
    aggregate_path = output_dir / "hillstrom_uplift_aggregate_private.json"
    aggregate_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _write_figures(result, output_dir)
    return result


def _expected_random_summary(dev: pd.DataFrame, scores: dict[str, np.ndarray],
                             tie: np.ndarray, propensity: float,
                             mu0: np.ndarray, mu1: np.ndarray,
                             reps: int = BOOTSTRAP_REPS) -> dict:
    y = dev[OUTCOME].to_numpy(int); a = dev[TREATMENT].to_numpy(int)
    ate = dr_ate_increment(y, a, propensity, mu0, mu1)
    point_by_budget = {f"{int(q * 100)}%": {
        "dr_ate_per_1000": float(ate * 1000),
        "expected_random_increment_per_1000": float(q * ate * 1000)}
        for q in BUDGETS}
    comparison_order = ["constant_ate", "history_recency"] + [
        name for name in SELECTION_ORDER[1:]] + list(SUPPLEMENTARY_ORDER)
    comparisons = []
    for name in comparison_order:
        comp = paired_expected_random_bootstrap(scores[name], tie, y, a,
            propensity, mu0, mu1, budget=.20, reps=reps, seed=BOOTSTRAP_SEED)
        comparisons.append({"candidate": name, **comp,
                            "formal_promotion_candidate": name in SELECTION_ORDER[1:]})
    return {"reference": {"method": "expected random targeting",
                           "dr_ate_increment_per_1000": float(ate * 1000),
                           "budgets": point_by_budget,
                           "bootstrap_reference_rule":
                               "recompute q × DR ATE inside each paired resample",
                           "nuisance_fit_scope": "training split only"},
            "comparisons": comparisons}


def reevaluate_saved_predictions(prediction_path: Path, aggregate_path: Path,
                                 bootstrap_reps: int = BOOTSTRAP_REPS) -> dict:
    """Update policy references from frozen predictions without fitting models."""
    result = json.loads(aggregate_path.read_text(encoding="utf-8"))
    if "development only" not in result.get("scope", ""):
        raise ValueError("Expected a development-only aggregate artifact.")
    expected_hash = result.get("artifacts", {}).get("development_predictions_sha256")
    if not expected_hash or sha256(prediction_path) != expected_hash:
        raise ValueError("Saved development predictions do not match the recorded artifact hash.")
    frame = pd.read_parquet(prediction_path)
    needed = {"treatment", "visit", "mu0_t_logistic", "mu1_t_logistic"}
    needed |= {f"cate_{name}" for name in CANDIDATE_ORDER}
    if not needed.issubset(frame.columns):
        raise ValueError("Stored predictions do not match the P3-008B schema.")
    y = frame[OUTCOME].to_numpy(int); a = frame[TREATMENT].to_numpy(int)
    e = float(a.mean()); tie = np.random.default_rng(TIE_SEED).random(len(frame))
    scores = {name: frame[f"cate_{name}"].to_numpy(float) for name in CANDIDATE_ORDER}
    mu0 = frame["mu0_t_logistic"].to_numpy(float)
    mu1 = frame["mu1_t_logistic"].to_numpy(float)
    incumbent, selection = select_formal_policy(scores, tie, y, a, e, mu0, mu1,
                                                reps=bootstrap_reps)
    history = paired_policy_bootstrap(scores["history_recency"], scores["constant_ate"],
        tie, y, a, e, mu0, mu1, budget=.20, reps=bootstrap_reps,
        seed=BOOTSTRAP_SEED)
    expected = _expected_random_summary(frame, scores, tie, e, mu0, mu1,
                                       bootstrap_reps)
    result["selection_comparisons"] = selection
    result["baseline_comparisons"] = [{"candidate": "history_recency",
        "reference": "constant_ate", **history,
        "eligible_for_model_selection": False}]
    result["expected_random_reference"] = expected["reference"]
    result["expected_random_comparisons"] = expected["comparisons"]
    result["selected_policy"] = incumbent
    result["configurations"]["selection_order"] = list(SELECTION_ORDER)
    result["configurations"]["supplementary_models"] = list(SUPPLEMENTARY_ORDER)
    result["configurations"]["candidate_order"] = list(CANDIDATE_ORDER)
    result["re_evaluation"] = {"used_saved_predictions": True,
        "model_fit_calls": 0, "prediction_sha256": sha256(prediction_path),
        "test_outcomes_accessed": False}
    aggregate_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                              encoding="utf-8")
    _write_figures(result, aggregate_path.parent)
    return result


def _write_figures(result: dict, output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    figures = ROOT / "docs/research/figures"
    figures.mkdir(parents=True, exist_ok=True)
    metrics = result["development_metrics"]
    curves = result["development_qini_curves"]
    labels = list(result["configurations"]["candidate_order"])
    pretty = [x.replace("_", " ") for x in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, label in zip(labels, pretty):
        curve = curves[name]
        ax.plot(curve["grid_fraction"], curve["gain_per_1000"], label=label)
    first = curves[labels[0]]
    ax.plot(first["grid_fraction"], first["random_reference_per_1000"],
            color="black", linestyle="--", linewidth=1.5, label="Random targeting")
    ax.set(xlabel="Fraction targeted", ylabel="Cumulative incremental visits per 1,000 eligible",
           title="Development uplift gain (IPW; exploratory selection data)")
    ax.legend(fontsize=7, ncol=2); fig.tight_layout()
    fig.savefig(figures / "p3_008b_development_uplift_curves.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    cate_labels = [n for n in labels if n != "history_recency"]
    cate_pretty = [n.replace("_", " ") for n in cate_labels]
    vals = [metrics[n]["cate_negative_share"] for n in cate_labels]
    pos = [metrics[n]["cate_positive_share"] for n in cate_labels]
    x = np.arange(len(cate_labels)); ax.bar(x, pos, label="Positive CATE")
    ax.bar(x, vals, bottom=pos, label="Negative CATE", color="tab:red")
    ax.set_xticks(x, cate_pretty, rotation=35, ha="right")
    ax.set(ylabel="Development share", title="Estimated CATE sign by candidate")
    ax.legend(); fig.tight_layout()
    fig.savefig(figures / "p3_008b_cate_signs.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    expected = result["expected_random_reference"]["budgets"]
    for budget in BUDGETS:
        key = f"{int(budget*100)}%"
        vals = [metrics[n]["policies_per_1000"][key]["dr_increment_vs_none"] for n in labels]
        line, = ax.plot(pretty, vals, marker="o", label=f"Model policy {key}")
        ax.axhline(expected[key]["expected_random_increment_per_1000"],
                   color=line.get_color(), linestyle="--", linewidth=1.2,
                   label=f"Expected random {key}")
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(np.arange(len(labels)), pretty, rotation=35, ha="right")
    ax.set(ylabel="DR incremental visits per 1,000 eligible",
           title="Development policy value versus treat-none")
    ax.legend(title="Exact budget", loc="center left", bbox_to_anchor=(1.02, .5),
              fontsize=8)
    fig.tight_layout(rect=(0, 0, .76, 1))
    fig.savefig(figures / "p3_008b_policy_values.png", dpi=160); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--split", type=Path, default=SPLIT_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS)
    parser.add_argument("--reuse-predictions", action="store_true",
                        help="Re-evaluate saved development predictions without fitting models.")
    args = parser.parse_args()
    if ROOT == args.output_dir.resolve() or ROOT in args.output_dir.resolve().parents:
        raise ValueError("Private predictions and aggregates must remain outside Git.")
    if args.reuse_predictions:
        prediction_path = args.output_dir / "hillstrom_development_predictions_private.parquet"
        aggregate_path = args.output_dir / "hillstrom_uplift_aggregate_private.json"
        result = reevaluate_saved_predictions(prediction_path, aggregate_path,
                                              args.bootstrap_reps)
    else:
        result = run_experiment(args.data, args.split, args.output_dir, args.bootstrap_reps)
    print(json.dumps({"selected_policy": result["selected_policy"],
                      "development_metrics": result["development_metrics"],
                      "selection": result["selection_comparisons"],
                      "runtime_seconds": result["runtime_seconds"]}, indent=2))


if __name__ == "__main__":
    main()

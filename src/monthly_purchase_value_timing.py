"""P3-006 future value, purchase-count, and right-censored timing study."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor, TweedieRegressor
from sklearn.metrics import (mean_absolute_error, mean_squared_error,
                             mean_poisson_deviance, mean_tweedie_deviance)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "docs" / "recovery"))
import monthly_purchase_advanced_benchmark as p3  # noqa: E402
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256,
    LABEL_COLUMN, CUSTOMER_COLUMN, MONTH_COLUMN,
    sha256_file, verify_frozen_inputs,
)

CUSTOMER, MONTH, LABEL = CUSTOMER_COLUMN, MONTH_COLUMN, LABEL_COLUMN
DECISION = "decision_time"
FEATURES = tuple(FEATURE_COLUMNS)
SEED = 20261113
DATA_END = pd.Timestamp("2011-12-09 12:50:00")
HORIZONS = (30, 60, 90)
PRIMARY_HORIZON = 30
SECONDARY_HORIZON = 60
MIN_DEV_EVAL_ORIGINS = 4
DEV_MONTH_CANDIDATES = tuple(f"2011-{m:02d}" for m in range(3, 7))
AMOUNT_MODELS = ("Mean baseline", "Historical rate", "Tweedie", "Random Forest", "HistGradientBoosting", "Two-part")


def horizon_feasibility(frame: pd.DataFrame, data_end: pd.Timestamp = DATA_END) -> dict[str, Any]:
    decision = pd.to_datetime(frame[DECISION])
    rows = {}
    for h in HORIZONS:
        ends = decision + pd.to_timedelta(h, unit="D")
        mature = ends <= pd.Timestamp(data_end)
        part = frame.loc[mature]
        fold_candidates=[]
        for month in DEV_MONTH_CANDIDATES:
            val=frame.loc[frame[MONTH].astype(str).eq(month)&mature]
            if val.empty:continue
            boundary=pd.to_datetime(val[DECISION]).min()
            train=(decision<boundary)&((decision+pd.to_timedelta(h,unit="D"))<boundary)&mature
            if int(train.sum())>=1000:
                fold_candidates.append({"evaluation_month":month,"training_n":int(train.sum()),
                                        "evaluation_n":int(len(val)),
                                        "latest_training_target_end":str((decision[train]+pd.to_timedelta(h,unit="D")).max()),
                                        "evaluation_boundary":str(boundary)})
        rows[str(h)] = {"horizon_days": h, "mature_snapshots": int(mature.sum()),
                        "mature_months": sorted(part[MONTH].astype(str).unique().tolist()),
                        "monthly_counts": {str(k): int(v) for k,v in part.groupby(MONTH).size().items()},
                        "latest_decision_month": str(part[MONTH].max()) if len(part) else None,
                        "strict_pre_holdout_fold_candidates":fold_candidates,
                        "strict_pre_holdout_fold_count":len(fold_candidates)}
    return rows


def build_future_targets(snapshots: pd.DataFrame, occasions: list[dict[str, Any]],
                         *, data_end: pd.Timestamp = DATA_END,
                         horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    """Attach all qualifying occasion counts/spend; retain mature zero outcomes."""
    events: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    for occasion in occasions:
        key = str(occasion["customer_id"])
        date = pd.Timestamp(occasion["transaction_date"]).normalize()
        amount = float(occasion["qualifying_gross_merchandise"])
        if not np.isfinite(amount) or amount <= 0:
            raise ValueError("Canonical qualifying occasion values must be finite and positive.")
        events.setdefault(key, []).append((date, amount))
    for key in events:
        events[key].sort(key=lambda x:x[0])
    rows = snapshots.copy().reset_index(drop=True)
    rows[DECISION] = pd.to_datetime(rows[DECISION])
    for horizon in horizons:
        if horizon <= 0:
            raise ValueError("Horizons must be positive day counts.")
        end_col = f"value_end_{horizon}d"
        mature_col = f"value_mature_{horizon}d"
        spend_col = f"future_gross_{horizon}d"
        count_col = f"future_occasion_count_{horizon}d"
        ends = rows[DECISION] + pd.to_timedelta(horizon, unit="D")
        mature = ends <= pd.Timestamp(data_end)
        amounts = np.full(len(rows), np.nan, dtype=float)
        counts = np.full(len(rows), np.nan, dtype=float)
        for i, row in enumerate(rows.itertuples(index=False)):
            if not mature.iloc[i]:
                continue
            start = pd.Timestamp(getattr(row, DECISION)).normalize()
            stop = start + pd.Timedelta(days=horizon)
            purchases = [amount for date, amount in events.get(str(getattr(row, CUSTOMER)), ()) if start <= date < stop]
            amounts[i] = float(np.sum(purchases)) if purchases else 0.0
            counts[i] = float(len(purchases))
        rows[end_col] = ends
        rows[mature_col] = mature.to_numpy(bool)
        rows[spend_col] = amounts
        rows[count_col] = counts
    return rows


def make_value_folds(frame: pd.DataFrame, horizon: int) -> list[dict[str, Any]]:
    folds = []
    maturity_col = f"value_mature_{horizon}d"
    end_col = f"value_end_{horizon}d"
    target = f"future_gross_{horizon}d"
    for month in DEV_MONTH_CANDIDATES:
        validation = frame.loc[frame[MONTH].astype(str).eq(month) & frame[maturity_col]].copy().reset_index(drop=True)
        if validation.empty:
            continue
        boundary = pd.to_datetime(validation[DECISION]).min()
        train = frame.loc[
            pd.to_datetime(frame[DECISION]).lt(boundary)
            & pd.to_datetime(frame[end_col]).lt(boundary)
            & frame[maturity_col]
            & frame[target].notna()
        ].copy().reset_index(drop=True)
        if len(train) < 1000 or train[target].nunique() < 2:
            continue
        if not (pd.to_datetime(train[end_col]) < boundary).all():
            raise ValueError("Value-model training target not mature at its fold boundary.")
        if validation[target].isna().any() or not validation[maturity_col].all():
            raise ValueError("Value-model evaluation target is not fully mature.")
        folds.append({"month": month, "boundary": boundary, "train": train, "validation": validation})
    return folds


def feature_pipeline(estimator: Any, *, scale: bool = False) -> Pipeline:
    steps = [("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
             ("imputer", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scale", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)


def make_regressor(name: str) -> Pipeline:
    if name == "Tweedie":
        estimator = TweedieRegressor(power=1.5, alpha=1.0, link="log", max_iter=1000, tol=1e-7)
        return feature_pipeline(estimator, scale=True)
    if name == "Random Forest":
        estimator = RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=20,
                                          max_features="sqrt", n_jobs=1, random_state=SEED)
        return feature_pipeline(estimator)
    if name == "HistGradientBoosting":
        estimator = HistGradientBoostingRegressor(loss="poisson", learning_rate=0.05, max_iter=100,
                                                   max_leaf_nodes=7, min_samples_leaf=50,
                                                   l2_regularization=1.0, early_stopping=False,
                                                   random_state=SEED)
        return feature_pipeline(estimator)
    if name == "Count Poisson GLM":
        return feature_pipeline(PoissonRegressor(alpha=1.0, max_iter=1000, tol=1e-8), scale=True)
    raise ValueError(name)


def _fit_two_part(train: pd.DataFrame, x_valid: pd.DataFrame, target: str) -> tuple[np.ndarray, int]:
    x_train = train.loc[:, list(FEATURES)]
    y = train[target].to_numpy(float)
    prop_pipe = feature_pipeline(LogisticRegression(solver="lbfgs", C=1.0, max_iter=3000,
                                                      tol=1e-7, random_state=SEED), scale=True)
    prop_pipe.fit(x_train, (y > 0).astype(int))
    p = prop_pipe.predict_proba(x_valid.loc[:, list(FEATURES)])[:, int(np.flatnonzero(prop_pipe.classes_ == 1)[0])]
    positives = train.loc[y > 0]
    severity = make_regressor("Tweedie")
    severity.fit(positives.loc[:, list(FEATURES)], positives[target].to_numpy(float))
    conditional = np.maximum(0.0, severity.predict(x_valid.loc[:, list(FEATURES)]))
    return p * conditional, 2


def amount_metrics(frame: pd.DataFrame, prediction: np.ndarray, target: str) -> dict[str, float]:
    y = frame[target].to_numpy(float)
    p = np.maximum(0.0, np.asarray(prediction, dtype=float))
    if len(p) != len(y) or not np.isfinite(p).all() or not np.isfinite(y).all():
        raise ValueError("Monetary predictions and outcomes must align and be finite.")
    return {"n": int(len(y)), "zero_share": float(np.mean(y == 0)),
            "actual_mean": float(y.mean()), "predicted_mean": float(p.mean()),
            "mae": float(mean_absolute_error(y, p)),
            "rmse": float(np.sqrt(mean_squared_error(y, p))),
            "mean_bias_prediction_minus_actual": float(np.mean(p-y))}


def monthly_value_metrics(frame: pd.DataFrame, prediction: np.ndarray, target: str,
                          *, capacities: tuple[float, ...] = (0.10,)) -> dict[str, Any]:
    frame=frame.reset_index(drop=True)
    y = frame[target].to_numpy(float)
    p = np.maximum(0.0, np.asarray(prediction, dtype=float))
    out = {"overall": amount_metrics(frame, p, target), "monthly": {}, "top_decile_value": {}}
    for month, ix in frame.groupby(MONTH, sort=True).groups.items():
        idx = np.asarray(list(ix), dtype=int)
        g = frame.iloc[idx]
        out["monthly"][str(month)] = amount_metrics(g, p[idx], target)
        out["top_decile_value"][str(month)] = {}
        for cap in capacities:
            k = max(1, int(np.ceil(cap*len(idx))))
            ids = g[CUSTOMER].astype(str).to_numpy()
            order = np.lexsort((ids, -p[idx]))[:k]
            selected = idx[order]
            out["top_decile_value"][str(month)][str(cap)] = {
                "selected_n": int(k), "actual_spend_capture": float(y[selected].sum()/y[idx].sum()) if y[idx].sum() else None,
                "selected_mean_spend": float(y[selected].mean()), "monthly_total_spend": float(y[idx].sum())}
    return out


def paired_cluster_amount_bootstrap(frame: pd.DataFrame, predictions: dict[str, np.ndarray],
                                    baseline: str, target: str, *, reps: int = 500, seed: int = SEED) -> dict[str, Any]:
    ids, codes = np.unique(frame[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    y = frame[target].to_numpy(float)
    losses = {k: np.abs(np.maximum(0, v)-y) for k,v in predictions.items()}
    output = {}
    rng = np.random.Generator(np.random.PCG64(seed))
    base = losses[baseline]
    for name, value in losses.items():
        if name == baseline: continue
        delta = value-base
        draws = np.empty(reps)
        for r in range(reps):
            sampled = rng.integers(0, len(ids), size=len(ids))
            weights = np.bincount(sampled, minlength=len(ids))[codes]
            draws[r] = float(np.dot(weights, delta)/weights.sum())
        output[name] = {"delta_mae": float(delta.mean()), "ci95": [float(x) for x in np.percentile(draws,[2.5,97.5])],
                        "valid_resamples": reps}
    return {"baseline": baseline, "method": "paired customer-trajectory percentile bootstrap; conditional on fitted predictions",
            "seed": seed, "reps": reps, "comparisons": output}


def _first_events(occasions: list[dict[str, Any]]) -> dict[str, list[tuple[pd.Timestamp, str]]]:
    by_customer: dict[str, list[tuple[pd.Timestamp, str]]] = {}
    for occasion in occasions:
        by_customer.setdefault(str(occasion["customer_id"]), []).append(
            (pd.Timestamp(occasion["transaction_date"]).normalize(), str(occasion["invoice_id"])))
    for values in by_customer.values(): values.sort()
    return by_customer


def build_survival_outcomes(frame: pd.DataFrame, occasions: list[dict[str, Any]],
                            *, observation_end: pd.Timestamp = DATA_END,
                            censor_at: pd.Timestamp | None = None) -> pd.DataFrame:
    """Create event/censor duration from each point-in-time snapshot."""
    by_customer: dict[str, list[pd.Timestamp]] = {}
    for occasion in occasions:
        by_customer.setdefault(str(occasion["customer_id"]), []).append(pd.Timestamp(occasion["transaction_date"]).normalize())
    for dates in by_customer.values(): dates.sort()
    out = frame.copy().reset_index(drop=True)
    decision = pd.to_datetime(out[DECISION])
    durations = np.zeros(len(out), dtype=float)
    events = np.zeros(len(out), dtype=bool)
    censor_end = pd.Timestamp(censor_at) if censor_at is not None else pd.Timestamp(observation_end)
    for i, row in enumerate(out.itertuples(index=False)):
        start = pd.Timestamp(getattr(row, DECISION))
        boundary = min(censor_end, pd.Timestamp(observation_end))
        if boundary <= start:
            continue
        dates = by_customer.get(str(getattr(row, CUSTOMER)), [])
        candidate = next((d for d in dates if d >= start and d <= boundary), None)
        if candidate is not None and (censor_at is None or candidate < pd.Timestamp(censor_at)):
            durations[i] = max(1e-6, (candidate-start).total_seconds()/86400)
            events[i] = True
        else:
            durations[i] = max(1e-6, (boundary-start).total_seconds()/86400)
    out["duration_days"] = durations
    out["event_observed"] = events
    out["survival_censor_date"] = censor_end
    return out


def _cox_objective(beta: np.ndarray, x: np.ndarray, time_days: np.ndarray,
                   event: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    eta = np.clip(x @ beta, -30, 30)
    risk = np.exp(eta)
    order = np.argsort(time_days, kind="mergesort")
    t_sorted = time_days[order]
    r_sorted = risk[order]
    xr_sorted = x[order] * r_sorted[:, None]
    suffix_r = np.cumsum(r_sorted[::-1])[::-1]
    suffix_x = np.cumsum(xr_sorted[::-1], axis=0)[::-1]
    event_times, event_counts = np.unique(time_days[event], return_counts=True)
    loglik = 0.0
    grad = np.zeros(x.shape[1], dtype=float)
    for t, d in zip(event_times, event_counts):
        rows = event & (time_days == t)
        idx = int(np.searchsorted(t_sorted, t, side="left"))
        denom = suffix_r[idx]
        loglik += float(eta[rows].sum() - d*np.log(denom))
        grad += x[rows].sum(axis=0) - d*suffix_x[idx]/denom
    n_events = max(1, int(event.sum()))
    loss = -loglik/n_events + 0.5*alpha*float(beta@beta)
    gradient = -grad/n_events + alpha*beta
    return float(loss), gradient


def _km_censoring(time_days: np.ndarray, event: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    censor = ~event
    points = np.unique(time_days[censor])
    survival = 1.0
    out = []
    n = len(time_days)
    for t in points:
        at_risk = int(np.sum(time_days >= t))
        d = int(np.sum(censor & (time_days == t)))
        if at_risk:
            survival *= (1-d/at_risk)
        out.append(survival)
    return points.astype(float), np.asarray(out, dtype=float)


def _g_censor(points: np.ndarray, surv: np.ndarray, t: float, *, left: bool = False) -> float:
    side = "left" if left else "right"
    idx = np.searchsorted(points, t, side=side)-1
    return float(surv[idx]) if idx >= 0 else 1.0


def ipcw_brier_at_horizon(y_time: np.ndarray, y_event: np.ndarray, survival_prediction: np.ndarray,
                          censor_times: np.ndarray, censor_survival: np.ndarray, horizon: float) -> dict[str, Any]:
    known = (y_event & (y_time < horizon)) | (y_time >= horizon)
    truth = np.where(y_event & (y_time < horizon), 0.0, 1.0)
    weights = np.zeros(len(y_time), dtype=float)
    for i in np.flatnonzero(known):
        t = y_time[i] if truth[i] == 0 else horizon
        g = _g_censor(censor_times, censor_survival, float(t), left=truth[i] == 0)
        weights[i] = 1/max(g, 1e-6)
    pred = np.clip(np.asarray(survival_prediction, dtype=float), 0, 1)
    loss = (truth-pred)**2
    return {"horizon_days": horizon, "ipcw_brier": float(np.sum(weights*loss)/len(y_time)),
            "known_n": int(known.sum()), "censored_before_horizon_n": int((~known).sum()),
            "censoring_survival_at_horizon": _g_censor(censor_times, censor_survival, horizon)}


def harrell_c_index(time_days: np.ndarray, event: np.ndarray, risk_score: np.ndarray) -> dict[str, Any]:
    """O(n log n) Harrell concordance; larger risk means earlier purchase."""
    t = np.asarray(time_days, float); e = np.asarray(event, bool); r = np.asarray(risk_score, float)
    finite = np.isfinite(t) & np.isfinite(r)
    t, e, r = t[finite], e[finite], r[finite]
    unique_r = np.unique(r)
    ranks = np.searchsorted(unique_r, r)+1
    tree = np.zeros(len(unique_r)+2, dtype=np.int64)
    def add(i: int) -> None:
        while i < len(tree): tree[i] += 1; i += i & -i
    def prefix(i: int) -> int:
        s=0
        while i>0: s += tree[i]; i -= i & -i
        return s
    order = np.argsort(-t, kind="mergesort")
    concordant = comparable = tied_risk = 0
    start = 0
    while start < len(order):
        end = start+1
        while end < len(order) and t[order[end]] == t[order[start]]: end += 1
        group = order[start:end]
        # A purchase event is comparable with all rows observed strictly later.
        for i in group[e[group]]:
            n_lower = prefix(int(ranks[i])-1)
            n_equal = prefix(int(ranks[i]))-n_lower
            n_total = prefix(len(unique_r))
            concordant += n_lower
            tied_risk += n_equal
            comparable += n_total
        for i in group: add(int(ranks[i]))
        start = end
    denom = comparable
    return {"harrell_c": float((concordant+0.5*tied_risk)/denom) if denom else None,
            "comparable_pairs": int(denom), "concordant_pairs": int(concordant), "tied_risk_pairs": int(tied_risk)}


def truncate_survival_followup(time_days: np.ndarray, event: np.ndarray,
                               horizon_days: float) -> tuple[np.ndarray, np.ndarray]:
    """Censor follow-up at a fixed horizon while preserving earlier censoring."""
    time_days = np.asarray(time_days, dtype=float)
    event = np.asarray(event, dtype=bool)
    if time_days.shape != event.shape:
        raise ValueError("Survival times and event indicators must have matching shapes.")
    if horizon_days <= 0 or not np.isfinite(horizon_days):
        raise ValueError("Survival evaluation horizon must be finite and positive.")
    if not np.isfinite(time_days).all() or np.any(time_days < 0):
        raise ValueError("Survival times must be finite and non-negative.")
    # The purchase target is half-open [T, T+h): an event exactly at h is
    # outside the horizon and is therefore treated as censored at h.
    truncated_time = np.minimum(time_days, horizon_days)
    truncated_event = event & (time_days < horizon_days)
    return truncated_time, truncated_event


def _survival_window_scope(month: str, horizon_days: int) -> dict[str, str]:
    decision = pd.Timestamp(month + "-01")
    window_end = decision + pd.Timedelta(days=horizon_days)
    holdout_start = pd.Timestamp("2011-07-01")
    scope = ("strict_pre_holdout_outcome_window" if window_end <= holdout_start
             else "exploratory_outcomes_extend_beyond_2011-07-01")
    return {"evaluation_window_end_exclusive": str(window_end), "outcome_scope": scope}


def load_purchase_occasion_api():
    """Load the canonical recovery module from this repository's documented layout."""
    from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (
        load_validated_purchase_input, build_purchase_occasions,
    )
    return load_validated_purchase_input, build_purchase_occasions


def fit_cox(train: pd.DataFrame, eval_frame: pd.DataFrame, *, alpha: float = 0.1) -> dict[str, Any]:
    prep = Pipeline([("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                     ("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    x_train = prep.fit_transform(train.loc[:, list(FEATURES)])
    x_eval = prep.transform(eval_frame.loc[:, list(FEATURES)])
    t = train.duration_days.to_numpy(float); e = train.event_observed.to_numpy(bool)
    if e.sum() < 10: raise ValueError("Cox model needs at least 10 observed events in training.")
    result = minimize(_cox_objective, np.zeros(x_train.shape[1]), args=(x_train,t,e,alpha),
                      jac=True, method="L-BFGS-B", options={"maxiter":1000,"ftol":1e-10})
    beta = np.asarray(result.x)
    if not np.isfinite(beta).all(): raise ValueError("Cox model produced non-finite coefficients.")
    eta_train = np.clip(x_train@beta,-30,30); eta_eval=np.clip(x_eval@beta,-30,30)
    risk = np.exp(eta_train)
    event_times=np.unique(t[e])
    base_h=[]; cumulative=0.0
    for u in event_times:
        at_risk=float(risk[t>=u].sum()); d=int(np.sum(e & (t==u)))
        if at_risk: cumulative += d/at_risk
        base_h.append(cumulative)
    return {"preprocessor":prep,"beta":beta,"baseline_times":event_times,
            "baseline_hazard":np.asarray(base_h),"eval_linear_predictor":eta_eval,
            "train_x":x_train,"train_time":t,"train_event":e,"train_eta":eta_train,
            "optimizer_success":bool(result.success),"optimizer_message":str(result.message),
            "training_events":int(e.sum()),"alpha":alpha}


def cox_survival_at(model: dict[str, Any], horizon: float) -> np.ndarray:
    times, hazard = model["baseline_times"], model["baseline_hazard"]
    idx=np.searchsorted(times,horizon,side="right")-1
    h0=float(hazard[idx]) if idx>=0 else 0.0
    return np.exp(-h0*np.exp(model["eval_linear_predictor"]))


def kaplan_meier_survival(time_days: np.ndarray, event: np.ndarray, horizon: float) -> float:
    points=np.unique(time_days[event]); surv=1.0
    for t in points:
        if t>horizon: break
        n=np.sum(time_days>=t); d=np.sum(event & (time_days==t))
        if n: surv *= 1-d/n
    return float(surv)


def cox_ph_diagnostic(model: dict[str, Any], *, max_events: int = 500, seed: int = SEED) -> dict[str, Any]:
    """Descriptive Schoenfeld-residual trend check, not a formal clustered test."""
    x=model["train_x"]; t=model["train_time"]; e=model["train_event"]; eta=model["train_eta"]
    ix=np.flatnonzero(e)
    if len(ix)>max_events:
        rng=np.random.Generator(np.random.PCG64(seed))
        ix=np.sort(rng.choice(ix,size=max_events,replace=False))
    residuals=[]; event_times=[]
    risk=np.exp(np.clip(eta,-30,30))
    for i in ix:
        at=t>=t[i]
        mean=np.average(x[at],axis=0,weights=risk[at])
        residuals.append(x[i]-mean);event_times.append(t[i])
    if len(residuals)<20:
        return {"status":"insufficient_events","sampled_events":len(residuals)}
    from scipy.stats import spearmanr
    rho=[]
    residuals=np.asarray(residuals)
    for j in range(residuals.shape[1]):
        value=spearmanr(np.log(np.asarray(event_times)),residuals[:,j]).statistic
        if np.isfinite(value):rho.append(float(value))
    return {"status":"descriptive_only","sampled_events":len(residuals),
            "max_abs_schoenfeld_time_correlation":float(max(map(abs,rho))) if rho else None,
            "interpretation":"Sampled residual-time association; repeated customer rows mean this is not a formal independent-observation test."}


def _value_segment_labels(train: pd.DataFrame, scored: pd.DataFrame) -> tuple[np.ndarray, list[float]]:
    feature="qualifying_gross_merchandise_365d"
    q=np.quantile(train[feature].to_numpy(float),[1/3,2/3])
    labels=np.where(scored[feature].to_numpy(float)<=q[0],"low",
                    np.where(scored[feature].to_numpy(float)<=q[1],"middle","high"))
    return labels,[float(q[0]),float(q[1])]


def _fit_amount_models(train: pd.DataFrame, valid: pd.DataFrame, horizon: int,
                       fit_records: list[dict[str, Any]], fold_name: str) -> dict[str, np.ndarray]:
    target=f"future_gross_{horizon}d"
    y=train[target].to_numpy(float)
    result={"Mean baseline":np.full(len(valid),float(y.mean())),
            "Historical rate":np.maximum(0,valid["qualifying_gross_merchandise_365d"].to_numpy(float))*horizon/365.0}
    for name in ("Tweedie","Random Forest","HistGradientBoosting"):
        model=make_regressor(name);t0=time.perf_counter()
        model.fit(train.loc[:,list(FEATURES)],y)
        result[name]=np.maximum(0.0,model.predict(valid.loc[:,list(FEATURES)]))
        fit_records.append({"task":"future_value","horizon_days":horizon,"fold":fold_name,"model":name,
                            "fit_seconds":time.perf_counter()-t0,"n_train":len(train)})
    t0=time.perf_counter()
    result["Two-part"],calls=_fit_two_part(train,valid,target)
    fit_records.append({"task":"future_value","horizon_days":horizon,"fold":fold_name,"model":"Two-part",
                        "fit_seconds":time.perf_counter()-t0,"n_train":len(train),"positive_train_n":int((y>0).sum()),
                        "estimator_fit_calls":calls})
    return result


def _fit_count_models(train: pd.DataFrame, valid: pd.DataFrame, horizon: int,
                      fit_records: list[dict[str, Any]], fold_name: str) -> dict[str,np.ndarray]:
    target=f"future_occasion_count_{horizon}d"
    y=train[target].to_numpy(float)
    predictions={"Historical frequency":np.maximum(0,valid["qualifying_purchase_occasions_365d"].to_numpy(float))*horizon/365.0}
    model=make_regressor("Count Poisson GLM");t0=time.perf_counter()
    model.fit(train.loc[:,list(FEATURES)],y)
    predictions["Poisson GLM"]=np.maximum(0,model.predict(valid.loc[:,list(FEATURES)]))
    fit_records.append({"task":"purchase_count","horizon_days":horizon,"fold":fold_name,"model":"Poisson GLM",
                        "fit_seconds":time.perf_counter()-t0,"n_train":len(train)})
    return predictions


def _count_metrics(frame: pd.DataFrame, pred: np.ndarray, target: str) -> dict[str, Any]:
    y=frame[target].to_numpy(float);p=np.maximum(0,np.asarray(pred,float))
    return {"n":len(y),"mean_count":float(y.mean()),"predicted_mean":float(p.mean()),
            "zero_share":float(np.mean(y==0)),"mae":float(mean_absolute_error(y,p)),
            "rmse":float(np.sqrt(mean_squared_error(y,p))),
            "poisson_deviance":float(mean_poisson_deviance(y,np.maximum(p,1e-10)))}


def _survival_experiment(cohort: pd.DataFrame, occasions: list[dict[str,Any]],
                         fit_records: list[dict[str,Any]]) -> tuple[dict[str,Any],pd.DataFrame]:
    eval_all=build_survival_outcomes(cohort,occasions,observation_end=DATA_END)
    summaries={};pred_parts=[]
    for month in DEV_MONTH_CANDIDATES:
        validation=eval_all.loc[eval_all[MONTH].astype(str).eq(month)].copy().reset_index(drop=True)
        if validation.empty:continue
        boundary=pd.to_datetime(validation[DECISION]).min()
        training_source=cohort.loc[pd.to_datetime(cohort[DECISION]).lt(boundary)].copy()
        training=build_survival_outcomes(training_source,occasions,observation_end=DATA_END,censor_at=boundary)
        if len(training)<1000 or training.event_observed.sum()<10:continue
        model=fit_cox(training,validation,alpha=0.1)
        fit_records.append({"task":"time_to_purchase","fold":month,"model":"Cox PH ridge","fit_seconds":None,
                            "n_train":len(training),"observed_training_events":model["training_events"],
                            "optimizer_success":model["optimizer_success"],"optimizer_message":model["optimizer_message"]})
        fit_records[-1]["ph_diagnostic"]=cox_ph_diagnostic(model)
        surv_predictions={}
        for h in (30,60,90):
            km=kaplan_meier_survival(training.duration_days.to_numpy(float),training.event_observed.to_numpy(bool),h)
            surv_predictions[f"Kaplan-Meier_{h}d"]=np.full(len(validation),km)
            surv_predictions[f"Cox_PH_{h}d"]=cox_survival_at(model,h)
        pred=validation[[CUSTOMER,MONTH,DECISION,"duration_days","event_observed"]].copy()
        for name,values in surv_predictions.items():pred[name]=values
        pred_parts.append(pred)
        per_month={"n_train":len(training),"train_events":int(training.event_observed.sum()),
                   "maximum_training_followup_days":float(training.duration_days.max()),
                   "n_evaluation":len(validation),"evaluation_events":int(validation.event_observed.sum()),
                   "evaluation_censored":int((~validation.event_observed).sum()),"metrics":{}}
        censor_points,censor_survival=_km_censoring(validation.duration_days.to_numpy(float),validation.event_observed.to_numpy(bool))
        # Evaluation has administrative follow-up to December; each March-June row exceeds 90d.
        for h in (30,60,90):
            at_h={}
            if h>float(training.duration_days.max()):
                per_month["metrics"][str(h)]={
                    "status":"not_supported_by_training_followup",
                    "horizon_days":h,
                    "maximum_training_followup_days":float(training.duration_days.max()),
                    "note":"No model extrapolation reported beyond the training follow-up support."}
                continue
            for name,values in surv_predictions.items():
                if not name.endswith(f"_{h}d"):continue
                # Primary concordance follows only event/censoring information
                # available through this evaluation horizon.
                truncated_time, truncated_event = truncate_survival_followup(
                    validation.duration_days.to_numpy(float),
                    validation.event_observed.to_numpy(bool), h)
                event_risk=1-values
                cindex=harrell_c_index(truncated_time,truncated_event,event_risk)
                full_cindex=harrell_c_index(validation.duration_days.to_numpy(float),
                                             validation.event_observed.to_numpy(bool),event_risk)
                brier=ipcw_brier_at_horizon(validation.duration_days.to_numpy(float),validation.event_observed.to_numpy(bool),
                                            values,censor_points,censor_survival,h)
                at_h[name]={"harrell_c":cindex["harrell_c"],"harrell_c_followup_days":h,
                            "comparable_pairs":cindex["comparable_pairs"],
                            "harrell_c_full_followup_descriptive":full_cindex["harrell_c"],
                            **_survival_window_scope(month,h),
                            **brier,"predicted_event_probability_mean":float(np.mean(1-values)),
                            "observed_event_rate_by_horizon":float(np.mean(validation.event_observed.to_numpy(bool)&
                                                                                 (validation.duration_days.to_numpy(float)<h)))}
            per_month["metrics"][str(h)]=at_h
        summaries[month]=per_month
    predictions=pd.concat(pred_parts,ignore_index=True) if pred_parts else pd.DataFrame()
    primary_c={month:{"Cox_PH":fold["metrics"]["30"]["Cox_PH_30d"]["harrell_c"],
                      "Kaplan_Meier":fold["metrics"]["30"]["Kaplan-Meier_30d"]["harrell_c"]}
               for month,fold in summaries.items() if "30" in fold["metrics"] and
               isinstance(fold["metrics"]["30"],dict) and "Cox_PH_30d" in fold["metrics"]["30"]}
    return {"folds":summaries,
            "primary_30_day_concordance":{"definition":"Harrell C from time/event data truncated at 30 days; event at day 30 is censored per half-open [T,T+30d) target.",
                                          "scope":"All March-June 30-day outcome windows end no later than 1 July 2011.",
                                          "folds":primary_c},
            "outcome_window_scope_note":"Pre-holdout names snapshot decision months only. Metrics for windows ending after 2011-07-01 are exploratory; per-horizon exclusive endpoints and scope are recorded.",
            "censoring_definition":"time from snapshot to next qualifying occasion; customers without event are right-censored at observation end or the training decision cutoff",
            "features":"same 11 M2 features, log1p, training-fold median imputation and standardization",
            "cox_regularization_alpha":0.1,
            "ipcw_note":"Evaluation censoring survival is estimated within each evaluation fold; no March-June administrative censor occurs before 90 days, so horizon IPCW weights are one for the estimable horizons.",
            "concordance_note":"Harrell C is calculated after truncating each evaluation row at the specified horizon; events at the half-open horizon endpoint are censored. Full-follow-up C is retained as a descriptive field and can include later outcomes."},predictions


def run_experiment(snapshots: pd.DataFrame, occasions: list[dict[str,Any]], output_dir: Path,
                   *, bootstrap_reps: int = 500) -> dict[str,Any]:
    started=time.perf_counter()
    targets=build_future_targets(snapshots,occasions)
    feasibility=horizon_feasibility(snapshots)
    fit_records=[];fold_predictions={};fold_results={};fit_count=0
    for horizon in (PRIMARY_HORIZON,SECONDARY_HORIZON):
        folds=make_value_folds(targets,horizon)
        expected=4 if horizon==30 else 3
        if len(folds)!=expected:raise ValueError(f"Expected {expected} feasible {horizon}-day folds, got {len(folds)}")
        target=f"future_gross_{horizon}d";count_target=f"future_occasion_count_{horizon}d"
        amount_rows=[];count_rows=[];per_fold=[]
        for fold in folds:
            tr,va,month=fold["train"],fold["validation"],fold["month"]
            predictions=_fit_amount_models(tr,va,horizon,fit_records,month)
            count_predictions=_fit_count_models(tr,va,horizon,fit_records,month)
            labels,thresholds=_value_segment_labels(tr,va)
            for model_name,pred in predictions.items():
                row=va[[CUSTOMER,MONTH,DECISION,target]].copy();row["model"]=model_name;row["prediction"]=pred
                row["historical_value_segment"]=labels;row["segment_cutoffs_from_training"]=json.dumps(thresholds)
                amount_rows.append(row)
            for model_name,pred in count_predictions.items():
                row=va[[CUSTOMER,MONTH,DECISION,count_target]].copy();row["model"]=model_name;row["prediction"]=pred
                count_rows.append(row)
            per_fold.append({"month":month,"n_train":len(tr),"training_customers":int(tr[CUSTOMER].nunique()),
                             "n_evaluation":len(va),"evaluation_customers":int(va[CUSTOMER].nunique()),
                             "train_positive_spend":int((tr[target]>0).sum()),"evaluation_positive_spend":int((va[target]>0).sum()),
                             "latest_train_label_end":str(pd.to_datetime(tr[f"value_end_{horizon}d"]).max()),
                             "boundary":str(fold["boundary"]),"historical_value_tercile_cutoffs":thresholds})
        amount_oof=pd.concat(amount_rows,ignore_index=True);count_oof=pd.concat(count_rows,ignore_index=True)
        amount_summary={};monthly_amount={}
        for model_name in AMOUNT_MODELS:
            part=amount_oof.loc[amount_oof.model.eq(model_name)].copy().reset_index(drop=True)
            pred=part.prediction.to_numpy(float)
            amount_summary[model_name]=monthly_value_metrics(part,pred,target)
            monthly_amount[model_name]={}
            for seg,g in part.groupby("historical_value_segment",sort=True):
                monthly_amount[model_name][str(seg)]={"n":len(g),"mae":float(mean_absolute_error(g[target],g.prediction)),
                    "mean_actual":float(g[target].mean()),"mean_predicted":float(g.prediction.mean())}
        boot_frame=amount_oof.loc[amount_oof.model.eq("Historical rate")].copy().reset_index(drop=True)
        comparison_predictions={"Historical rate":boot_frame.prediction.to_numpy(float)}
        for model_name in AMOUNT_MODELS:
            if model_name=="Historical rate":continue
            row=amount_oof.loc[amount_oof.model.eq(model_name)].copy()
            row=row.set_index([MONTH,CUSTOMER]).loc[boot_frame.set_index([MONTH,CUSTOMER]).index]
            comparison_predictions[model_name]=row.prediction.to_numpy(float)
        uncertainty=paired_cluster_amount_bootstrap(boot_frame,comparison_predictions,"Historical rate",target,
                                                    reps=bootstrap_reps,seed=SEED+horizon)
        count_summary={}
        for model_name in ("Historical frequency","Poisson GLM"):
            part=count_oof.loc[count_oof.model.eq(model_name)].copy()
            count_summary[model_name]={"overall":_count_metrics(part,part.prediction.to_numpy(float),count_target),"monthly":{}}
            for month,g in part.groupby(MONTH,sort=True):count_summary[model_name]["monthly"][str(month)]=_count_metrics(g,g.prediction.to_numpy(float),count_target)
        target_frame=amount_oof.loc[amount_oof.model.eq("Mean baseline")].copy().reset_index(drop=True)
        zero_spend=np.zeros(len(target_frame),dtype=float)
        tweedie_deviance={}
        for model_name in ("Historical rate","HistGradientBoosting"):
            part=amount_oof.loc[amount_oof.model.eq(model_name)].copy()
            tweedie_deviance[model_name]=float(mean_tweedie_deviance(
                part[target].to_numpy(float),part.prediction.to_numpy(float),power=1.5))
        count_target_frame=count_oof.loc[count_oof.model.eq("Historical frequency")].copy()
        zero_count_mae=float(mean_absolute_error(count_target_frame[count_target].to_numpy(float),
                                                np.zeros(len(count_target_frame))))
        fold_results[str(horizon)]={"folds":per_fold,"monetary_models":amount_summary,
                                    "historical_value_segments":monthly_amount,"paired_customer_bootstrap_mae":uncertainty,
                                    "additional_diagnostics":{"predict_zero_spend":amount_metrics(target_frame,zero_spend,target),
                                                               "tweedie_deviance_power_1_5":tweedie_deviance,
                                                               "predict_zero_count_mae":zero_count_mae},
                                    "purchase_count_models":count_summary,
                                    "target_distribution":{"positive_share":float(np.mean(amount_oof.loc[amount_oof.model.eq("Mean baseline"),target]>0)),
                                                           "mean":float(amount_oof.loc[amount_oof.model.eq("Mean baseline"),target].mean()),
                                                           "p95":float(amount_oof.loc[amount_oof.model.eq("Mean baseline"),target].quantile(.95)),
                                                           "p99":float(amount_oof.loc[amount_oof.model.eq("Mean baseline"),target].quantile(.99)),
                                                           "maximum":float(amount_oof.loc[amount_oof.model.eq("Mean baseline"),target].max())}}
        fold_predictions[str(horizon)]={"amount":amount_oof,"count":count_oof}

    # Exploratory replay: previously examined 2011-07 onward; no selection uses it.
    exploratory={};exploratory_frames={}
    for horizon in (PRIMARY_HORIZON,SECONDARY_HORIZON):
        cutoff=pd.Timestamp("2011-07-01")
        target=f"future_gross_{horizon}d";end_col=f"value_end_{horizon}d";mature=f"value_mature_{horizon}d"
        full_train=targets.loc[pd.to_datetime(targets[DECISION]).lt(cutoff)
                               & pd.to_datetime(targets[end_col]).le(cutoff)&targets[mature]].copy().reset_index(drop=True)
        test_months=tuple(f"2011-{m:02d}" for m in range(7,12 if horizon==30 else 11))
        validation=targets.loc[targets[MONTH].astype(str).isin(test_months)&targets[mature]].copy().reset_index(drop=True)
        preds=_fit_amount_models(full_train,validation,horizon,fit_records,"exploratory_holdout_fit")
        summary={}
        for name,pred in preds.items():summary[name]=monthly_value_metrics(validation,pred,target)
        exploratory[str(horizon)]={"warning":"Previously examined M2 holdout; descriptive only, not independent confirmation.",
                                   "training_n":len(full_train),"evaluation_n":len(validation),"evaluation_months":list(test_months),
                                   "models":summary}
        frames=[]
        for name,pred in preds.items():
            part=validation[[CUSTOMER,MONTH,DECISION,target]].copy();part["model"]=name;part["prediction"]=pred;frames.append(part)
        exploratory_frames[str(horizon)]=pd.concat(frames,ignore_index=True)

    survival_summary,survival_predictions=_survival_experiment(targets,occasions,fit_records)
    # Record horizon choice before viewing comparative model results.
    result={"experiment":"COMMERCIAL_DS_P3_006","created_utc":datetime.now(timezone.utc).isoformat(),
            "status":"completed; 30-day horizon primary, 60-day secondary, 90-day modelling deferred by predeclared origin rule",
            "horizon_selection_rule":{"rule":f"Primary spend/count horizon must support at least {MIN_DEV_EVAL_ORIGINS} mature, strict, pre-holdout evaluation origins with a nonempty mature training set.",
                                    "decision":"30 days primary; 60 days secondary with three origins; 90 days deferred with only two origins.",
                                    "chosen_before_model_performance_comparison":True,"feasibility":feasibility},
            "target_definition":{"population":"existing M2-004 eligible customer-month snapshots, including zero future-purchase outcomes",
                                 "features":list(FEATURES),"spend":"sum positive canonical qualifying gross merchandise in [T,T+h); GBP nominal gross, not net revenue/profit",
                                 "returns_cancellations":"Excluded from the qualifying occasion contract; negative, cancellation and non-positive quantity/price lines do not reduce spending target.",
                                 "maturity":"horizon endpoint at or before corrected source end; non-mature outcomes remain null and are not negatives.",
                                 "outliers":"No trimming or winsorising; heavy right tail is retained and p95/p99/max reported.",
                                 "count":"number of distinct canonical customer-invoice qualifying purchase occasions in the same half-open future window."},
            "development":{"monetary_and_count_results":fold_results},
            "survival":{"summary":survival_summary,"model":"penalized Cox proportional hazards with Breslow baseline; Kaplan-Meier reference",
                        "time_origin":"snapshot decision time","event":"next qualifying canonical occasion","censoring":"right censor at source end for evaluation; at fold decision cutoff for model training"},
            "exploratory_holdout":exploratory,
            "purchase_count_assessment":{"methods":"historical 365-day occasion rate and Poisson GLM; count predictions use mature 30-day primary targets in development.",
                                          "bg_nbd":"Not fitted. lifetimes/lifelines are not installed; fixed-window aggregate counts and strong calendar variation make homogeneous dropout-process assumptions uncertain with four OOF origins.",
                                          "recommendation":"Retain descriptive count regression; defer BG/NBD until a longer, explicitly calibrated customer transaction panel is available."},
            "fit_records":fit_records,"fit_count":sum(int(x.get("estimator_fit_calls",1)) for x in fit_records),
            "runtime":{"experiment_seconds":time.perf_counter()-started,"fit_records":len(fit_records),"seed":SEED},
            "provenance":{"dataset_sha256":EXPECTED_DATASET_SHA256,"manifest_sha256":EXPECTED_MANIFEST_SHA256,
                          "feature_columns":list(FEATURES),"data_end":"2011-12-09 12:50:00",
                          "packages":{"numpy":np.__version__,"pandas":pd.__version__}}}
    output_dir.mkdir(parents=True,exist_ok=True);private=output_dir/"private";private.mkdir(parents=True,exist_ok=True)
    result["provenance"]["aggregate_sha256_pending"]=True
    (output_dir/"p3_006_aggregate_results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    pd.concat([fold_predictions[str(h)]["amount"].assign(horizon_days=h) for h in (30,60)],ignore_index=True).to_parquet(private/"p3_006_development_value_predictions.parquet",index=False)
    pd.concat([fold_predictions[str(h)]["count"].assign(horizon_days=h) for h in (30,60)],ignore_index=True).to_parquet(private/"p3_006_development_count_predictions.parquet",index=False)
    survival_predictions.to_parquet(private/"p3_006_survival_predictions.parquet",index=False)
    pd.concat([exploratory_frames[str(h)].assign(horizon_days=h) for h in (30,60)],ignore_index=True).to_parquet(private/"p3_006_exploratory_holdout_predictions.parquet",index=False)
    plot_outputs(fold_predictions,survival_predictions,output_dir)
    from monthly_purchase_baselines import sha256_file as _sha
    manifest={"experiment":"P3-006","aggregate_sha256":_sha(output_dir/"p3_006_aggregate_results.json"),
              "dataset_sha256":EXPECTED_DATASET_SHA256,"feature_order":list(FEATURES),
              "private_files":["private/p3_006_development_value_predictions.parquet","private/p3_006_development_count_predictions.parquet",
                               "private/p3_006_survival_predictions.parquet","private/p3_006_exploratory_holdout_predictions.parquet"]}
    (output_dir/"p3_006_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return result


def plot_outputs(fold_predictions: dict[str,Any], survival_predictions: pd.DataFrame, output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    primary=fold_predictions[str(PRIMARY_HORIZON)]["amount"]
    rf=primary.loc[primary.model.eq("Random Forest")].copy()
    rf["decile"]=pd.qcut(rf.prediction.rank(method="first"),10,labels=False)+1
    grouped=rf.groupby("decile",observed=True).agg(predicted=("prediction","mean"),observed=("future_gross_30d","mean"))
    fig,ax=plt.subplots(figsize=(6,4));ax.plot(grouped.index,grouped.predicted,marker="o",label="Predicted mean")
    ax.plot(grouped.index,grouped.observed,marker="o",label="Observed mean")
    ax.set(xlabel="Random Forest prediction decile",ylabel="30-day gross merchandise (GBP)",title="Future value by predicted decile");ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/"docs/research/figures/p3_006_value_deciles.png",dpi=160);plt.close(fig)
    if len(survival_predictions):
        frame=survival_predictions.loc[survival_predictions[MONTH].astype(str).eq("2011-06")].copy()
        fig,ax=plt.subplots(figsize=(6,4))
        for col,label in (("Kaplan-Meier_30d","Kaplan–Meier"),("Cox_PH_30d","Cox PH")):
            event_risk=1-frame[col].to_numpy(float)
            edges=np.linspace(0,1,6); bins=np.digitize(event_risk,edges[1:-1])
            xs=[];ys=[]
            observed=(frame.event_observed.to_numpy(bool)&(frame.duration_days.to_numpy(float)<30)).astype(float)
            for b in range(5):
                ix=bins==b
                if ix.any():xs.append(float(event_risk[ix].mean()));ys.append(float(observed[ix].mean()))
            if xs:ax.plot(xs,ys,marker="o",label=label)
        ax.plot([0,1],[0,1],"--",color="0.6");ax.set(xlim=(0,1),ylim=(0,1),xlabel="Predicted 30-day purchase probability",ylabel="Observed rate",title="June 30-day timing calibration");ax.legend();ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(ROOT/"docs/research/figures/p3_006_survival_calibration.png",dpi=160);plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser()
    data_root=ROOT.parent/"source_data/uci_online_retail_ii"
    parser.add_argument("--dataset",type=Path,default=data_root/"monthly_customer_snapshots_m2_004.parquet")
    parser.add_argument("--manifest",type=Path,default=data_root/"monthly_customer_snapshots_m2_004.parquet.manifest.json")
    parser.add_argument("--output-dir",type=Path,default=data_root/"p3_006_outputs")
    parser.add_argument("--bootstrap-reps",type=int,default=500)
    args=parser.parse_args()
    if ROOT in args.output_dir.resolve().parents or args.output_dir.resolve()==ROOT:raise ValueError("P3 outputs must remain outside Git.")
    _,cohort=verify_frozen_inputs(args.dataset,args.manifest)
    load_validated_purchase_input,build_purchase_occasions=load_purchase_occasion_api()
    validated=load_validated_purchase_input();occasions,summary=build_purchase_occasions(validated)
    result=run_experiment(cohort,occasions,args.output_dir,bootstrap_reps=args.bootstrap_reps)
    result["provenance"]["qualifying_occasion_summary"]={k:v for k,v in summary.items() if k!="excluded_rows_by_reason"}
    (args.output_dir/"p3_006_aggregate_results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    manifest_path=args.output_dir/"p3_006_manifest.json"
    manifest=json.loads(manifest_path.read_text())
    manifest["aggregate_sha256"]=sha256_file(args.output_dir/"p3_006_aggregate_results.json")
    manifest["qualifying_occasion_count"]=int(summary["occasion_count"])
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"fit_count":result["fit_count"],"runtime":result["runtime"],
                      "horizon_feasibility":result["horizon_selection_rule"]["feasibility"]},indent=2))


if __name__=="__main__":main()

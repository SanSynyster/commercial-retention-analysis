"""P3-007 point-in-time customer segmentation experiment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import resource
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score,
                             davies_bouldin_score, normalized_mutual_info_score,
                             silhouette_score)
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from monthly_customer_snapshots import FEATURE_COLUMNS  # noqa: E402
from monthly_purchase_baselines import (  # noqa: E402
    EXPECTED_DATASET_SHA256, EXPECTED_MANIFEST_SHA256,
    CUSTOMER_COLUMN, MONTH_COLUMN, verify_frozen_inputs,
)

CUSTOMER = CUSTOMER_COLUMN
MONTH = MONTH_COLUMN
DECISION = "decision_time"
OUTCOME = "outcome_label"
REFERENCE_MONTH = "2011-03"
DEV_EVAL_MONTHS = ("2011-04", "2011-05", "2011-06")
EXPLORATORY_MONTHS = ("2011-07", "2011-08", "2011-09", "2011-10", "2011-11")
K_VALUES = tuple(range(3, 9))
SEEDS = (20261113, 20261114, 20261115)
BOOTSTRAP_REPS = 12
BOOTSTRAP_SEED = 20261127
SILHOUETTE_SAMPLE = 2000

# Compact point-in-time feature set: RFM plus average basket value and recent
# 90-day activity share. Redundant 365-day distinct dates, basket quantity,
# product counts, and 90-day spend are omitted based on the March correlation audit.
BASE_FEATURES = (
    "days_since_last_qualifying_purchase",
    "qualifying_purchase_occasions_365d",
    "qualifying_gross_merchandise_365d",
    "average_qualifying_basket_value_365d",
)
DERIVED_FEATURE = "purchase_occasion_share_90d"
CLUSTER_FEATURES = BASE_FEATURES + (DERIVED_FEATURE,)
LOG_FEATURES = BASE_FEATURES
RFM_COLUMNS = {
    "recency": "days_since_last_qualifying_purchase",
    "frequency": "qualifying_purchase_occasions_365d",
    "monetary": "qualifying_gross_merchandise_365d",
}


def make_segmentation_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive only historical features available at each stored snapshot."""
    missing = set(BASE_FEATURES + ("qualifying_purchase_occasions_90d",)) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing point-in-time segmentation columns: {sorted(missing)}")
    features = frame.loc[:, list(BASE_FEATURES)].astype(float).copy()
    denominator = frame["qualifying_purchase_occasions_365d"].astype(float).to_numpy()
    numerator = frame["qualifying_purchase_occasions_90d"].astype(float).to_numpy()
    if not np.isfinite(denominator).all() or not np.isfinite(numerator).all() or (denominator <= 0).any():
        raise ValueError("Eligible snapshots need finite positive 365-day frequency and finite 90-day frequency.")
    features[DERIVED_FEATURE] = numerator / denominator
    if not np.isfinite(features.to_numpy()).all() or (features.to_numpy() < 0).any():
        raise ValueError("Segmentation features must be finite and non-negative.")
    for column in LOG_FEATURES:
        features[column] = np.log1p(features[column])
    return features.loc[:, list(CLUSTER_FEATURES)]


def fit_reference_transform(reference_raw: pd.DataFrame) -> tuple[SimpleImputer, StandardScaler, np.ndarray, dict[str, Any]]:
    """Fit median imputation and scaling using reference rows only."""
    reference_features = make_segmentation_features(reference_raw)
    imputer = SimpleImputer(strategy="median")
    imputed = imputer.fit_transform(reference_features)
    scaler = StandardScaler()
    transformed = scaler.fit_transform(imputed)
    metadata = {
        "feature_order": list(CLUSTER_FEATURES),
        "log1p_features": list(LOG_FEATURES),
        "imputation_medians_reference_only": [float(x) for x in imputer.statistics_],
        "transformed_means_reference_only": [float(x) for x in scaler.mean_],
        "transformed_scales_reference_only": [float(x) for x in scaler.scale_],
        "reference_n": int(len(reference_raw)),
    }
    return imputer, scaler, transformed, metadata


def transform_with_reference(frame: pd.DataFrame, imputer: SimpleImputer,
                              scaler: StandardScaler) -> np.ndarray:
    features = make_segmentation_features(frame)
    return scaler.transform(imputer.transform(features))


def _quantile_scores(values: np.ndarray, thresholds: np.ndarray, *, reverse: bool = False) -> np.ndarray:
    scores = np.searchsorted(thresholds, np.asarray(values, dtype=float), side="right") + 1
    if reverse:
        scores = 6 - scores
    return scores.astype(int)


def fit_rfm_rules(reference: pd.DataFrame) -> dict[str, Any]:
    """Fit reference quintile cutpoints for ordinal recency/frequency/monetary scores."""
    specs = {
        "recency": (RFM_COLUMNS["recency"], True),
        "frequency": (RFM_COLUMNS["frequency"], False),
        "monetary": (RFM_COLUMNS["monetary"], False),
    }
    rules = {}
    for name, (column, reverse) in specs.items():
        values = np.log1p(reference[column].astype(float).to_numpy())
        thresholds = np.quantile(values, [0.2, 0.4, 0.6, 0.8])
        rules[name] = {"column": column, "thresholds_log1p": [float(x) for x in thresholds],
                       "reverse": reverse}
    return {"thresholds": rules, "fit_month": REFERENCE_MONTH,
            "score_definition": "nominal five ordinal scores from reference quintile cutpoints; R reversed so lower recency is higher score; ties use searchsorted(side=right). Discrete 365-day frequency realizes four non-empty score bands in March; frequency=1 maps to F=2 because its value equals the first quantile cutpoint."}


def assign_rfm(frame: pd.DataFrame, rules: dict[str, Any]) -> pd.DataFrame:
    output = pd.DataFrame(index=frame.index)
    for name, rule in rules["thresholds"].items():
        values = np.log1p(frame[rule["column"]].astype(float).to_numpy())
        output[name] = _quantile_scores(values, np.asarray(rule["thresholds_log1p"]), reverse=rule["reverse"])
    r, f, m = (output[c].to_numpy() for c in ("recency", "frequency", "monetary"))
    conditions = [
        (r >= 4) & (f >= 4) & (m >= 4),
        (r <= 2) & (f >= 3),
        (r <= 2) & (f <= 2),
        (r >= 4) & (f >= 3),
        (r >= 4) & (f <= 2),
        (m >= 4),
    ]
    names = ["Champions", "At risk", "Hibernating", "Loyal", "Potential", "Big spenders"]
    output["rfm_segment"] = np.select(conditions, names, default="Regular")
    output["rfm_code"] = output[["recency", "frequency", "monetary"]].astype(str).agg("".join, axis=1)
    return output


def fit_cluster(name: str, k: int, seed: int):
    if name == "KMeans":
        return KMeans(n_clusters=k, n_init=20, random_state=seed, algorithm="lloyd")
    if name == "GaussianMixture":
        return GaussianMixture(n_components=k, covariance_type="full", reg_covar=1e-5,
                               n_init=5, max_iter=300, random_state=seed)
    raise ValueError(name)


def predict_cluster(model: Any, name: str, x: np.ndarray) -> np.ndarray:
    labels = model.predict(x) if name in ("KMeans", "GaussianMixture") else model.fit_predict(x)
    return np.asarray(labels, dtype=int)


def cluster_quality(x: np.ndarray, labels: np.ndarray, *, sample_size: int = SILHOUETTE_SAMPLE,
                    seed: int = 20261113) -> dict[str, Any]:
    labels = np.asarray(labels)
    counts = np.bincount(labels, minlength=int(labels.max()) + 1)
    if np.unique(labels).size < 2 or np.unique(labels).size >= len(labels):
        silhouette = None
    else:
        silhouette = float(silhouette_score(x, labels, sample_size=min(sample_size, len(x)), random_state=seed))
    return {
        "n_clusters": int(np.unique(labels).size),
        "silhouette_sampled": silhouette,
        "davies_bouldin": float(davies_bouldin_score(x, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(x, labels)),
        "cluster_sizes": [int(np.sum(labels == label)) for label in sorted(np.unique(labels))],
        "cluster_shares": [float(np.mean(labels == label)) for label in sorted(np.unique(labels))],
        "minimum_cluster_share": float(min(np.mean(labels == label) for label in np.unique(labels))),
    }


def evaluate_candidates(x: np.ndarray, *, bootstrap_reps: int = BOOTSTRAP_REPS) -> tuple[dict[str, Any], dict[tuple[str, int], Any]]:
    results: dict[str, Any] = {}
    primary_models = {}
    for name in ("KMeans", "GaussianMixture"):
        results[name] = {}
        for k in K_VALUES:
            seed_models = []
            seed_labels = []
            for seed in SEEDS:
                model = fit_cluster(name, k, seed)
                labels = model.fit_predict(x)
                seed_models.append(model)
                seed_labels.append(np.asarray(labels, dtype=int))
            primary = seed_models[0]
            primary_labels = seed_labels[0]
            seed_ari = [float(adjusted_rand_score(primary_labels, labels)) for labels in seed_labels[1:]]
            quality = cluster_quality(x, primary_labels)
            results[name][str(k)] = {**quality,
                "seed_values": list(SEEDS),
                "seed_ari_vs_primary": seed_ari,
                "mean_seed_ari": float(np.mean(seed_ari)),
                "converged": bool(getattr(primary, "n_iter_", 1) < getattr(primary, "max_iter", 2)),
            }
            primary_models[(name, k)] = primary

    # Ward agglomeration is feasible at the 4,260-row reference size, but it has
    # no native out-of-sample prediction rule and is diagnostic only.
    results["Agglomerative"] = {}
    for k in K_VALUES:
        model = AgglomerativeClustering(n_clusters=k, linkage="ward", compute_full_tree=True)
        labels = model.fit_predict(x)
        results["Agglomerative"][str(k)] = cluster_quality(x, labels)

    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    for name in ("KMeans", "GaussianMixture"):
        for k in K_VALUES:
            base_model = primary_models[(name, k)]
            base_labels = base_model.predict(x)
            ari = []
            for _ in range(bootstrap_reps):
                sample = rng.integers(0, len(x), size=len(x))
                model = fit_cluster(name, k, int(rng.integers(1, 2**31 - 1)))
                model.fit(x[sample])
                resampled_labels = model.predict(x)
                ari.append(float(adjusted_rand_score(base_labels, resampled_labels)))
            entry = results[name][str(k)]
            entry["customer_bootstrap_ari_mean"] = float(np.mean(ari))
            entry["customer_bootstrap_ari_p10_p90"] = [float(v) for v in np.quantile(ari, [0.1, 0.9])]
            entry["customer_bootstrap_repetitions"] = int(bootstrap_reps)
    return results, primary_models


def choose_model(results: dict[str, Any]) -> dict[str, Any]:
    """Apply the predeclared stability/size rule, without outcome metrics."""
    eligible = []
    for name in ("KMeans", "GaussianMixture"):
        for k in K_VALUES:
            row = results[name][str(k)]
            if (row["minimum_cluster_share"] >= 0.03 and row["mean_seed_ari"] >= 0.90
                    and row["customer_bootstrap_ari_mean"] >= 0.75):
                eligible.append((row["customer_bootstrap_ari_mean"], row["mean_seed_ari"],
                                 -k, 1 if name == "KMeans" else 0, name, k))
    if not eligible:
        return {"selected": None,
                "rule":"Eligible only if every reference cluster is >=3%, mean seed ARI >=0.90, and mean customer-bootstrap ARI >=0.75; otherwise retain transparent RFM as primary segmentation.",
                "eligible_candidates": []}
    eligible.sort(reverse=True)
    best = eligible[0]
    return {"selected": {"algorithm": best[4], "k": best[5]},
            "rule":"Among candidates with every reference cluster >=3%, mean seed ARI >=0.90, and mean customer-bootstrap ARI >=0.75, choose greatest bootstrap ARI; then seed ARI; then smaller k; prefer KMeans on a remaining tie.",
            "eligible_candidates":[{"algorithm":x[4],"k":x[5],"bootstrap_ari":x[0],"seed_ari":x[1]} for x in eligible]}


def _month_summary(frame: pd.DataFrame, labels: np.ndarray, name: str) -> list[dict[str, Any]]:
    out = frame[[CUSTOMER, MONTH]].copy().reset_index(drop=True)
    out["segment"] = np.asarray(labels).astype(int)
    rows = []
    for month, group in out.groupby(MONTH, sort=True):
        counts = group.segment.value_counts().sort_index()
        rows.extend({"month":str(month),"segment":int(seg),"n":int(n),"share":float(n/len(group)),
                     "eligible_customers":int(group[CUSTOMER].nunique())} for seg,n in counts.items())
    return rows


def transition_summary(frame: pd.DataFrame, labels: pd.Series,
                       months: tuple[str, ...], segment_name: str) -> dict[str, Any]:
    data = frame[[CUSTOMER, MONTH]].copy()
    data["segment"] = labels.to_numpy()
    months_out = []
    transition_tables = {}
    for left, right in zip(months, months[1:]):
        a = data.loc[data[MONTH].astype(str).eq(left), [CUSTOMER,"segment"]].rename(columns={"segment":"from"})
        b = data.loc[data[MONTH].astype(str).eq(right), [CUSTOMER,"segment"]].rename(columns={"segment":"to"})
        joined = a.merge(b, on=CUSTOMER, how="inner", validate="one_to_one")
        segment_order = sorted(data.segment.unique(), key=str)
        matrix = pd.crosstab(joined["from"], joined["to"]).reindex(
            index=segment_order, columns=segment_order, fill_value=0)
        ari = float(adjusted_rand_score(joined["from"], joined["to"])) if len(joined) else None
        matches = int(np.sum(joined["from"].to_numpy() == joined["to"].to_numpy()))
        prior_ids=set(a[CUSTOMER]); next_ids=set(b[CUSTOMER])
        months_out.append({"from_month":left,"to_month":right,"matched_customers":int(len(joined)),
                           "entrants":int(len(next_ids-prior_ids)),"leavers":int(len(prior_ids-next_ids)),
                           "same_segment_share":float(matches/len(joined)) if len(joined) else None,
                           "adjusted_rand_index":ari})
        transition_tables[f"{left}_to_{right}"]={"segment_name":segment_name,
            "labels":[int(x) if isinstance(x,(int,np.integer)) else str(x) for x in matrix.index],
            "counts":matrix.astype(int).values.tolist(),
            "row_normalized":matrix.div(matrix.sum(axis=1).replace(0,np.nan),axis=0).fillna(0).values.tolist()}
    return {"adjacent_months":months_out,"transition_matrices":transition_tables}


def select_30_day_monetary_targets(dev: pd.DataFrame, holdout: pd.DataFrame) -> pd.DataFrame:
    """Select only 30-day target rows before merging on customer-month keys."""
    target_col="future_gross_30d"
    required={"horizon_days","model",CUSTOMER,MONTH,target_col}
    for name,frame in (("development",dev),("holdout",holdout)):
        missing=required-set(frame.columns)
        if missing:
            raise ValueError(f"{name} P3-006 target rows lack required columns: {sorted(missing)}")
    source=pd.concat([
        dev.loc[dev.horizon_days.eq(30)&dev.model.eq("HistGradientBoosting"),[CUSTOMER,MONTH,target_col]],
        holdout.loc[holdout.horizon_days.eq(30)&holdout.model.eq("HistGradientBoosting"),[CUSTOMER,MONTH,target_col]],
    ],ignore_index=True)
    if source.duplicated([CUSTOMER,MONTH]).any():
        raise ValueError("Selected 30-day P3-006 targets do not have unique snapshot keys.")
    return source


def outcome_profiles(assignments: pd.DataFrame, snapshots: pd.DataFrame,
                     output_dir: Path) -> dict[str, Any]:
    """Profile mature 30d outcomes after clustering; all row-level joins stay private."""
    private = output_dir / "private"
    dev_path = private / "p3_006_development_value_predictions.parquet"
    holdout_path = private / "p3_006_exploratory_holdout_predictions.parquet"
    if not dev_path.exists() or not holdout_path.exists():
        raise FileNotFoundError("P3-006 private actual-value outputs are required for outcome profiling.")
    dev = pd.read_parquet(dev_path)
    hold = pd.read_parquet(holdout_path)
    count_path = private / "p3_006_development_count_predictions.parquet"
    count_source = pd.read_parquet(count_path) if count_path.exists() else pd.DataFrame()
    target_col = "future_gross_30d"
    source = select_30_day_monetary_targets(dev,hold)
    labels = snapshots[[CUSTOMER,MONTH,OUTCOME,"outcome_window_mature","outcome_coverage_status"]].copy()
    joined=assignments.merge(labels,on=[CUSTOMER,MONTH],validate="one_to_one").merge(
        source,on=[CUSTOMER,MONTH],how="left",validate="one_to_one")
    future_count_col="future_occasion_count_30d"
    if len(count_source):
        count_source=count_source.loc[count_source.horizon_days.eq(30)&count_source.model.eq("Historical frequency"),
                                      [CUSTOMER,MONTH,future_count_col]].drop_duplicates([CUSTOMER,MONTH])
        joined=joined.merge(count_source,on=[CUSTOMER,MONTH],how="left",validate="one_to_one")
    selected_months=set(DEV_EVAL_MONTHS+EXPLORATORY_MONTHS)
    joined=joined.loc[joined[MONTH].astype(str).isin(selected_months)].copy()
    if not joined.outcome_window_mature.fillna(False).all() or not joined.outcome_coverage_status.eq("complete").all():
        raise ValueError("Outcome profiles require mature complete labels only.")
    joined["period"] = np.where(joined[MONTH].astype(str).isin(DEV_EVAL_MONTHS),"development_Apr-Jun","exploratory_Jul-Nov")
    joined["purchase_from_spend"]=(joined[target_col]>0).astype(int)
    if joined[OUTCOME].astype(int).to_numpy().tolist()!=joined["purchase_from_spend"].astype(int).to_numpy().tolist():
        raise ValueError("P3-006 gross target and frozen M2 purchase label disagree on profiled rows.")
    result={}
    for period, data in joined.groupby("period",sort=True):
        result[period]={}
        def _segment_key(value: Any, column: str) -> str:
            return str(int(value)) if column=="ml_segment" else str(value)
        for col in ("ml_segment","rfm_segment"):
            summary=data.groupby(col,observed=True).agg(
                n=(CUSTOMER,"size"),unique_customers=(CUSTOMER,"nunique"),
                purchase_rate=("purchase_from_spend","mean"),
                mean_future_gross_gbp=(target_col,"mean"),median_future_gross_gbp=(target_col,"median"),
                p90_future_gross_gbp=(target_col,lambda x:float(x.quantile(.9)))).reset_index()
            result[period][col]={_segment_key(row[col],col):{"n":int(row.n),"unique_customers":int(row.unique_customers),
                "purchase_rate":float(row.purchase_rate),"mean_future_gross_gbp":float(row.mean_future_gross_gbp),
                "median_future_gross_gbp":float(row.median_future_gross_gbp),"p90_future_gross_gbp":float(row.p90_future_gross_gbp)}
                for _,row in summary.iterrows()}
            if future_count_col in data and data[future_count_col].notna().all():
                count_summary=data.groupby(col,observed=True)[future_count_col].agg(["mean","median"]).to_dict("index")
                for segment,stats in count_summary.items():
                    result[period][col][_segment_key(segment,col)]["mean_future_occasion_count_30d"] = float(stats["mean"])
        cells=data.groupby(["rfm_segment","ml_segment"],observed=True).agg(
            n=(CUSTOMER,"size"),purchase_rate=("purchase_from_spend","mean"),mean_value=(target_col,"mean")).reset_index()
        ranges=[]
        for rfm, group in cells.loc[cells.n>=50].groupby("rfm_segment",sort=True):
            if group.ml_segment.nunique()>=2:
                ranges.append({"rfm_segment":str(rfm),"qualifying_cluster_cells":int(len(group)),
                               "purchase_rate_range":float(group.purchase_rate.max()-group.purchase_rate.min()),
                               "mean_value_range_gbp":float(group.mean_value.max()-group.mean_value.min()),
                               "minimum_cell_n":50})
        eligible_ranges=[x for x in ranges]
        result[period]["within_rfm_cluster_variation"]={
            "rfm_groups_with_at_least_two_cluster_cells_n50":len(eligible_ranges),
            "median_purchase_rate_range":float(np.median([x["purchase_rate_range"] for x in eligible_ranges])) if eligible_ranges else None,
            "median_mean_value_range_gbp":float(np.median([x["mean_value_range_gbp"] for x in eligible_ranges])) if eligible_ranges else None,
            "largest_purchase_rate_spreads":sorted(eligible_ranges,key=lambda x:x["purchase_rate_range"],reverse=True)[:5]}
    return result


def cluster_profiles(frame: pd.DataFrame, labels: np.ndarray, x: np.ndarray) -> dict[str, Any]:
    data=frame.reset_index(drop=True).copy();data["ml_segment"]=np.asarray(labels)
    raw_profile={}
    for cluster, group in data.groupby("ml_segment",sort=True):
        raw_profile[str(int(cluster))]={"n":len(group),"share":len(group)/len(data),
            "feature_medians":{c:float(group[c].median()) for c in BASE_FEATURES},
            "recent_purchase_share_90d_median":float((group["qualifying_purchase_occasions_90d"].astype(float)/group["qualifying_purchase_occasions_365d"].astype(float)).median())}
    zprofile=pd.DataFrame(x,columns=CLUSTER_FEATURES).assign(ml_segment=labels).groupby("ml_segment").mean()
    return {"clusters":raw_profile,"standardized_centroid_profiles":{str(int(i)):{c:float(v) for c,v in row.items()}
              for i,row in zprofile.iterrows()}}


def _internal_memory_bytes() -> int | None:
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system()=="Darwin": return int(value)
    return int(value*1024)


def run_experiment(snapshots: pd.DataFrame, output_dir: Path,
                   *, bootstrap_reps: int = BOOTSTRAP_REPS) -> dict[str, Any]:
    started=time.perf_counter(); ref=snapshots.loc[snapshots[MONTH].astype(str).eq(REFERENCE_MONTH)].copy().reset_index(drop=True)
    if ref.empty or ref[CUSTOMER].duplicated().any():
        raise ValueError("Reference month must contain one unique eligible row per customer.")
    imputer,scaler,x_ref,transform_metadata=fit_reference_transform(ref)
    rules=fit_rfm_rules(ref)
    candidate_results,models=evaluate_candidates(x_ref,bootstrap_reps=bootstrap_reps)
    selection=choose_model(candidate_results)
    # If no method clears the predeclared stability criteria, RFM remains the
    # selected operational baseline; best candidate is still shown descriptively.
    if selection["selected"]:
        chosen=selection["selected"]
        model_name,k=chosen["algorithm"],int(chosen["k"])
        final_model=models[(model_name,k)]
        selection_scope="stability-qualified unsupervised candidate"
    else:
        eligible=[(candidate_results[name][str(k)]["customer_bootstrap_ari_mean"],
                   candidate_results[name][str(k)]["mean_seed_ari"],-k,name,k)
                  for name in ("KMeans","GaussianMixture") for k in K_VALUES]
        _,_,_,model_name,k=max(eligible)
        final_model=models[(model_name,k)]
        selection_scope="no ML candidate met stability rule; selected RFM, best ML candidate shown only descriptively"
    assignments=[]; transformed_by_month={}
    for month in (REFERENCE_MONTH,)+DEV_EVAL_MONTHS+EXPLORATORY_MONTHS:
        rows=snapshots.loc[snapshots[MONTH].astype(str).eq(month)].copy().reset_index(drop=True)
        x=transform_with_reference(rows,imputer,scaler);transformed_by_month[month]=x
        ml=final_model.predict(x)
        rfm=assign_rfm(rows,rules)
        out=rows[[CUSTOMER,MONTH,DECISION]].copy()
        out["ml_segment"]=ml.astype(int);out["rfm_segment"]=rfm.rfm_segment.to_numpy()
        out["rfm_code"]=rfm.rfm_code.to_numpy()
        assignments.append(out)
    assignment_frame=pd.concat(assignments,ignore_index=True)
    if assignment_frame.duplicated([CUSTOMER,MONTH]).any():
        raise ValueError("Snapshot assignment keys are not unique.")
    ref_assign=assignment_frame.loc[assignment_frame[MONTH].astype(str).eq(REFERENCE_MONTH)]
    ml_ref=ref_assign.ml_segment.to_numpy(int)
    rfm_ref=ref_assign.rfm_segment.to_numpy(str)
    reference_cross=pd.crosstab(ref_assign.ml_segment,ref_assign.rfm_segment)
    comparison={"reference_adjusted_rand":float(adjusted_rand_score(ml_ref,rfm_ref)),
                "reference_normalized_mutual_information":float(normalized_mutual_info_score(ml_ref,rfm_ref)),
                "reference_cross_tab":{str(int(i)):{str(c):int(v) for c,v in row.items()}
                                       for i,row in reference_cross.iterrows()},"by_month":{}}
    for month in (REFERENCE_MONTH,)+DEV_EVAL_MONTHS+EXPLORATORY_MONTHS:
        part=assignment_frame.loc[assignment_frame[MONTH].astype(str).eq(month)]
        comparison["by_month"][month]={
            "adjusted_rand_ml_vs_rfm":float(adjusted_rand_score(part.ml_segment,part.rfm_segment)),
            "normalized_mutual_information_ml_vs_rfm":float(normalized_mutual_info_score(part.ml_segment,part.rfm_segment)),
            "cross_tab":{str(int(i)):{str(c):int(v) for c,v in row.items()}
                         for i,row in pd.crosstab(part.ml_segment,part.rfm_segment).astype(int).iterrows()}}
    transitions_dev=transition_summary(assignment_frame,assignment_frame.ml_segment,
                                       (REFERENCE_MONTH,)+DEV_EVAL_MONTHS,"ml_segment")
    transitions_all=transition_summary(assignment_frame,assignment_frame.ml_segment,
                                       (REFERENCE_MONTH,)+DEV_EVAL_MONTHS+EXPLORATORY_MONTHS,"ml_segment")
    rfm_transitions=transition_summary(assignment_frame,assignment_frame.rfm_segment,
                                       (REFERENCE_MONTH,)+DEV_EVAL_MONTHS+EXPLORATORY_MONTHS,"rfm_segment")
    # Match and profile only mature labels. P3-006 private target rows carry
    # individual outcomes outside Git; they are never serialized to aggregate JSON.
    p3out=output_dir.parent/"p3_006_outputs"
    profiles=outcome_profiles(assignment_frame,snapshots,p3out)
    profile=cluster_profiles(ref,ml_ref,x_ref)
    rfmprof={}
    rfm_assign=assign_rfm(ref,rules)
    for segment,group in pd.concat([ref.reset_index(drop=True),rfm_assign.reset_index(drop=True)],axis=1).groupby("rfm_segment",sort=True):
        rfmprof[str(segment)]={"n":len(group),"share":len(group)/len(ref),
            "recency_median_days":float(group[RFM_COLUMNS["recency"]].median()),
            "frequency_median_365d":float(group[RFM_COLUMNS["frequency"]].median()),
            "monetary_median_365d_gbp":float(group[RFM_COLUMNS["monetary"]].median())}
    # Month-by-month size and feature profile shifts for the frozen reference model.
    monthly_profiles={};monthly_sizes=[]
    for month in (REFERENCE_MONTH,)+DEV_EVAL_MONTHS+EXPLORATORY_MONTHS:
        rows=snapshots.loc[snapshots[MONTH].astype(str).eq(month)].copy().reset_index(drop=True)
        x=transformed_by_month[month]
        labels=assignment_frame.loc[assignment_frame[MONTH].astype(str).eq(month),"ml_segment"].to_numpy(int)
        monthly_profiles[month]=cluster_profiles(rows,labels,x)["clusters"]
        monthly_sizes.extend(_month_summary(rows,labels,"ml_segment"))
    # Scores/results selected without any outcome data; only after this point are
    # outcome profiles included in the aggregate artifact.
    result={"experiment":"COMMERCIAL_DS_P3_007","created_utc":datetime.now(timezone.utc).isoformat(),
        "cohort":{"dataset_sha256":EXPECTED_DATASET_SHA256,"manifest_sha256":EXPECTED_MANIFEST_SHA256,
                  "total_snapshot_rows":len(snapshots),"reference_month":REFERENCE_MONTH,
                  "reference_n":len(ref),"reference_unique_customers":int(ref[CUSTOMER].nunique()),
                  "development_evaluation_months":list(DEV_EVAL_MONTHS),
                  "exploratory_replay_months":list(EXPLORATORY_MONTHS),
                  "monthly_counts":{str(k):int(v) for k,v in snapshots.groupby(MONTH).size().items()}},
        "feature_design":{"features":list(CLUSTER_FEATURES),"base_rfm_features":list(BASE_FEATURES),
            "derived_recent_share":"qualifying_purchase_occasions_90d / qualifying_purchase_occasions_365d",
            "log1p_features":list(LOG_FEATURES),"preprocessing":transform_metadata,
            "reference_only_fit":True,"correlation_rule":"Spearman absolute correlation >=0.90 considered strong redundancy; among 11 predictors, occasions365 vs distinct_dates365=0.98 and occasions90 vs gross90=0.98; retain occasions365, omit distinct dates and gross90, and retain bounded recent activity share. Basket value shares log gross correlation 0.68; 365-day occasions and gross correlate 0.82.",
            "excluded_customer_identifiers_and_outcomes":True},
        "rfm_baseline":{"rule":rules,"segments_reference_profiles":rfmprof,
            "assignment_precedence":["Champions","At risk","Hibernating","Loyal","Potential","Big spenders","Regular"]},
        "algorithms":{"kmeans":{"config":"k=3..8; n_init=20; Lloyd; seeds 20261113/14/15"},
                      "gaussian_mixture":{"config":"k=3..8; full covariance; reg_covar=1e-5; n_init=5; max_iter=300; seeds 20261113/14/15"},
                      "agglomerative":{"config":"Ward linkage, k=3..8, full March reference cohort; no native prediction, descriptive only"},
                      "hdbscan":{"status":"not run; dependency unavailable and not needed for fixed-out-of-sample assignment comparison"}},
        "candidate_quality":candidate_results,"model_selection":{**selection,"selection_scope":selection_scope,
            "selection_used_future_outcomes":False},
        "experiment_counts":{"kmeans_seed_fits":len(K_VALUES)*len(SEEDS),
            "gaussian_mixture_seed_fits":len(K_VALUES)*len(SEEDS),
            "customer_bootstrap_fits":2*len(K_VALUES)*bootstrap_reps,
            "agglomerative_fits":len(K_VALUES),
            "total_estimator_fits":2*len(K_VALUES)*len(SEEDS)+2*len(K_VALUES)*bootstrap_reps+len(K_VALUES),
            "silhouette_sample_size":min(SILHOUETTE_SAMPLE,len(ref))},
        "assignment":{"model_algorithm":model_name,"k":int(k),"reference_fit_month":REFERENCE_MONTH,
            "prediction_rule":"KMeans nearest-centroid predict or GaussianMixture posterior maximum; same frozen reference preprocessing; no evaluation refit.",
            "development_months":list(DEV_EVAL_MONTHS),"exploratory_months":list(EXPLORATORY_MONTHS)},
        "reference_cluster_profiles":profile,"monthly_cluster_profiles":monthly_profiles,
        "monthly_cluster_sizes":monthly_sizes,
        "temporal_transitions":{"development_only":transitions_dev,"through_exploratory_replay":transitions_all,
                                "rfm_through_exploratory_replay":rfm_transitions},
        "rfm_comparison":comparison,
        "mature_30_day_outcome_profiles_descriptive_only":profiles,
        "runtime":{"experiment_seconds":time.perf_counter()-started,"seed_values":list(SEEDS),
                    "customer_bootstrap_repetitions_per_k_algorithm":bootstrap_reps,
                    "max_resident_set_bytes":_internal_memory_bytes(),
                    "python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,
                    "scipy":scipy.__version__,"scikit_learn":sklearn.__version__},
        "limitations":["March is a one-month reference fit, not a seasonal training panel.",
                       "Rows in later months repeat customers; transition comparisons use matched customers and report entrants/leavers.",
                       "July-November is an exploratory replay: its outcomes have already been examined.",
                       "Internal metrics are geometric summaries, not commercial value tests.",
                       "Cluster outcome contrasts are observational and do not establish incremental campaign effect."]}
    output_dir.mkdir(parents=True,exist_ok=True);private=output_dir/"private";private.mkdir(parents=True,exist_ok=True)
    assignment_frame.to_parquet(private/"p3_007_customer_month_assignments.parquet",index=False)
    (output_dir/"p3_007_aggregate_results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    manifest={"experiment":"P3-007","dataset_sha256":EXPECTED_DATASET_SHA256,
              "aggregate_sha256":_sha256(output_dir/"p3_007_aggregate_results.json"),
              "private_files":["private/p3_007_customer_month_assignments.parquet"],
              "reference_month":REFERENCE_MONTH,"selected_algorithm":model_name,"selected_k":int(k)}
    (output_dir/"p3_007_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    plot_outputs(result,output_dir)
    return result


def _sha256(path: Path) -> str:
    import hashlib
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def plot_outputs(result: dict[str,Any], output_dir: Path) -> None:
    import matplotlib.pyplot as plt
    figures=ROOT/"docs/research/figures";figures.mkdir(parents=True,exist_ok=True)
    chosen=result["model_selection"].get("selected")
    if chosen is None:
        chosen=result["assignment"]
    profiles=result["reference_cluster_profiles"]["standardized_centroid_profiles"]
    labels=sorted(profiles,key=lambda x:int(x));features=list(CLUSTER_FEATURES)
    arr=np.asarray([[profiles[label][feature] for feature in features] for label in labels])
    fig,ax=plt.subplots(figsize=(8,4.5));im=ax.imshow(arr,aspect="auto",cmap="coolwarm",vmin=-2,vmax=2)
    ax.set_xticks(range(len(features)),["Log days since last purchase (higher = less recent)","Frequency","Spend","Basket value","Recent share"],rotation=25,ha="right")
    ax.set_yticks(range(len(labels)),[f"Cluster {x}" for x in labels]);ax.set_title(f"Reference cluster profiles ({result['assignment']['model_algorithm']}, k={result['assignment']['k']})")
    fig.colorbar(im,ax=ax,label="Standard deviations from March reference mean");fig.tight_layout()
    fig.savefig(figures/"p3_007_cluster_feature_profiles.png",dpi=160);plt.close(fig)
    # RFM and ML segment sizes in the reference month.
    rfm=result["rfm_baseline"]["segments_reference_profiles"]
    ml=result["reference_cluster_profiles"]["clusters"]
    names=list(rfm);sizes=[rfm[n]["n"] for n in names]
    ml_names=sorted(ml,key=int);ml_sizes=[ml[n]["n"] for n in ml_names]
    fig,axes=plt.subplots(1,2,figsize=(10,4),sharey=False)
    axes[0].bar(np.arange(len(names)),sizes,color="tab:blue")
    axes[0].set_xticks(np.arange(len(names)),names,rotation=35,ha="right");axes[0].set_ylabel("Reference snapshots");axes[0].set_title("RFM rules")
    axes[1].bar(np.arange(len(ml_names)),ml_sizes,color="tab:orange")
    axes[1].set_xticks(np.arange(len(ml_names)),ml_names);axes[1].set_title(f"{result['assignment']['model_algorithm']} clusters")
    fig.suptitle("March reference segment sizes");fig.tight_layout();fig.savefig(figures/"p3_007_segment_sizes.png",dpi=160);plt.close(fig)
    # Most recent in-development to first exploratory month transition.
    matrix=result["temporal_transitions"]["through_exploratory_replay"]["transition_matrices"].get("2011-06_to_2011-07")
    if matrix:
        fig,ax=plt.subplots(figsize=(5,4));im=ax.imshow(np.asarray(matrix["row_normalized"]),vmin=0,vmax=1,cmap="Blues")
        ax.set(xlabel="July assigned cluster",ylabel="June assigned cluster",title="Matched customer transitions (June → July)")
        ax.set_xticks(range(len(matrix["labels"])),matrix["labels"]);ax.set_yticks(range(len(matrix["labels"])),matrix["labels"])
        fig.colorbar(im,ax=ax,label="Row proportion");fig.tight_layout();fig.savefig(figures/"p3_007_june_july_transition.png",dpi=160);plt.close(fig)
    cross=result["rfm_comparison"]["reference_cross_tab"]
    all_rfm=sorted({k for vals in cross.values() for k in vals})
    ml_ids=sorted(cross,key=int);mat=np.asarray([[cross[m].get(r,0) for r in all_rfm] for m in ml_ids])
    fig,ax=plt.subplots(figsize=(8,4.5));im=ax.imshow(mat,aspect="auto",cmap="Purples")
    ax.set_xticks(range(len(all_rfm)),all_rfm,rotation=35,ha="right");ax.set_yticks(range(len(ml_ids)),ml_ids)
    ax.set(xlabel="RFM rule segment",ylabel="ML cluster",title="March reference ML × RFM cross-tab")
    fig.colorbar(im,ax=ax,label="Customer snapshots");fig.tight_layout();fig.savefig(figures/"p3_007_rfm_cluster_crosstab.png",dpi=160);plt.close(fig)


def main() -> None:
    parser=argparse.ArgumentParser()
    data_root=ROOT.parent/"source_data/uci_online_retail_ii"
    parser.add_argument("--dataset",type=Path,default=data_root/"monthly_customer_snapshots_m2_004.parquet")
    parser.add_argument("--manifest",type=Path,default=data_root/"monthly_customer_snapshots_m2_004.parquet.manifest.json")
    parser.add_argument("--output-dir",type=Path,default=data_root/"p3_007_outputs")
    parser.add_argument("--bootstrap-reps",type=int,default=BOOTSTRAP_REPS)
    args=parser.parse_args()
    if ROOT in args.output_dir.resolve().parents or args.output_dir.resolve()==ROOT:
        raise ValueError("P3-007 private outputs must remain outside the repository.")
    _,snapshots=verify_frozen_inputs(args.dataset,args.manifest)
    result=run_experiment(snapshots,args.output_dir,bootstrap_reps=args.bootstrap_reps)
    print(json.dumps({"selected":result["model_selection"],"assignment":result["assignment"],
                      "runtime":result["runtime"]},indent=2))


if __name__=="__main__":main()

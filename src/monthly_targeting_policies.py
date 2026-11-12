"""Aggregate retrospective targeting-policy comparison for the M2 holdout."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DATASET_SHA256 = "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8"
EXPECTED_SOURCE_MANIFEST_SHA256 = "3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13"
EXPECTED_PREDICTIONS_SHA256 = "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1"
EXPECTED_M2_RUN_MANIFEST_SHA256 = "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a"
CUSTOMER = "customer_id"
MONTH = "snapshot_month"
DECISION = "decision_time"
LABEL = "outcome_label"
MODEL_C = "probability_C_full_11"
MODEL_B = "probability_B_rfm"
FREQUENCY = "qualifying_purchase_dates_365d"
CAPACITIES = (0.05, 0.10, 0.20)
MONTHS = ("2011-07", "2011-08", "2011-09", "2011-10", "2011-11")
POLICIES = ("model_c", "rfm", "frequency")
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261112


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capacity_count(n_eligible: int, capacity: float) -> int:
    if n_eligible < 0 or not 0 < capacity <= 1:
        raise ValueError("Eligible count must be nonnegative and capacity in (0,1].")
    return int(np.ceil(capacity * n_eligible)) if n_eligible else 0


def verify_and_load(dataset_path: Path, source_manifest_path: Path, predictions_path: Path, run_manifest_path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    paths = {
        "dataset": dataset_path,
        "source_manifest": source_manifest_path,
        "predictions": predictions_path,
        "baseline_run_manifest": run_manifest_path,
    }
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    expected = {
        "dataset": EXPECTED_DATASET_SHA256,
        "source_manifest": EXPECTED_SOURCE_MANIFEST_SHA256,
        "predictions": EXPECTED_PREDICTIONS_SHA256,
        "baseline_run_manifest": EXPECTED_M2_RUN_MANIFEST_SHA256,
    }
    if hashes != expected:
        raise ValueError(f"Frozen M2 inputs do not match their hashes: {hashes}")
    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("output_sha256") != EXPECTED_DATASET_SHA256:
        raise ValueError("Dataset manifest does not pin the expected Parquet.")
    if run_manifest.get("dataset_sha256") != EXPECTED_DATASET_SHA256 or run_manifest.get("protocol_sha256") != "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4":
        raise ValueError("Baseline run manifest does not match frozen M2 data/protocol.")
    cohort = pd.read_parquet(dataset_path)
    predictions = pd.read_parquet(predictions_path)
    for frame in (cohort, predictions):
        frame[DECISION] = pd.to_datetime(frame[DECISION])
    test = cohort.loc[cohort["evaluation_partition"].eq("test")].copy()
    if len(test) != 21672 or test.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Unexpected test population or duplicate customer-month keys.")
    if not test["outcome_window_mature"].all() or not test[LABEL].isin([0, 1]).all():
        raise ValueError("Targeting evaluation requires mature binary outcomes.")
    if not test["outcome_coverage_status"].eq("complete").all():
        raise ValueError("Targeting evaluation includes incomplete outcome coverage.")
    selected_predictions = predictions[[CUSTOMER, DECISION, LABEL, MODEL_C, MODEL_B]].copy()
    if len(selected_predictions) != 21672 or selected_predictions.duplicated([CUSTOMER, DECISION]).any():
        raise ValueError("Frozen prediction artifact has an unexpected schema/count.")
    data = test.merge(selected_predictions, on=[CUSTOMER, DECISION], how="inner", validate="one_to_one", suffixes=("", "_prediction"))
    if len(data) != len(test) or not data[LABEL].eq(data[f"{LABEL}_prediction"]).all():
        raise ValueError("Frozen predictions do not align with the approved labels.")
    data = data.drop(columns=[f"{LABEL}_prediction"])
    expected_months = {"2011-07": 4314, "2011-08": 4326, "2011-09": 4324, "2011-10": 4364, "2011-11": 4344}
    if data.groupby(MONTH).size().to_dict() != expected_months:
        raise ValueError("M2-008 test month counts differ from the frozen results.")
    if not data[FREQUENCY].notna().all() or (data[FREQUENCY] < 0).any():
        raise ValueError("Frequency policy feature is missing or invalid.")
    for score in (MODEL_C, MODEL_B):
        if not np.isfinite(data[score].to_numpy(float)).all():
            raise ValueError(f"Frozen score {score} contains non-finite values.")
    return data.sort_values([MONTH, CUSTOMER], kind="mergesort").reset_index(drop=True), hashes


def select_ranked(frame: pd.DataFrame, score_column: str, capacity: float, *, descending: bool = True) -> pd.DataFrame:
    """Select exact capacity with deterministic customer-key tie-breaking."""
    if frame[CUSTOMER].duplicated().any():
        raise ValueError("Each customer may appear only once in a monthly selection.")
    k = capacity_count(len(frame), capacity)
    ordered = frame.assign(_customer_tie=frame[CUSTOMER].astype(str)).sort_values(
        [score_column, "_customer_tie"], ascending=[not descending, True], kind="mergesort"
    )
    return ordered.head(k).drop(columns="_customer_tie")


def _selected_metrics(n: int, positives: int, selected_n: int, selected_positive: float) -> dict[str, float | int]:
    if n <= 0 or selected_n <= 0:
        raise ValueError("Population and selected count must be positive.")
    prevalence = positives / n
    precision = selected_positive / selected_n
    return {
        "eligible_customers": int(n),
        "selected_customers": int(selected_n),
        "selected_positive_outcomes": float(selected_positive),
        "eligible_positive_outcomes": int(positives),
        "precision": float(precision),
        "purchase_capture_recall": float(selected_positive / positives) if positives else 0.0,
        "monthly_prevalence": float(prevalence),
        "lift": float(precision / prevalence) if prevalence else None,
    }


def _random_expected(n: int, positives: int, selected_n: int) -> dict[str, float | int]:
    prevalence = positives / n
    expected_positive = selected_n * prevalence
    return {
        "eligible_customers": int(n),
        "selected_customers": int(selected_n),
        "selected_positive_outcomes": float(expected_positive),
        "eligible_positive_outcomes": int(positives),
        "precision": float(prevalence),
        "purchase_capture_recall": float(selected_n / n),
        "monthly_prevalence": float(prevalence),
        "lift": 1.0,
        "method": "analytical uniform-selection expectation; no random customer list drawn",
    }


def _policy_score(policy: str) -> tuple[str, bool]:
    if policy == "model_c":
        return MODEL_C, True
    if policy == "rfm":
        return MODEL_B, True
    if policy == "frequency":
        return FREQUENCY, True
    raise ValueError(f"Unknown ranked policy: {policy}")


def _selection_metrics_and_overlap(data: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    monthly: dict[str, Any] = {}
    selected_rows: list[pd.DataFrame] = []
    pooled_acc: dict[float, dict[str, dict[str, float]]] = {}
    contact_counts: dict[str, dict[float, dict[str, int]]] = {
        policy: {capacity: {} for capacity in CAPACITIES} for policy in POLICIES
    }
    for month in MONTHS:
        group = data.loc[data[MONTH].eq(month)].copy()
        n = len(group)
        y = group[LABEL].to_numpy(int)
        positives = int(y.sum())
        month_result: dict[str, Any] = {
            "eligible_customers": n,
            "unique_customers": int(group[CUSTOMER].nunique()),
            "positive_outcomes": positives,
            "negative_outcomes": int(n - positives),
            "prevalence": float(y.mean()),
            "capacities": {},
        }
        if group[CUSTOMER].nunique() != n:
            raise AssertionError(f"Duplicate customer in monthly evaluation: {month}")
        for capacity in CAPACITIES:
            k = capacity_count(n, capacity)
            policy_selections: dict[str, pd.DataFrame] = {}
            policy_metrics: dict[str, Any] = {}
            for policy in POLICIES:
                score, descending = _policy_score(policy)
                selected = select_ranked(group, score, capacity, descending=descending)
                policy_selections[policy] = selected
                metric = _selected_metrics(n, positives, len(selected), float(selected[LABEL].sum()))
                policy_metrics[policy] = metric
                exported = selected[[CUSTOMER, DECISION, MONTH, LABEL]].copy()
                exported["policy"] = policy
                exported["capacity"] = capacity
                exported["policy_score"] = selected[score].to_numpy(float)
                selected_rows.append(exported)
                for customer in selected[CUSTOMER].astype(str):
                    month_contacts = contact_counts[policy][capacity]
                    month_contacts[customer] = month_contacts.get(customer, 0) + 1
            policy_metrics["random"] = _random_expected(n, positives, k)
            for policy in POLICIES:
                for metric_name in ("precision", "purchase_capture_recall", "lift"):
                    policy_metrics[policy][f"difference_vs_random_{metric_name}"] = (
                        policy_metrics[policy][metric_name] - policy_metrics["random"][metric_name]
                    )

            full_set = set(policy_selections["model_c"][CUSTOMER])
            overlap: dict[str, Any] = {}
            for policy in POLICIES:
                other = set(policy_selections[policy][CUSTOMER])
                intersection = len(full_set & other)
                union = len(full_set | other)
                overlap[policy] = {
                    "intersection_with_model_c": intersection,
                    "share_of_model_c_selected": intersection / len(full_set),
                    "jaccard_with_model_c": intersection / union if union else 1.0,
                }
            expected_random_overlap = k * k / n
            overlap["random_expected"] = {
                "expected_intersection_with_model_c": expected_random_overlap,
                "expected_share_of_model_c_selected": expected_random_overlap / k,
                "interpretation": "expectation for a uniform size-k random list; no realized identities",
            }
            month_result["capacities"][f"{int(capacity * 100)}pct"] = {
                "selected_per_policy": policy_metrics,
                "overlap_with_model_c": overlap,
            }
            for policy in (*POLICIES, "random"):
                pooled_acc.setdefault(capacity, {}).setdefault(policy, {"selected": 0.0, "selected_positive": 0.0})
                pooled_acc[capacity][policy]["selected"] += float(policy_metrics[policy]["selected_customers"])
                pooled_acc[capacity][policy]["selected_positive"] += float(policy_metrics[policy]["selected_positive_outcomes"])
        monthly[month] = month_result
    selections = pd.concat(selected_rows, ignore_index=True)
    pooled: dict[str, Any] = {}
    total_n = int(len(data))
    total_positive = int(data[LABEL].sum())
    for capacity in CAPACITIES:
        pooled[f"{int(capacity * 100)}pct"] = {}
        for policy in (*POLICIES, "random"):
            acc = pooled_acc[capacity][policy]
            selected_n = acc["selected"]
            selected_positive = acc["selected_positive"]
            precision = selected_positive / selected_n
            prevalence = total_positive / total_n
            pooled[f"{int(capacity * 100)}pct"][policy] = {
                "eligible_snapshots": total_n,
                "eligible_customers_by_month_sum": sum(int(data.loc[data[MONTH].eq(m), CUSTOMER].nunique()) for m in MONTHS),
                "selected_snapshot_events": selected_n,
                "selected_positive_outcomes": selected_positive,
                "eligible_positive_outcomes": total_positive,
                "precision_snapshot_weighted": precision,
                "purchase_capture_recall_snapshot_weighted": selected_positive / total_positive,
                "pooled_prevalence_snapshot_weighted": prevalence,
                "lift_over_pooled_prevalence": precision / prevalence,
                "difference_vs_random_precision": precision - (acc["selected_positive"] / selected_n if policy == "random" else pooled_acc[capacity]["random"]["selected_positive"] / pooled_acc[capacity]["random"]["selected"]),
                "difference_vs_random_capture": selected_positive / total_positive - pooled_acc[capacity]["random"]["selected_positive"] / total_positive,
                "difference_vs_random_lift": precision / prevalence - 1.0,
            }
    for capacity in CAPACITIES:
        for policy in POLICIES:
            value = pooled[f"{int(capacity * 100)}pct"][policy]
            random_value = pooled[f"{int(capacity * 100)}pct"]["random"]
            value["difference_vs_random_precision"] = value["precision_snapshot_weighted"] - random_value["precision_snapshot_weighted"]
            value["difference_vs_random_capture"] = value["purchase_capture_recall_snapshot_weighted"] - random_value["purchase_capture_recall_snapshot_weighted"]
            value["difference_vs_random_lift"] = value["lift_over_pooled_prevalence"] - random_value["lift_over_pooled_prevalence"]

    overlap_pooled: dict[str, Any] = {}
    for capacity in CAPACITIES:
        tag = f"{int(capacity * 100)}pct"
        sums = {policy: 0 for policy in POLICIES}
        totals = {policy: 0 for policy in POLICIES}
        union_sums = {policy: 0 for policy in POLICIES}
        random_expected = 0.0
        random_expected_c = 0
        for month in MONTHS:
            group = data.loc[data[MONTH].eq(month)]
            n = len(group)
            k = capacity_count(n, capacity)
            selected = {policy: set(selections.loc[(selections[MONTH].eq(month)) & (selections.capacity.eq(capacity)) & (selections.policy.eq(policy)), CUSTOMER]) for policy in POLICIES}
            cset = selected["model_c"]
            for policy in POLICIES:
                inter = len(cset & selected[policy])
                sums[policy] += inter
                totals[policy] += len(cset)
                union_sums[policy] += len(cset | selected[policy])
            random_expected += k * k / n
            random_expected_c += k
        for policy in POLICIES:
            overlap_pooled.setdefault(tag, {})[policy] = {
                "intersection_count_across_monthly_snapshots": sums[policy],
                "share_of_model_c_selections": sums[policy] / totals[policy] if totals[policy] else None,
                "jaccard_of_summed_monthly_sets": sums[policy] / union_sums[policy] if union_sums[policy] else None,
            }
        overlap_pooled[tag]["random_expected"] = {
            "expected_intersection_count_across_monthly_snapshots": random_expected,
            "expected_share_of_model_c_selections": random_expected / random_expected_c,
            "note": "Expected overlap; not a realized random target list.",
        }

    concentration = {}
    for policy, policy_capacities in contact_counts.items():
        concentration[policy] = {}
        for capacity, counts in policy_capacities.items():
            values = list(counts.values())
            concentration[policy][f"{int(capacity * 100)}pct"] = {
                "unique_customers_selected_at_least_once": len(values),
                "total_customer_month_contact_events": int(sum(values)),
                "customers_selected_in_multiple_months": int(sum(value >= 2 for value in values)),
                "maximum_months_selected": int(max(values, default=0)),
            }
    monthly["pooled_snapshot_weighted"] = pooled
    monthly["pooled_overlap_with_model_c"] = overlap_pooled
    monthly["contact_concentration_ranked_policies"] = concentration
    return monthly, selections, contact_counts


def _weighted_selection_positive(
    y: np.ndarray, row_weights: np.ndarray, sorted_indices: np.ndarray, k: int,
) -> tuple[float, np.ndarray]:
    ordered_weights = row_weights[sorted_indices]
    before = np.cumsum(ordered_weights) - ordered_weights
    selected_weights = np.minimum(ordered_weights, np.maximum(0.0, k - before))
    return float(np.dot(selected_weights, y[sorted_indices])), selected_weights


def paired_customer_cluster_bootstrap(
    data: pd.DataFrame, *, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Bootstrap customer trajectories; recompute each month's top-k selections."""
    customer_values, customer_codes = np.unique(data[CUSTOMER].astype(str).to_numpy(), return_inverse=True)
    if len(customer_values) < 2:
        raise ValueError("At least two customer clusters are required.")
    rng = np.random.Generator(np.random.PCG64(seed))
    labels = data[LABEL].to_numpy(dtype=float)
    months = data[MONTH].astype(str).to_numpy()
    policies = {name: data[_policy_score(name)[0]].to_numpy(dtype=float) for name in POLICIES}
    sorted_order: dict[tuple[str, str], np.ndarray] = {}
    month_indices: dict[str, np.ndarray] = {}
    for month in MONTHS:
        idx = np.flatnonzero(months == month)
        month_indices[month] = idx
        keys = data.iloc[idx][CUSTOMER].astype(str).to_numpy()
        for policy in POLICIES:
            score = policies[policy][idx]
            # lexsort's last key is primary: descending score, then stable customer-key tie break.
            sorted_order[(month, policy)] = idx[np.lexsort((keys, -score))]
    draws_by_capacity = {
        capacity: {comparison: {metric: [] for metric in ("precision", "capture", "lift")} for comparison in ("model_c_minus_rfm", "model_c_minus_frequency", "model_c_minus_random")}
        for capacity in CAPACITIES
    }
    omitted = 0
    for _ in range(n_resamples):
        draws = rng.integers(0, len(customer_values), size=len(customer_values))
        cluster_weights = np.bincount(draws, minlength=len(customer_values)).astype(float)
        row_weights = cluster_weights[customer_codes]
        replicate_results: dict[float, dict[str, dict[str, float]]] = {}
        valid = True
        for capacity in CAPACITIES:
            accum = {policy: {"selected": 0.0, "selected_positive": 0.0} for policy in (*POLICIES, "random")}
            total_eligible = total_positive = 0.0
            for month in MONTHS:
                idx = month_indices[month]
                weights_month = row_weights[idx]
                n_weight = float(weights_month.sum())
                positive_weight = float(np.dot(weights_month, labels[idx]))
                if n_weight == 0:
                    continue
                k = capacity_count(int(n_weight), capacity)
                total_eligible += n_weight
                total_positive += positive_weight
                for policy in POLICIES:
                    pos, _ = _weighted_selection_positive(labels, row_weights, sorted_order[(month, policy)], k)
                    accum[policy]["selected"] += k
                    accum[policy]["selected_positive"] += pos
                accum["random"]["selected"] += k
                accum["random"]["selected_positive"] += k * positive_weight / n_weight
            if total_eligible <= 0 or total_positive <= 0:
                valid = False
                break
            replicate_results[capacity] = {}
            prevalence = total_positive / total_eligible
            for policy in (*POLICIES, "random"):
                selected = accum[policy]["selected"]
                selected_positive = accum[policy]["selected_positive"]
                precision = selected_positive / selected
                capture = selected_positive / total_positive
                replicate_results[capacity][policy] = {
                    "precision": precision,
                    "capture": capture,
                    "lift": precision / prevalence,
                }
        if not valid:
            omitted += 1
            continue
        for capacity in CAPACITIES:
            result = replicate_results[capacity]
            for comparison, other in (("model_c_minus_rfm", "rfm"), ("model_c_minus_frequency", "frequency"), ("model_c_minus_random", "random")):
                for metric in ("precision", "capture", "lift"):
                    draws_by_capacity[capacity][comparison][metric].append(result["model_c"][metric] - result[other][metric])
    intervals: dict[str, Any] = {}
    for capacity in CAPACITIES:
        tag = f"{int(capacity * 100)}pct"
        intervals[tag] = {}
        for comparison, metric_values in draws_by_capacity[capacity].items():
            intervals[tag][comparison] = {}
            for metric, values in metric_values.items():
                if values:
                    low, high = np.percentile(values, [2.5, 97.5])
                    intervals[tag][comparison][metric] = [float(low), float(high)]
                else:
                    intervals[tag][comparison][metric] = [None, None]
    return {
        "method": "paired customer-cluster bootstrap; sample customer trajectories with replacement, preserve multiplicity, reselect monthly top-k",
        "requested_resamples": n_resamples,
        "valid_resamples": n_resamples - omitted,
        "omitted_resamples": omitted,
        "seed": seed,
        "interval_method": "two-sided percentile 95% interval",
        "estimand": "snapshot-weighted pooled July-November policy contrasts conditional on this historical holdout; monthly capacities recomputed using ceil(capacity × bootstrap snapshot count)",
        "difference_intervals": intervals,
        "limitations": "Customer resampling captures repeated-month dependence, not uncertainty across future calendar periods. Random policy is its analytical expectation, so intervals do not include finite random-list draw variability.",
    }


def run_analysis(data: pd.DataFrame, hashes: dict[str, str], *, n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> tuple[dict[str, Any], pd.DataFrame]:
    monthly, selected, _ = _selection_metrics_and_overlap(data)
    bootstrap = paired_customer_cluster_bootstrap(data, n_resamples=n_resamples, seed=seed)
    aggregate = {
        "experiment": "M3-002 retrospective targeting policies; exploratory analysis of previously examined holdout",
        "input_sha256": hashes,
        "holdout": {
            "months": list(MONTHS), "snapshots": int(len(data)),
            "unique_customers_across_holdout": int(data[CUSTOMER].nunique()),
            "positive_snapshots": int(data[LABEL].sum()),
            "pooled_prevalence_snapshot_weighted": float(data[LABEL].mean()),
            "mature_only": bool(data["outcome_window_mature"].all()),
        },
        "capacity_rule": "ceil(capacity × eligible customer-month snapshots in that month)",
        "tie_break_rule": "rank score descending, then customer key ascending; applies to Model C, RFM and frequency",
        "policies": {
            "model_c": "frozen probability_C_full_11 descending",
            "rfm": "frozen probability_B_rfm descending",
            "frequency": "qualifying_purchase_dates_365d descending; no fitted model",
            "random": "analytical uniform-selection expectation; no sampled random list",
        },
        "frequency_definition_note": "This milestone follows the requested qualifying_purchase_dates_365d rule; M3-001 had suggested the alternative existing 90-day occasion count.",
        "monthly_and_pooled_results": monthly,
        "paired_customer_cluster_bootstrap": bootstrap,
        "interpretation_limit": "Precision, capture and lift measure retrospective purchase propensity only; they do not estimate incremental CRM impact.",
    }
    return aggregate, selected


def write_outputs(aggregate: dict[str, Any], selected: pd.DataFrame, output_dir: Path) -> dict[str, str]:
    repo = ROOT.resolve()
    destination = output_dir.resolve()
    if destination == repo or repo in destination.parents:
        raise ValueError("Row-level selections must be stored outside the repository.")
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        "aggregate": destination / "m3_002_targeting_aggregate.json",
        "selections": destination / "m3_002_targeting_selections.parquet",
        "manifest": destination / "m3_002_targeting_manifest.json",
    }
    if any(path.exists() for path in files.values()):
        raise FileExistsError("Refusing to overwrite existing M3-002 outputs.")
    files["aggregate"].write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    selected.to_parquet(files["selections"], index=False)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": aggregate["input_sha256"],
        "output_sha256": {"aggregate": sha256_file(files["aggregate"]), "selections": sha256_file(files["selections"])},
        "output_files": {key: path.name for key, path in files.items()},
        "row_level_selections_outside_repository": True,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {key: str(path) for key, path in files.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--baseline-run-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    parser.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED)
    args = parser.parse_args(argv)
    data, hashes = verify_and_load(args.dataset, args.source_manifest, args.predictions, args.baseline_run_manifest)
    aggregate, selected = run_analysis(data, hashes, n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed)
    outputs = write_outputs(aggregate, selected, args.output_dir)
    print(json.dumps({"holdout": aggregate["holdout"], "pooled": aggregate["monthly_and_pooled_results"]["pooled_snapshot_weighted"], "bootstrap": aggregate["paired_customer_cluster_bootstrap"], "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

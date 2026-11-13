"""One-shot confirmatory and secondary evaluation on the frozen Hillstrom test split.

This module performs no model fitting or selection. It loads test rows only after
verifying the P3-008A source and split hashes; row-level output stays private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import hypergeom, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hillstrom_causal_audit import DEFAULT_DATA, DEFAULT_OUTPUT, sha256  # noqa: E402

DATA_SHA256 = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
SPLIT_SHA256 = "0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce"
SPLIT_PATH = DEFAULT_OUTPUT / "hillstrom_row_split_private.csv"
OUTPUT_PATH = ROOT.parent / "source_data/hillstrom/p3_008c_outputs"
ARMS = ("Mens E-Mail", "Womens E-Mail", "No E-Mail")
OUTCOMES = ("visit", "conversion", "spend")
PRIMARY_CONTRAST = ("Mens E-Mail", "No E-Mail")
SECONDARY_CONTRASTS = (
    ("Mens E-Mail", "No E-Mail"),
    ("Womens E-Mail", "No E-Mail"),
    ("Mens E-Mail", "Womens E-Mail"),
)
SEED = 20261118
SPEND_BOOTSTRAP_REPS = 20_000
SPEND_PERMUTATION_REPS = 50_000
POLICY_BUDGET = 0.20


def wilson_interval(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for one binomial proportion, without continuity correction."""
    if n <= 0 or successes < 0 or successes > n:
        raise ValueError("Wilson interval requires 0 <= successes <= n and n > 0.")
    z = float(norm.ppf(1 - alpha / 2)); p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return float(center - half), float(center + half)


def newcombe_risk_difference_interval(x_t: int, n_t: int, x_c: int, n_c: int,
                                      alpha: float = 0.05) -> tuple[float, float]:
    """Newcombe uncorrected Wilson-score interval (independent proportions)."""
    p_t = x_t / n_t; p_c = x_c / n_c; diff = p_t - p_c
    lt, ut = wilson_interval(x_t, n_t, alpha)
    lc, uc = wilson_interval(x_c, n_c, alpha)
    lower = diff - np.sqrt((p_t - lt) ** 2 + (uc - p_c) ** 2)
    upper = diff + np.sqrt((ut - p_t) ** 2 + (p_c - lc) ** 2)
    return float(lower), float(upper)


def exact_binary_randomization_pvalue(x_t: int, n_t: int, x_c: int, n_c: int) -> float:
    """Exact two-sided conditional randomization p-value using |risk difference|."""
    if min(n_t, n_c) <= 0 or min(x_t, x_c) < 0 or x_t > n_t or x_c > n_c:
        raise ValueError("Invalid binary contrast counts.")
    n = n_t + n_c; successes = x_t + x_c; observed = x_t / n_t - x_c / n_c
    lo = max(0, n_t - (n - successes)); hi = min(n_t, successes)
    possible = np.arange(lo, hi + 1)
    treated_success = possible
    control_success = successes - possible
    diffs = treated_success / n_t - control_success / n_c
    pmf = hypergeom.pmf(possible, n, successes, n_t)
    return float(np.clip(pmf[np.abs(diffs) >= abs(observed) - 1e-12].sum(), 0, 1))


def binary_risk_difference(frame: pd.DataFrame, outcome: str = "visit") -> dict:
    """Risk difference and predeclared Newcombe/Wilson and exact RI diagnostics."""
    if set(frame.treatment.unique()) != {0, 1}:
        raise ValueError("Both randomized contrast arms are required.")
    y = frame[outcome].to_numpy(dtype=int)
    if not np.isin(y, [0, 1]).all():
        raise ValueError(f"{outcome} must be binary.")
    a = frame.treatment.to_numpy(dtype=int)
    n_t = int((a == 1).sum()); n_c = int((a == 0).sum())
    x_t = int(y[a == 1].sum()); x_c = int(y[a == 0].sum())
    p_t = x_t / n_t; p_c = x_c / n_c; rd = p_t - p_c
    se = float(np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c))
    lo, hi = newcombe_risk_difference_interval(x_t, n_t, x_c, n_c)
    return {"n_treated": n_t, "events_treated": x_t, "rate_treated": p_t,
            "n_control": n_c, "events_control": x_c, "rate_control": p_c,
            "realized_propensity": float(n_t / (n_t + n_c)),
            "risk_difference": rd, "risk_difference_pp": rd * 100,
            "additional_events_per_1000": rd * 1000, "standard_error": se,
            "ci95_low": lo, "ci95_high": hi,
            "ci95_low_pp": lo * 100, "ci95_high_pp": hi * 100,
            "exact_two_sided_randomization_p":
                exact_binary_randomization_pvalue(x_t, n_t, x_c, n_c),
            "ci_method": "Newcombe hybrid-score interval using uncorrected Wilson limits",
            "test_method": "exact conditional randomization test; two-sided absolute risk difference"}


def map_contrast(frame: pd.DataFrame, treated_arm: str, control_arm: str) -> pd.DataFrame:
    """Filter a pair of randomized arms and map assignment to 1/0."""
    if treated_arm == control_arm or treated_arm not in ARMS or control_arm not in ARMS:
        raise ValueError("Contrast must contain two distinct documented arms.")
    out = frame.loc[frame.segment.isin([treated_arm, control_arm])].copy()
    out["treatment"] = out.segment.eq(treated_arm).astype(np.int8)
    if set(out.treatment.unique()) != {0, 1}:
        raise ValueError("Both arms must be present in the contrast population.")
    return out


def frozen_test_row_indices(split: pd.DataFrame) -> np.ndarray:
    """Validate the frozen split schema and return only test row indices."""
    if list(split.columns) != ["row_index", "split"]:
        raise ValueError("Unexpected split schema.")
    if split.row_index.duplicated().any() or set(split.split.unique()) != {"train", "development", "test"}:
        raise ValueError("Split membership is incomplete or duplicated.")
    return split.loc[split.split.eq("test"), "row_index"].astype(int).to_numpy()


def mean_difference(frame: pd.DataFrame, outcome: str) -> dict:
    """Difference in arithmetic means, positive for treatment minus control."""
    a = frame.treatment.to_numpy(dtype=int); y = frame[outcome].to_numpy(dtype=float)
    if not np.isfinite(y).all():
        raise ValueError("Mean outcome must be finite.")
    yt = y[a == 1]; yc = y[a == 0]
    return {"n_treated": len(yt), "n_control": len(yc),
            "realized_propensity": float(len(yt) / len(y)),
            "mean_treated": float(yt.mean()), "mean_control": float(yc.mean()),
            "difference": float(yt.mean() - yc.mean())}


def stratified_bootstrap_mean_difference(frame: pd.DataFrame, outcome: str,
                                          reps: int = SPEND_BOOTSTRAP_REPS,
                                          seed: int = SEED) -> dict:
    """Customer-row percentile bootstrap, resampling within assigned arms."""
    a = frame.treatment.to_numpy(dtype=int); y = frame[outcome].to_numpy(dtype=float)
    yt = y[a == 1]; yc = y[a == 0]
    rng = np.random.default_rng(seed); draws = np.empty(reps)
    batch_size = 250
    for start in range(0, reps, batch_size):
        b = min(batch_size, reps - start)
        it = rng.integers(0, len(yt), size=(b, len(yt)))
        ic = rng.integers(0, len(yc), size=(b, len(yc)))
        draws[start:start + b] = yt[it].mean(axis=1) - yc[ic].mean(axis=1)
    return {"ci95_low": float(np.quantile(draws, .025)),
            "ci95_high": float(np.quantile(draws, .975)),
            "reps": reps, "seed": seed,
            "method": "stratified customer-row percentile bootstrap"}


def randomization_test_mean_difference(frame: pd.DataFrame, outcome: str,
                                       reps: int = SPEND_PERMUTATION_REPS,
                                       seed: int = SEED) -> dict:
    """Fixed-count Monte Carlo randomization test for a mean difference."""
    y = frame[outcome].to_numpy(dtype=float); a = frame.treatment.to_numpy(dtype=int)
    nt = int(a.sum()); nc = len(a) - nt
    if min(nt, nc) <= 0 or not np.isfinite(y).all():
        raise ValueError("Both arms and finite outcomes are required.")
    observed = float(y[a == 1].mean() - y[a == 0].mean())
    total = float(y.sum()); rng = np.random.default_rng(seed); extreme = 0
    for _ in range(reps):
        selected = rng.choice(len(y), size=nt, replace=False)
        sum_t = float(y[selected].sum())
        stat = sum_t / nt - (total - sum_t) / nc
        extreme += abs(stat) >= abs(observed) - 1e-12
    p = (extreme + 1) / (reps + 1)
    return {"p_value": float(p), "extreme_draws": int(extreme), "reps": reps,
            "seed": seed, "monte_carlo_se": float(np.sqrt(p * (1 - p) / reps)),
            "method": "two-sided fixed-count Monte Carlo randomization test; plus-one correction"}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values, returned in the original key order."""
    if not p_values or any(not np.isfinite(p) or p < 0 or p > 1 for p in p_values.values()):
        raise ValueError("Holm adjustment requires finite p-values in [0, 1].")
    ordered = sorted(p_values, key=p_values.get)
    m = len(ordered); adjusted: dict[str, float] = {}; running = 0.0
    for rank, key in enumerate(ordered):
        running = max(running, (m - rank) * p_values[key])
        adjusted[key] = float(min(1.0, running))
    return {key: adjusted[key] for key in p_values}


def expected_random_policy_value(ate: float, ci_low: float, ci_high: float,
                                 budget: float = POLICY_BUDGET) -> dict:
    """Scale a risk-difference estimate and interval to expected random targeting."""
    if not 0 <= budget <= 1 or ci_low > ci_high:
        raise ValueError("Invalid budget or interval.")
    scale = budget * 1000
    return {"budget": budget, "increment_per_1000": float(ate * scale),
            "ci95_low_per_1000": float(ci_low * scale),
            "ci95_high_per_1000": float(ci_high * scale),
            "treat_none_increment_per_1000": 0.0,
            "definition": "budget × randomized test ATE"}


def paired_policy_value_bootstrap(candidate_contributions: np.ndarray,
                                  reference_contributions: np.ndarray,
                                  reps: int = 5000, seed: int = SEED) -> dict:
    """Generic paired row bootstrap of policy-value influence contributions."""
    candidate = np.asarray(candidate_contributions, dtype=float)
    reference = np.asarray(reference_contributions, dtype=float)
    if candidate.shape != reference.shape or candidate.ndim != 1 or not len(candidate):
        raise ValueError("Paired policy contributions must be aligned one-dimensional arrays.")
    differences = candidate - reference; n = len(differences)
    rng = np.random.default_rng(seed); draws = np.empty(reps)
    for i in range(reps):
        draws[i] = differences[rng.integers(0, n, size=n)].mean()
    return {"difference": float(differences.mean()),
            "ci95_low": float(np.quantile(draws, .025)),
            "ci95_high": float(np.quantile(draws, .975)),
            "reps": reps, "seed": seed}


def load_locked_test(data_path: Path = DEFAULT_DATA,
                     split_path: Path = SPLIT_PATH) -> tuple[pd.DataFrame, dict]:
    """Validate frozen provenance, then parse only rows/outcomes in the test split."""
    if sha256(data_path) != DATA_SHA256 or sha256(split_path) != SPLIT_SHA256:
        raise ValueError("Hillstrom source or frozen split checksum mismatch.")
    split = pd.read_csv(split_path)
    if len(split) != 64_000:
        raise ValueError("Unexpected frozen split shape or schema.")
    test_ids = frozen_test_row_indices(split)
    if len(test_ids) != 12_800:
        raise ValueError("Expected the frozen 12,800-row test split.")
    test_set = set(test_ids.tolist())
    rows = pd.read_csv(data_path, usecols=["segment", "visit", "conversion", "spend"],
        skiprows=lambda line: line > 0 and (line - 1) not in test_set)
    if len(rows) != len(test_ids):
        raise ValueError("Test row parsing did not match frozen membership.")
    rows.insert(0, "row_index", np.sort(test_ids))
    if set(rows.segment.unique()) != set(ARMS):
        raise ValueError("Unexpected treatment arms in locked test rows.")
    if not rows.visit.isin([0, 1]).all() or not rows.conversion.isin([0, 1]).all():
        raise ValueError("Invalid binary outcome in locked test rows.")
    if not np.isfinite(rows.spend).all() or (rows.spend < 0).any():
        raise ValueError("Invalid spend value in locked test rows.")
    if not rows.spend.gt(0).eq(rows.conversion.eq(1)).all():
        raise ValueError("Spend/conversion outcome definition mismatch.")
    arm_counts = rows.segment.value_counts().reindex(ARMS).astype(int).to_dict()
    meta = {"source_sha256": DATA_SHA256, "split_sha256": SPLIT_SHA256,
            "test_rows_parsed": len(rows), "test_arm_counts": arm_counts,
            "test_outcomes_accessed": True}
    return rows, meta


def _contrast_name(treated: str, control: str, outcome: str) -> str:
    return f"{treated} vs {control} | {outcome}"


def evaluate_test(frame: pd.DataFrame, metadata: dict,
                  spend_bootstrap_reps: int = SPEND_BOOTSTRAP_REPS,
                  spend_permutation_reps: int = SPEND_PERMUTATION_REPS) -> dict:
    """Compute frozen primary ATE, eight Holm-adjusted secondary tests and policy value."""
    pair = map_contrast(frame, *PRIMARY_CONTRAST)
    primary = binary_risk_difference(pair, "visit")
    primary["realized_propensity"] = float(pair.treatment.mean())
    policy = expected_random_policy_value(primary["risk_difference"],
        primary["ci95_low"], primary["ci95_high"])

    secondary = []; raw_p: dict[str, float] = {}
    comparisons = []
    for treated, control in SECONDARY_CONTRASTS:
        for outcome in OUTCOMES:
            if (treated, control, outcome) == (*PRIMARY_CONTRAST, "visit"):
                continue
            name = _contrast_name(treated, control, outcome)
            block = map_contrast(frame, treated, control)
            if outcome in ("visit", "conversion"):
                stat = binary_risk_difference(block, outcome)
                item = {"contrast": f"{treated} vs {control}", "outcome": outcome,
                        **stat, "uncertainty_method": stat["ci_method"],
                        "p_value_unadjusted": stat["exact_two_sided_randomization_p"]}
                raw_p[name] = item["p_value_unadjusted"]
            else:
                stat = mean_difference(block, outcome)
                boot_seed = SEED + len(secondary)
                perm_seed = SEED + 100 + len(secondary)
                ci = stratified_bootstrap_mean_difference(block, outcome,
                    reps=spend_bootstrap_reps, seed=boot_seed)
                test = randomization_test_mean_difference(block, outcome,
                    reps=spend_permutation_reps, seed=perm_seed)
                item = {"contrast": f"{treated} vs {control}", "outcome": outcome,
                        **stat, "ci95_low": ci["ci95_low"], "ci95_high": ci["ci95_high"],
                        "uncertainty_method": ci["method"],
                        "p_value_unadjusted": test["p_value"],
                        "randomization_test": test}
                raw_p[name] = test["p_value"]
            comparisons.append(name); secondary.append(item)
    adjusted = holm_adjust(raw_p)
    for item, key in zip(secondary, comparisons):
        item["holm_adjusted_p"] = adjusted[key]
    return {"primary": primary, "secondary": secondary,
            "secondary_holm_family_size": len(secondary),
            "expected_random_policy_20pct": policy,
            "metadata": {**metadata, "model_fit_calls": 0,
                         "model_selection_performed": False,
                         "candidate_diagnostics_run": False}}


def run(data_path: Path = DEFAULT_DATA, split_path: Path = SPLIT_PATH,
        output_dir: Path = OUTPUT_PATH, spend_bootstrap_reps: int = SPEND_BOOTSTRAP_REPS,
        spend_permutation_reps: int = SPEND_PERMUTATION_REPS) -> dict:
    start = time.perf_counter()
    if ROOT == output_dir.resolve() or ROOT in output_dir.resolve().parents:
        raise ValueError("Private test outcomes must be stored outside the repository.")
    rows, metadata = load_locked_test(data_path, split_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    private_path = output_dir / "hillstrom_test_rows_private.parquet"
    rows.to_parquet(private_path, index=False)
    result = evaluate_test(rows, metadata, spend_bootstrap_reps, spend_permutation_reps)
    result["experiment"] = "COMMERCIAL_DS_P3_008C"
    result["protocol"] = {"primary_contrast": list(PRIMARY_CONTRAST),
        "primary_outcome": "visit", "outcome_window": "original two weeks",
        "primary_ci": "Newcombe hybrid score with uncorrected Wilson limits",
        "primary_test": "exact conditional randomization; absolute risk difference",
        "secondary_holm_tests": 8, "selected_policy": "constant_ate",
        "policy_budget": POLICY_BUDGET,
        "candidate_model_test_diagnostics": "not run; optional and no frozen model objects available",
        "model_selection_performed": False, "model_fit_calls": 0,
        "spend_bootstrap_reps": spend_bootstrap_reps,
        "spend_randomization_reps": spend_permutation_reps,
        "seed": SEED}
    result["runtime_seconds"] = time.perf_counter() - start
    result["private_test_rows_sha256"] = sha256(private_path)
    (output_dir / "hillstrom_locked_test_aggregate_private.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--split", type=Path, default=SPLIT_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--spend-bootstrap-reps", type=int, default=SPEND_BOOTSTRAP_REPS)
    parser.add_argument("--spend-permutation-reps", type=int, default=SPEND_PERMUTATION_REPS)
    args = parser.parse_args()
    result = run(args.data, args.split, args.output_dir,
                 args.spend_bootstrap_reps, args.spend_permutation_reps)
    print(json.dumps({"primary": result["primary"],
                      "secondary": result["secondary"],
                      "expected_random_policy_20pct": result["expected_random_policy_20pct"],
                      "runtime_seconds": result["runtime_seconds"]}, indent=2))


if __name__ == "__main__":
    main()

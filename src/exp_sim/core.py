from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from math import sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

Z975 = NormalDist().inv_cdf(0.975)
_NORMAL = NormalDist()
PRIVATE_PATH_MARKERS = ("b2b3-outcome-output", "INSIGHT-004", "data/raw", "data/processed")
ANALYST_RECORD_COLUMNS = (
    "customer_id", "assignment", "eligible_day21", "optout_pre_day21", "sent", "delivered", "engaged",
    "outcome_90", "resolved_90", "same_day_ambiguous", "first_order_status_error",
    "first_order_later_cancelled", "intervention_cost", "complaint", "optout_post_randomization",
    "margin_90", "margin_180", "margin_resolved_90", "margin_resolved_180", "ascertainment_rule",
)
FORBIDDEN_ANALYST_COLUMNS = {"resolution_scenario", "true_itt_rd", "true_outcome_90", "true_repeat_180", "potential_control", "potential_treatment", "hidden_outcome"}


@dataclass(frozen=True)
class ExperimentConfig:
    n_customers: int = 4000
    seed: int = 20261109
    allocation_treatment: float = 0.5
    p_early_repeat: float = 0.20
    p_late_repeat: float = 0.18
    p_optout_pre_day21: float = 0.05
    p_operationally_contactable: float = 0.95
    eligible_effect: float = 0.04
    outcome_missingness: str = "complete"  # complete, balanced_random, differential, outcome_dependent
    missing_rate_control: float = 0.01
    missing_rate_treatment: float = 0.01
    missing_effect_if_repeat: float = 0.20
    p_complaint_control: float = 0.003
    complaint_effect: float = 0.0  # conditional absolute risk effect among delivered customers
    p_optout_control: float = 0.02
    optout_effect: float = 0.0  # conditional absolute risk effect among delivered customers
    p_delivery: float = 0.96
    guardrail_latent_correlation: float = 0.0
    contribution_per_repeat: float = 12.0
    intervention_cost_per_sent: float = 0.35
    p_repeat_180_control: float = 0.30
    effect_180_eligible: float = 0.01
    margin_noise_sd: float = 8.0
    margin_missing_rate: float = 0.0
    margin_resolution_follows_outcome: bool = False
    same_day_ambiguous_rate: float = 0.0
    p_first_order_status_error: float = 0.0
    p_first_order_later_cancelled: float = 0.0

    def validate(self) -> None:
        if self.n_customers < 2:
            raise ValueError("n_customers must be at least 2")
        if not 0 < self.allocation_treatment < 1:
            raise ValueError("allocation_treatment must be strictly between 0 and 1")
        if not 1 <= round(self.n_customers * self.allocation_treatment) < self.n_customers:
            raise ValueError("allocation must place at least one synthetic customer in each arm")
        for name in (
            "allocation_treatment", "p_early_repeat", "p_late_repeat", "p_optout_pre_day21",
            "p_operationally_contactable", "p_complaint_control", "p_optout_control",
            "p_repeat_180_control", "p_delivery", "missing_rate_control", "missing_rate_treatment",
            "margin_missing_rate", "same_day_ambiguous_rate", "p_first_order_status_error",
            "p_first_order_later_cancelled",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if not -1 <= self.guardrail_latent_correlation <= 1:
            raise ValueError("guardrail_latent_correlation must be in [-1, 1]")
        if not -1 <= self.eligible_effect <= 1 or not 0 <= self.p_late_repeat + self.eligible_effect <= 1:
            raise ValueError("p_late_repeat + eligible_effect must be in [0, 1]")
        if not 0 <= self.p_complaint_control + self.complaint_effect <= 1:
            raise ValueError("complaint risk among delivered customers must be in [0, 1]")
        if not 0 <= self.p_optout_control + self.optout_effect <= 1:
            raise ValueError("opt-out risk among delivered customers must be in [0, 1]")
        if not 0 <= self.p_repeat_180_control + self.effect_180_eligible <= 1:
            raise ValueError("p_repeat_180_control + effect_180_eligible must be in [0, 1]")
        if self.p_repeat_180_control < self.p_late_repeat or self.p_repeat_180_control + self.effect_180_eligible < self.p_late_repeat + self.eligible_effect:
            raise ValueError("180-day repeat probabilities must contain the 90-day probabilities")
        if self.outcome_missingness not in {"complete", "balanced_random", "differential", "outcome_dependent"}:
            raise ValueError("Unknown outcome_missingness scenario")
        if self.outcome_missingness == "outcome_dependent" and not self.margin_resolution_follows_outcome:
            raise ValueError("Outcome-dependent missingness requires margin_resolution_follows_outcome=True to prevent financial leakage")
        if self.margin_noise_sd < 0 or self.contribution_per_repeat < 0 or self.intervention_cost_per_sent < 0:
            raise ValueError("Margin and cost inputs must be non-negative")


@dataclass(frozen=True)
class SensitivityRange:
    lower: float
    upper: float
    approved_before_unblinding: bool
    label: str = ""

    def validate(self) -> None:
        if self.lower > self.upper or self.lower < -1 or self.upper > 1:
            raise ValueError("Sensitivity range must satisfy -1 <= lower <= upper <= 1")


@dataclass(frozen=True)
class DecisionConfig:
    min_outcome_completeness: float = 0.98
    max_differential_missingness: float = 0.01
    complaint_margin: float = 0.002
    optout_margin: float = 0.005
    min_margin_completeness: float = 0.98
    max_differential_margin_missingness: float = 0.01
    min_margin_per_customer: float = 0.50
    min_margin_lower_bound: float = -0.25
    min_margin_180_point: float = 0.0
    min_margin_180_lower: float = -0.25


@dataclass(frozen=True)
class SimulatorTruth:
    """Private evaluation truth. Never pass this object to analysis or decisions."""
    missingness_mechanism: str
    config: ExperimentConfig
    population_itt_rd: float
    finite_population_sate: float
    sample_eligible_fraction: float
    potential_control_90: np.ndarray
    potential_treatment_90: np.ndarray
    realized_outcome_90: np.ndarray
    resolution_mask: np.ndarray
    margin_90_truth: np.ndarray
    margin_180_truth: np.ndarray
    margin_capture_90: np.ndarray
    margin_capture_180: np.ndarray
    potential_margin_control_90: np.ndarray
    potential_margin_treatment_90: np.ndarray
    population_itt_margin_90: float
    finite_population_sate_margin_90: float


@dataclass(frozen=True)
class SyntheticTrial:
    """Separate analyst-visible records from simulator-private truth and RNG streams."""
    records: pd.DataFrame
    truth: SimulatorTruth
    bootstrap_seed_sequence: np.random.SeedSequence
    replicate_seed_sequence: np.random.SeedSequence


def _thresholds(probabilities: np.ndarray) -> np.ndarray:
    eps = np.finfo(float).eps
    return np.fromiter((_NORMAL.inv_cdf(float(np.clip(p, eps, 1 - eps))) for p in probabilities), dtype=float, count=len(probabilities))


def _clone_seed_sequence(seed_sequence: np.random.SeedSequence) -> np.random.SeedSequence:
    """Create a reusable immutable specification, ignoring a caller's spawn counter."""
    return np.random.SeedSequence(seed_sequence.entropy, spawn_key=seed_sequence.spawn_key,
                                  pool_size=seed_sequence.pool_size)


def generate_trial(
    config: ExperimentConfig,
    *,
    seed_sequence: np.random.SeedSequence | None = None,
) -> SyntheticTrial:
    """Generate artificial analyst records and a separate private truth object."""
    config.validate()
    root = _clone_seed_sequence(seed_sequence) if seed_sequence is not None else np.random.SeedSequence(config.seed)
    streams = root.spawn(9)
    rng_assignment, rng_eligibility, rng_outcome, rng_delivery, rng_guardrail, rng_resolution, rng_admin, rng_margin = [np.random.default_rng(s) for s in streams[:8]]
    n = config.n_customers
    n_treatment = round(n * config.allocation_treatment)
    treatment = np.zeros(n, dtype=bool)
    treatment[rng_assignment.permutation(n)[:n_treatment]] = True
    customer_id = np.array([f"SYN-{config.seed}-{i:07d}" for i in range(n)], dtype=object)

    # Pre-divergence eligibility inputs are generated independently of assignment.
    early = rng_eligibility.random(n) < config.p_early_repeat
    optout_pre = rng_eligibility.random(n) < config.p_optout_pre_day21
    contactable = rng_eligibility.random(n) < config.p_operationally_contactable
    eligible = (~early) & (~optout_pre) & contactable
    pi_sample = float(eligible.mean())
    pi_population = (1 - config.p_early_repeat) * (1 - config.p_optout_pre_day21) * config.p_operationally_contactable

    late_u = rng_outcome.random(n)
    p_c = config.p_late_repeat
    p_t = p_c + config.eligible_effect
    y0 = early | (late_u < p_c)
    y1_late = early | (late_u < p_t)
    potential_t = np.where(eligible, y1_late, y0)
    potential_c = y0
    outcome = np.where(treatment, potential_t, potential_c)
    sate = float(np.mean(potential_t.astype(float) - potential_c.astype(float)))

    sent = treatment & eligible
    delivered = sent & (rng_delivery.random(n) < config.p_delivery)
    engaged = delivered & (rng_delivery.random(n) < 0.30)

    # Gaussian-copula correlation is configurable; marginals are the stated event risks.
    z_complaint = rng_guardrail.standard_normal(n)
    z_independent = rng_guardrail.standard_normal(n)
    rho = config.guardrail_latent_correlation
    z_optout = rho * z_complaint + sqrt(max(0.0, 1 - rho * rho)) * z_independent
    complaint_risk = np.clip(config.p_complaint_control + delivered * config.complaint_effect, 0, 1)
    optout_risk = np.clip(config.p_optout_control + delivered * config.optout_effect, 0, 1)
    complaint = z_complaint < _thresholds(complaint_risk)
    optout_post = z_optout < _thresholds(optout_risk)

    p180_c = config.p_repeat_180_control
    p180_t = p180_c + config.effect_180_eligible
    repeat180_c = early | (late_u < p180_c)
    repeat180_t = np.where(eligible, early | (late_u < p180_t), repeat180_c)
    repeat180 = np.where(treatment, repeat180_t, repeat180_c)

    if config.outcome_missingness == "complete":
        resolved = np.ones(n, dtype=bool)
    elif config.outcome_missingness == "balanced_random":
        resolved = rng_resolution.random(n) >= config.missing_rate_control
    elif config.outcome_missingness == "differential":
        miss_prob = np.where(treatment, config.missing_rate_treatment, config.missing_rate_control)
        resolved = rng_resolution.random(n) >= miss_prob
    else:
        base_miss = np.where(treatment, config.missing_rate_treatment, config.missing_rate_control)
        risk_factor = np.where(outcome, 1.0 + config.missing_effect_if_repeat, 1.0)
        miss_prob = np.clip(base_miss * risk_factor, 0, 1)
        resolved = rng_resolution.random(n) >= miss_prob

    ambiguous_same_day = rng_admin.random(n) < config.same_day_ambiguous_rate
    status_error = rng_admin.random(n) < config.p_first_order_status_error
    later_cancel = rng_admin.random(n) < config.p_first_order_later_cancelled
    margin_noise = rng_margin.normal(0, config.margin_noise_sd, n)
    intervention_cost = sent.astype(float) * config.intervention_cost_per_sent
    margin90 = outcome * config.contribution_per_repeat - intervention_cost + margin_noise
    margin180 = repeat180 * config.contribution_per_repeat - intervention_cost + margin_noise
    margin90_control = potential_c.astype(float) * config.contribution_per_repeat + margin_noise
    margin90_treatment = potential_t.astype(float) * config.contribution_per_repeat - eligible.astype(float) * config.intervention_cost_per_sent + margin_noise
    margin_capture90 = rng_margin.random(n) >= config.margin_missing_rate
    margin_capture180 = rng_margin.random(n) >= config.margin_missing_rate
    # Apply one common purchase-resolution policy to both arms. When enabled,
    # purchase-linked financial outcomes remain unavailable if the 90-day
    # purchase outcome is unresolved; simulator-private truth is retained below.
    margin_resolved90 = margin_capture90 & (resolved if config.margin_resolution_follows_outcome else True)
    margin_resolved180 = margin_capture180 & (resolved if config.margin_resolution_follows_outcome else True)

    records = pd.DataFrame({
        "customer_id": customer_id,
        "assignment": np.where(treatment, "treatment", "control"),
        "eligible_day21": eligible,
        "optout_pre_day21": optout_pre,
        "sent": sent,
        "delivered": delivered,
        "engaged": engaged,
        "outcome_90": np.where(resolved, outcome.astype(float), np.nan),
        "resolved_90": resolved,
        "same_day_ambiguous": ambiguous_same_day,
        "first_order_status_error": status_error,
        "first_order_later_cancelled": later_cancel,
        "intervention_cost": intervention_cost,
        "complaint": complaint,
        "optout_post_randomization": optout_post,
        "margin_90": np.where(margin_resolved90, margin90, np.nan),
        "margin_180": np.where(margin_resolved180, margin180, np.nan),
        "margin_resolved_90": margin_resolved90,
        "margin_resolved_180": margin_resolved180,
        "ascertainment_rule": "common_synthetic_capture_v1",
    })
    records = records.loc[:, ANALYST_RECORD_COLUMNS]
    truth = SimulatorTruth(
        missingness_mechanism=config.outcome_missingness,
        config=config,
        population_itt_rd=float(pi_population * config.eligible_effect),
        finite_population_sate=sate,
        sample_eligible_fraction=pi_sample,
        potential_control_90=potential_c,
        potential_treatment_90=potential_t,
        realized_outcome_90=outcome,
        resolution_mask=resolved,
        margin_90_truth=margin90,
        margin_180_truth=margin180,
        margin_capture_90=margin_capture90,
        margin_capture_180=margin_capture180,
        potential_margin_control_90=margin90_control,
        potential_margin_treatment_90=margin90_treatment,
        population_itt_margin_90=float(pi_population * (config.eligible_effect * config.contribution_per_repeat - config.intervention_cost_per_sent)),
        finite_population_sate_margin_90=float(np.mean(margin90_treatment - margin90_control)),
    )
    return SyntheticTrial(records=records, truth=truth, bootstrap_seed_sequence=streams[8], replicate_seed_sequence=root)


def wilson_interval(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * sqrt((p * (1 - p) / n) + (z * z / (4 * n * n))) / den
    return max(0.0, center - half), min(1.0, center + half)


def newcombe_interval(x_t: int, n_t: int, x_c: int, n_c: int, alpha: float = 0.05) -> tuple[float, float, float]:
    """Newcombe hybrid-score interval for treatment-minus-control risk difference."""
    if n_t <= 0 or n_c <= 0 or not (0 <= x_t <= n_t and 0 <= x_c <= n_c):
        raise ValueError("Counts must be valid and both arms must have observations")
    pt, pc = x_t / n_t, x_c / n_c
    lt, ut = wilson_interval(x_t, n_t, alpha)
    lc, uc = wilson_interval(x_c, n_c, alpha)
    rd = pt - pc
    lower = rd - sqrt((pt - lt) ** 2 + (uc - pc) ** 2)
    upper = rd + sqrt((ut - pt) ** 2 + (pc - lc) ** 2)
    return rd, max(-1.0, lower), min(1.0, upper)


def _risk_interval_by_newcombe(frame: pd.DataFrame, col: str) -> dict[str, float]:
    arms = {a: frame.loc[frame.assignment == a, col].astype(bool) for a in ("treatment", "control")}
    rd, lower, upper = newcombe_interval(int(arms["treatment"].sum()), len(arms["treatment"]), int(arms["control"].sum()), len(arms["control"]))
    return {"rd": float(rd), "lower_95": lower, "upper_95": upper}


def analyze_trial(
    frame: pd.DataFrame,
    *,
    sensitivity_range: SensitivityRange | None,
    decision_config: DecisionConfig = DecisionConfig(),
    margin_bootstrap_reps: int = 10000,
    missingness_assumptions_approved: bool = False,
    bootstrap_seed_sequence: np.random.SeedSequence | None = None,
) -> dict[str, Any]:
    """Analyze analyst-visible rows only; simulator truth is a separate object."""
    missing_cols = set(ANALYST_RECORD_COLUMNS).difference(frame.columns)
    extra_cols = set(frame.columns).difference(ANALYST_RECORD_COLUMNS)
    if missing_cols or extra_cols:
        raise ValueError(f"Analyst record schema mismatch; missing={sorted(missing_cols)}, extra={sorted(extra_cols)}")
    if frame.customer_id.duplicated().any():
        raise ValueError("Expected one row per synthetic randomized customer")
    if not set(frame.assignment.unique()).issubset({"control", "treatment"}):
        raise ValueError("Invalid assignment value")
    if frame.ascertainment_rule.nunique() != 1:
        raise ValueError("Outcome ascertainment rule must be identical across randomized arms")
    if frame.assignment.nunique() != 2:
        raise ValueError("Both randomized arms must be represented")
    for value_col, resolved_col in (("outcome_90", "resolved_90"), ("margin_90", "margin_resolved_90"), ("margin_180", "margin_resolved_180")):
        observed_mask = frame[value_col].notna().to_numpy()
        status_mask = frame[resolved_col].astype(bool).to_numpy()
        if not np.array_equal(observed_mask, status_mask):
            raise ValueError(f"{value_col} values must agree with {resolved_col}")
    if margin_bootstrap_reps < 1:
        raise ValueError("margin_bootstrap_reps must be positive")

    analysis: dict[str, Any] = {}
    arm_stats = {}
    for arm in ("control", "treatment"):
        g = frame.loc[frame.assignment == arm]
        observed = g.loc[g.resolved_90.astype(bool), "outcome_90"].astype(bool)
        arm_stats[arm] = {"n_randomized": int(len(g)), "n_resolved": int(len(observed)), "n_events": int(observed.sum()), "risk_resolved": float(observed.mean()) if len(observed) else None}
    can_estimate = all(arm_stats[a]["n_resolved"] > 0 for a in ("treatment", "control"))
    degenerate = can_estimate and all(arm_stats[a]["n_events"] in (0, arm_stats[a]["n_resolved"]) for a in ("treatment", "control"))
    if can_estimate:
        rd, lo, hi = newcombe_interval(arm_stats["treatment"]["n_events"], arm_stats["treatment"]["n_resolved"], arm_stats["control"]["n_events"], arm_stats["control"]["n_resolved"])
        test_status = "REJECT" if lo > 0 or hi < 0 else "DO NOT REJECT"
        stat_status = "INCONCLUSIVE" if degenerate or (hi - lo) <= 1e-15 else ("PASS" if lo > 0 else ("FAIL" if hi < 0 else "INCONCLUSIVE"))
        ci = [lo, hi]
    else:
        rd, lo, hi, test_status, stat_status, ci = None, None, None, "INCONCLUSIVE", "INCONCLUSIVE", [None, None]
    analysis["primary"] = {"method": "newcombe_hybrid_score_resolved_itt", "estimand": "all_randomized_itt_rd", "rd_resolved": rd, "ci95": ci, "hypothesis_test_status": test_status, "statistical_status": stat_status, "degenerate": bool(degenerate), "arms": arm_stats}

    missing = {}
    for arm in ("control", "treatment"):
        g = frame.loc[frame.assignment == arm]
        missing[arm] = 1.0 - float(g.resolved_90.astype(bool).mean())
    completeness = 1.0 - float((~frame.resolved_90.astype(bool)).mean())
    miss_diff = abs(missing["treatment"] - missing["control"])
    diagnostics_pass = completeness >= decision_config.min_outcome_completeness and miss_diff <= decision_config.max_differential_missingness
    analysis["ascertainment"] = {"completeness": completeness, "missing_fraction_by_arm": missing, "absolute_missingness_difference": miss_diff, "thresholds_pass": bool(diagnostics_pass), "same_day_ambiguous_count": int(frame.same_day_ambiguous.sum()), "same_day_rule": "ambiguous split orders are non-events; two-way sensitivity only"}

    worst_t = arm_stats["treatment"]["n_events"] / arm_stats["treatment"]["n_randomized"]
    worst_c = (arm_stats["control"]["n_events"] + arm_stats["control"]["n_randomized"] - arm_stats["control"]["n_resolved"]) / arm_stats["control"]["n_randomized"]
    best_t = (arm_stats["treatment"]["n_events"] + arm_stats["treatment"]["n_randomized"] - arm_stats["treatment"]["n_resolved"]) / arm_stats["treatment"]["n_randomized"]
    best_c = arm_stats["control"]["n_events"] / arm_stats["control"]["n_randomized"]
    analysis["extreme_bounds_descriptive_only"] = {"adverse_rd": worst_t - worst_c, "opposite_best_rd": best_t - best_c}

    if sensitivity_range is None or not sensitivity_range.approved_before_unblinding:
        analysis["sensitivity"] = {"status": "INCONCLUSIVE / NOT AUTHORISED", "reason": "No plausible-departure range approved before simulated unblinding"}
    elif not can_estimate:
        analysis["sensitivity"] = {"status": "QUALIFIED / INCONCLUSIVE", "reason": "At least one randomized arm has no resolved outcomes"}
    else:
        sensitivity_range.validate()
        analysis["sensitivity"] = _tipping_sensitivity(frame, sensitivity_range)

    eligibility = frame.eligible_day21.astype(bool).to_numpy()
    elig_stats = {}
    for arm in ("control", "treatment"):
        m = (frame.assignment.to_numpy() == arm) & eligibility & frame.resolved_90.astype(bool).to_numpy()
        vals = frame.loc[m, "outcome_90"].astype(bool)
        elig_stats[arm] = {"n_resolved": int(len(vals)), "risk": float(vals.mean()) if len(vals) else float("nan"), "n_events": int(vals.sum())}
    if min(elig_stats[a]["n_resolved"] for a in elig_stats) > 0:
        erd, elo, ehi = newcombe_interval(elig_stats["treatment"]["n_events"], elig_stats["treatment"]["n_resolved"], elig_stats["control"]["n_events"], elig_stats["control"]["n_resolved"])
    else:
        erd = elo = ehi = float("nan")
    analysis["day21_eligible_secondary"] = {"rd": erd, "ci95": [elo, ehi], "arms": elig_stats, "causal_only_if_pre_divergence_parity_verified": True}

    analysis["guardrails"] = {"complaint": _risk_interval_by_newcombe(frame, "complaint"), "optout": _risk_interval_by_newcombe(frame, "optout_post_randomization")}
    resolved_mask = frame.resolved_90.astype(bool).to_numpy()
    observed_outcomes = frame.outcome_90.fillna(0).astype(bool).to_numpy()
    alternate = observed_outcomes | frame.same_day_ambiguous.astype(bool).to_numpy()
    same_day_sens = {}
    for arm in ("control", "treatment"):
        mask = (frame.assignment.to_numpy() == arm) & resolved_mask
        same_day_sens[arm] = float(alternate[mask].mean()) if mask.any() else float("nan")
    analysis["same_day_sensitivity"] = {"primary_ambiguous_candidates_counted_as_non_events": True, "alternate_if_all_ambiguous_candidates_counted": same_day_sens["treatment"] - same_day_sens["control"]}

    status_error_sensitivity = {}
    for arm in ("control", "treatment"):
        mask = (frame.assignment.to_numpy() == arm) & resolved_mask & ~frame.first_order_status_error.astype(bool).to_numpy()
        vals = frame.loc[mask, "outcome_90"].astype(bool)
        status_error_sensitivity[arm] = {"n": int(len(vals)), "events": int(vals.sum()), "risk": float(vals.mean()) if len(vals) else None}
    if all(status_error_sensitivity[a]["n"] for a in status_error_sensitivity):
        _, status_lo, status_hi = newcombe_interval(status_error_sensitivity["treatment"]["events"], status_error_sensitivity["treatment"]["n"], status_error_sensitivity["control"]["events"], status_error_sensitivity["control"]["n"])
        status_rd = status_error_sensitivity["treatment"]["risk"] - status_error_sensitivity["control"]["risk"]
    else:
        status_rd, status_lo, status_hi = None, None, None
    analysis["status_error_sensitivity_only"] = {"arms": status_error_sensitivity, "rd": status_rd, "ci95": [status_lo, status_hi]}

    bootstrap_seq = bootstrap_seed_sequence or _seed_sequence_from_records(frame)
    analysis["commercial"] = _margin_summary(frame, bootstrap_reps=margin_bootstrap_reps, bootstrap_seed_sequence=bootstrap_seq)
    # Only caller approval plus observable diagnostics can authorize the missingness assumption gate.
    analysis["missingness_assumptions"] = {"reviewed_assumption_approved": bool(missingness_assumptions_approved), "observable_diagnostics_pass": bool(diagnostics_pass), "assumptions_pass": bool(missingness_assumptions_approved and diagnostics_pass)}
    analysis["diagnostics_pass"] = bool(diagnostics_pass)
    analysis["sate_estimate"] = None  # Simulator-private SATE is held only in SimulatorTruth.
    return analysis


def _seed_sequence_from_records(frame: pd.DataFrame) -> np.random.SeedSequence:
    visible = pd.util.hash_pandas_object(frame, index=False).to_numpy(dtype=np.uint64).tobytes()
    digest = hashlib.sha256(visible).digest()
    return np.random.SeedSequence(int.from_bytes(digest[:16], "little"))


def _tipping_sensitivity(frame: pd.DataFrame, bounds: SensitivityRange) -> dict[str, Any]:
    bounds.validate()
    arm = {}
    for name in ("control", "treatment"):
        g = frame.loc[frame.assignment == name]
        obs = g.loc[g.resolved_90.astype(bool), "outcome_90"].astype(float)
        miss_n = int((~g.resolved_90.astype(bool)).sum())
        arm[name] = {"N": len(g), "n_res": len(obs), "n_miss": miss_n, "p_obs": float(obs.mean()) if len(obs) else float("nan"), "r": len(obs) / len(g)}

    def scenario(dt: float, dc: float) -> dict[str, Any]:
        pt_obs, pc_obs = arm["treatment"]["p_obs"], arm["control"]["p_obs"]
        qt, qc = float(np.clip(pt_obs + dt, 0, 1)), float(np.clip(pc_obs + dc, 0, 1))
        pt_all = arm["treatment"]["r"] * pt_obs + (1 - arm["treatment"]["r"]) * qt
        pc_all = arm["control"]["r"] * pc_obs + (1 - arm["control"]["r"]) * qc
        rd = pt_all - pc_all
        vt = arm["treatment"]["r"] ** 2 * pt_obs * (1 - pt_obs) / max(1, arm["treatment"]["n_res"])
        vt += (1 - arm["treatment"]["r"]) ** 2 * qt * (1 - qt) / max(1, arm["treatment"]["n_miss"])
        vc = arm["control"]["r"] ** 2 * pc_obs * (1 - pc_obs) / max(1, arm["control"]["n_res"])
        vc += (1 - arm["control"]["r"]) ** 2 * qc * (1 - qc) / max(1, arm["control"]["n_miss"])
        half = Z975 * sqrt(max(0.0, vt + vc))
        return {"delta_t": float(dt), "delta_c": float(dc), "rd": float(rd), "ci95": [max(-1.0, rd - half), min(1.0, rd + half)]}

    grid = np.linspace(bounds.lower, bounds.upper, max(3, int(round((bounds.upper - bounds.lower) / 0.01)) + 1))
    scenarios = [scenario(float(dt), float(dc)) for dt in grid for dc in grid]
    point_tip = [x for x in scenarios if x["rd"] <= 0]
    ci_tip = [x for x in scenarios if x["ci95"][0] <= 0]
    robust = not point_tip and not ci_tip
    point_mag = min((max(abs(x["delta_t"]), abs(x["delta_c"])) for x in point_tip), default=None)
    interval_mag = min((max(abs(x["delta_t"]), abs(x["delta_c"])) for x in ci_tip), default=None)
    pt_obs, pc_obs = arm["treatment"]["p_obs"], arm["control"]["p_obs"]
    dmax = max(bounds.lower + pt_obs, (1 - pc_obs) - bounds.upper, 0.0)

    def outside_distance(predicate) -> float | None:
        if predicate(scenario(bounds.lower, bounds.upper)):
            return 0.0
        steps = 200
        for idx in range(1, steps + 1):
            distance = dmax * idx / steps
            dt = max(-pt_obs, bounds.lower - distance)
            dc = min(1 - pc_obs, bounds.upper + distance)
            if predicate(scenario(dt, dc)):
                return float(distance)
        return None

    point_outside = outside_distance(lambda x: x["rd"] <= 0) if not point_tip else 0.0
    interval_outside = outside_distance(lambda x: x["ci95"][0] <= 0) if not ci_tip else 0.0
    return {
        "status": "ROBUST" if robust else "QUALIFIED / INCONCLUSIVE",
        "range": [bounds.lower, bounds.upper], "range_label": bounds.label,
        "approved_before_unblinding": bounds.approved_before_unblinding,
        "scenarios_evaluated": len(scenarios), "point_tip_present": bool(point_tip),
        "interval_tip_present": bool(ci_tip), "min_rd_in_range": min(x["rd"] for x in scenarios),
        "min_lower_ci_in_range": min(x["ci95"][0] for x in scenarios),
        "max_upper_ci_in_range": max(x["ci95"][1] for x in scenarios),
        "smallest_point_tip_linf_magnitude_in_range": point_mag,
        "smallest_interval_tip_linf_magnitude_in_range": interval_mag,
        "point_tip_distance_outside_range_linf": point_outside,
        "interval_tip_distance_outside_range_linf": interval_outside,
        "outside_range_distance_search_steps": 200,
        "outside_range_distance_resolution_linf": dmax / 200,
    }


def _margin_summary(frame: pd.DataFrame, *, bootstrap_reps: int, bootstrap_seed_sequence: np.random.SeedSequence) -> dict[str, Any]:
    result: dict[str, Any] = {}
    # SeedSequence.spawn mutates its parent counter. Clone the immutable identity
    # so repeated analyses of the same visible trial remain reproducible.
    stable = np.random.SeedSequence(bootstrap_seed_sequence.entropy,
                                    spawn_key=bootstrap_seed_sequence.spawn_key,
                                    pool_size=bootstrap_seed_sequence.pool_size)
    rng90, rng180 = (np.random.default_rng(s) for s in stable.spawn(2))
    for horizon, col, resolved_col, rng in ((90, "margin_90", "margin_resolved_90", rng90), (180, "margin_180", "margin_resolved_180", rng180)):
        values = {}
        for arm in ("control", "treatment"):
            g = frame.loc[frame.assignment == arm, col].astype(float)
            values[arm] = {"n": len(g), "complete": int(g.notna().sum()), "mean": float(g.mean())}
        tvals = frame.loc[frame.assignment == "treatment", col].dropna().to_numpy(dtype=float)
        cvals = frame.loc[frame.assignment == "control", col].dropna().to_numpy(dtype=float)
        if len(tvals) and len(cvals):
            diffs = np.empty(bootstrap_reps, dtype=float)
            for b in range(bootstrap_reps):
                diffs[b] = rng.choice(tvals, len(tvals), replace=True).mean() - rng.choice(cvals, len(cvals), replace=True).mean()
            lower, upper = np.quantile(diffs, [0.025, 0.975])
        else:
            lower = upper = float("nan")
        resolved_rates = {arm: float(frame.loc[frame.assignment == arm, resolved_col].astype(bool).mean()) for arm in ("control", "treatment")}
        result[str(horizon)] = {
            "arms": values, "difference_t_minus_c": values["treatment"]["mean"] - values["control"]["mean"],
            "ci95_percentile_bootstrap": [float(lower), float(upper)], "bootstrap_replicates": bootstrap_reps,
            "completeness_by_arm": resolved_rates, "completeness": min(resolved_rates.values()),
            "absolute_missingness_difference": abs(resolved_rates["treatment"] - resolved_rates["control"]),
        }
    return result


def _guardrail_status(result: dict[str, float], margin: float) -> str:
    if result["upper_95"] < margin:
        return "PASS"
    if result["lower_95"] > 0 or result["rd"] >= margin:
        return "FAIL"
    return "INCONCLUSIVE"


def _margin_status(summary: dict[str, Any], *, config: DecisionConfig, horizon: str) -> str:
    if summary["completeness"] < config.min_margin_completeness or summary["absolute_missingness_difference"] > config.max_differential_margin_missingness:
        return "INCONCLUSIVE"
    lower = summary["ci95_percentile_bootstrap"][0]
    if horizon == "90":
        good = summary["difference_t_minus_c"] >= config.min_margin_per_customer and lower > config.min_margin_lower_bound
    else:
        good = summary["difference_t_minus_c"] >= config.min_margin_180_point and lower > config.min_margin_180_lower
    return "PASS" if good else "FAIL"


def decide_90_day(analysis: dict[str, Any], *, sensitivity_range: SensitivityRange | None, config: DecisionConfig = DecisionConfig()) -> dict[str, Any]:
    """Record the initial 90-day decision; it is never changed by 180-day follow-up."""
    if sensitivity_range is None or not sensitivity_range.approved_before_unblinding:
        return {"stage": "DAY_90", "status": "INCONCLUSIVE / NOT AUTHORISED", "gates": {"sensitivity_range": "INCONCLUSIVE"}, "holdout_required": True}
    primary = analysis["primary"]
    gates: dict[str, str] = {}
    # Reuse the analysis state so degeneracy can never be upgraded to PASS.
    gates["statistical_conversion"] = primary["statistical_status"]
    gates["ascertainment"] = "PASS" if analysis["diagnostics_pass"] else "INCONCLUSIVE"
    gates["missingness_assumptions"] = "PASS" if analysis["missingness_assumptions"]["assumptions_pass"] else "INCONCLUSIVE"
    gates["sensitivity_robustness"] = "PASS" if analysis["sensitivity"]["status"] == "ROBUST" else "INCONCLUSIVE"
    gates["complaint"] = _guardrail_status(analysis["guardrails"]["complaint"], config.complaint_margin)
    gates["optout"] = _guardrail_status(analysis["guardrails"]["optout"], config.optout_margin)
    m90 = analysis["commercial"]["90"]
    gates["margin_completeness_90"] = "PASS" if m90["completeness"] >= config.min_margin_completeness and m90["absolute_missingness_difference"] <= config.max_differential_margin_missingness else "INCONCLUSIVE"
    gates["margin_90"] = _margin_status(m90, config=config, horizon="90")
    if any(v == "FAIL" for v in gates.values()):
        status = "DO NOT ADOPT"
    elif any(v == "INCONCLUSIVE" for v in gates.values()):
        status = "INCONCLUSIVE"
    else:
        status = "PROVISIONAL ADOPT WITH HOLDOUT"
    return {"stage": "DAY_90", "status": status, "gates": gates, "holdout_required": status == "PROVISIONAL ADOPT WITH HOLDOUT", "recorded_before_180_day_readout": True}


def assess_180_day(analysis: dict[str, Any], decision_90: dict[str, Any], *, config: DecisionConfig = DecisionConfig()) -> dict[str, Any]:
    """Separate later confirmation/rollback; does not mutate or overwrite the day-90 decision."""
    if decision_90["status"] != "PROVISIONAL ADOPT WITH HOLDOUT":
        return {"stage": "DAY_180", "status": "NOT APPLICABLE", "action": "NO ROLLBACK TRIGGER", "day_90_status_unchanged": decision_90["status"]}
    m180 = analysis["commercial"]["180"]
    complete = m180["completeness"] >= config.min_margin_completeness and m180["absolute_missingness_difference"] <= config.max_differential_margin_missingness
    margin_status = _margin_status(m180, config=config, horizon="180")
    if not complete:
        status = "ROLLBACK"
        reason = "Incomplete or differential 180-day financial records"
    elif margin_status != "PASS":
        status = "ROLLBACK"
        reason = "180-day contribution-margin gate failed"
    else:
        status = "CONFIRM"
        reason = "180-day contribution-margin gate passed"
    return {"stage": "DAY_180", "status": status, "action": "STOP EXPANSION / ROLLBACK TO BAU" if status == "ROLLBACK" else "CONFIRM PROVISIONAL ADOPTION", "reason": reason, "day_90_status_unchanged": decision_90["status"]}


def decide_adoption(analysis: dict[str, Any], *, sensitivity_range: SensitivityRange | None, config: DecisionConfig = DecisionConfig()) -> dict[str, Any]:
    """Return explicitly separate 90-day and 180-day decisions."""
    day90 = decide_90_day(analysis, sensitivity_range=sensitivity_range, config=config)
    day180 = assess_180_day(analysis, day90, config=config)
    return {"day_90": day90, "day_180": day180, "status": day90["status"]}


def _probability_metric(flags: list[bool], *, denominator_mask: list[bool] | None = None) -> dict[str, Any]:
    mask = np.ones(len(flags), dtype=bool) if denominator_mask is None else np.asarray(denominator_mask, dtype=bool)
    values = np.asarray(flags, dtype=bool)[mask]
    denominator = int(mask.sum())
    numerator = int(values.sum())
    estimate = numerator / denominator if denominator else None
    mcse = sqrt(estimate * (1 - estimate) / denominator) if denominator else None
    ci = wilson_interval(numerator, denominator) if denominator else (None, None)
    return {"estimate": estimate, "mcse": mcse, "ci95_wilson": list(ci), "numerator": numerator, "denominator": denominator}


def _continuous_metric(values: list[float]) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(len(arr))
    mean = float(arr.mean()) if n else None
    se = float(arr.std(ddof=1) / sqrt(n)) if n > 1 else None
    return {"mean": mean, "mcse": se, "denominator": n}


def monte_carlo(
    base: ExperimentConfig,
    *,
    replicates: int = 250,
    seed: int = 33001,
    sensitivity_range: SensitivityRange | None = None,
    decision_config: DecisionConfig = DecisionConfig(),
    margin_bootstrap_reps: int = 1000,
    missingness_assumptions_approved: bool = True,
) -> dict[str, Any]:
    """Run serial, schedule-independent synthetic Monte Carlo with independent spawned streams."""
    if replicates < 1:
        raise ValueError("replicates must be positive")
    campaign_seed = np.random.SeedSequence(seed)
    replicate_sequences = campaign_seed.spawn(replicates)
    rows = []
    for replicate_sequence in replicate_sequences:
        trial = generate_trial(base, seed_sequence=replicate_sequence)
        analysis = analyze_trial(
            trial.records, sensitivity_range=sensitivity_range, decision_config=decision_config,
            margin_bootstrap_reps=margin_bootstrap_reps,
            missingness_assumptions_approved=missingness_assumptions_approved,
            bootstrap_seed_sequence=trial.bootstrap_seed_sequence,
        )
        decision = decide_adoption(analysis, sensitivity_range=sensitivity_range, config=decision_config)
        d90, d180 = decision["day_90"]["status"], decision["day_180"]["status"]
        primary_ci = analysis["primary"]["ci95"]
        primary_defined = primary_ci[0] is not None and primary_ci[1] is not None
        true_effect = trial.truth.finite_population_sate
        rows.append({
            "rd_est": analysis["primary"]["rd_resolved"], "lo": primary_ci[0], "hi": primary_ci[1],
            "truth": true_effect, "population_truth": trial.truth.population_itt_rd,
            "true_margin90_population": trial.truth.population_itt_margin_90,
            "true_margin90_sate": trial.truth.finite_population_sate_margin_90,
            "primary_defined": primary_defined,
            "primary_positive": bool(primary_defined and primary_ci[0] > 0),
            "primary_reject": bool(primary_defined and (primary_ci[0] > 0 or primary_ci[1] < 0)),
            "covers_truth": bool(primary_defined and primary_ci[0] <= true_effect <= primary_ci[1]),
            "complaint_state": decision["day_90"]["gates"].get("complaint", "INCONCLUSIVE"),
            "optout_state": decision["day_90"]["gates"].get("optout", "INCONCLUSIVE"),
            "sensitivity_state": analysis["sensitivity"]["status"],
            "day90_status": d90, "day180_status": d180,
            "day90_provisional": d90 == "PROVISIONAL ADOPT WITH HOLDOUT",
            "day180_confirm": d180 == "CONFIRM", "day180_rollback": d180 == "ROLLBACK",
            "joint_confirmed": d90 == "PROVISIONAL ADOPT WITH HOLDOUT" and d180 == "CONFIRM",
            "inconclusive_90": d90.startswith("INCONCLUSIVE"),
            "bias": None if analysis["primary"]["rd_resolved"] is None else analysis["primary"]["rd_resolved"] - true_effect,
            "margin_bootstrap_reps": margin_bootstrap_reps,
        })
    df = pd.DataFrame(rows)
    R = len(rows)
    metrics: dict[str, Any] = {
        "day90_provisional_adoption": _probability_metric(df.day90_provisional.tolist()),
        "day90_inconclusive": _probability_metric(df.inconclusive_90.tolist()),
        "day180_confirm_marginal": _probability_metric(df.day180_confirm.tolist()),
        "day180_rollback_marginal": _probability_metric(df.day180_rollback.tolist()),
        "joint_90_provisional_and_180_confirm": _probability_metric(df.joint_confirmed.tolist()),
        "day180_confirm_given_90_provisional": _probability_metric(df.day180_confirm.tolist(), denominator_mask=df.day90_provisional.tolist()),
        "day180_rollback_given_90_provisional": _probability_metric(df.day180_rollback.tolist(), denominator_mask=df.day90_provisional.tolist()),
        "complaint_guardrail_pass": _probability_metric((df.complaint_state == "PASS").tolist()),
        "complaint_guardrail_inconclusive": _probability_metric((df.complaint_state == "INCONCLUSIVE").tolist()),
        "optout_guardrail_pass": _probability_metric((df.optout_state == "PASS").tolist()),
        "optout_guardrail_inconclusive": _probability_metric((df.optout_state == "INCONCLUSIVE").tolist()),
        "sensitivity_robust": _probability_metric((df.sensitivity_state == "ROBUST").tolist()),
        "ci_coverage_conditional_on_defined": _probability_metric(df.covers_truth.tolist(), denominator_mask=df.primary_defined.tolist()),
    }
    null_config = abs(base.eligible_effect) < 1e-15
    metrics["type_i_error_unconditional"] = _probability_metric(df.primary_reject.tolist()) if null_config else {"estimate": None, "mcse": None, "ci95_wilson": [None, None], "numerator": 0, "denominator": 0}
    metrics["power_unconditional"] = _probability_metric(df.primary_positive.tolist())
    metrics["false_statistical_positive_when_population_itt_nonpositive"] = (
        _probability_metric(df.primary_positive.tolist()) if base.eligible_effect <= 0
        else {"estimate": None, "mcse": None, "ci95_wilson": [None, None], "numerator": 0, "denominator": 0}
    )
    metrics["false_provisional_adoption_when_population_itt_nonpositive"] = (
        _probability_metric(df.day90_provisional.tolist()) if base.eligible_effect <= 0
        else {"estimate": None, "mcse": None, "ci95_wilson": [None, None], "numerator": 0, "denominator": 0}
    )
    nonviable_margin_mask = (df.true_margin90_population < decision_config.min_margin_per_customer).tolist()
    metrics["false_provisional_adoption_when_true_margin_below_threshold"] = _probability_metric(
        df.day90_provisional.tolist(), denominator_mask=nonviable_margin_mask)
    bias_errors = [v for v in df.bias.tolist() if v is not None and np.isfinite(v)]
    bias_metric = _continuous_metric(bias_errors)
    estimated_metric = _continuous_metric([v for v in df.rd_est.tolist() if v is not None and np.isfinite(v)])
    per_arm_child_streams = [{"entropy": int(s.entropy), "spawn_key": list(s.spawn_key)} for s in replicate_sequences]
    return {
        "label": "HYPOTHETICAL SYNTHETIC MONTE CARLO; NOT BUSINESS EVIDENCE",
        "replicates": R, "seed": seed, "seed_stream_scheme": "numpy.SeedSequence.spawn; serial order-independent replicate streams",
        "replicate_seed_streams": per_arm_child_streams,
        "n_customers": base.n_customers, "scenario": base.outcome_missingness,
        "margin_resolution_follows_outcome": base.margin_resolution_follows_outcome,
        "margin_bootstrap_replicates_per_trial": margin_bootstrap_reps,
        "margin_gate_metrics_include_bootstrap_replicates": margin_bootstrap_reps,
        "simulator_evaluation_only": {
            "population_itt_rd_mean": float(np.mean([r["population_truth"] for r in rows])),
            "finite_population_sate_mean": _continuous_metric([r["truth"] for r in rows]),
            "population_itt_margin_90": float(np.mean([r["true_margin90_population"] for r in rows])),
            "finite_population_sate_margin_90": _continuous_metric([r["true_margin90_sate"] for r in rows]),
            "conditional_effect": base.eligible_effect,
            "hidden_missingness_mechanism": base.outcome_missingness,
        },
        "continuous_metrics": {"bias_vs_finite_population_sate": bias_metric, "estimated_resolved_rd": estimated_metric},
        "probability_metrics": metrics,
        "effective_denominators": {
            "all_replicates": R,
            "primary_interval_defined": int(df.primary_defined.sum()),
            "day90_provisional_adoption": int(df.day90_provisional.sum()),
            "margin_bootstrap_replicates_per_trial": margin_bootstrap_reps,
        },
        "status_counts": {"day90": {str(k): int(v) for k, v in df.day90_status.value_counts(dropna=False).items()}, "day180": {str(k): int(v) for k, v in df.day180_status.value_counts(dropna=False).items()}},
        "smoke_results_are_not_precise_operating_characteristics": R < 5000,
    }


def write_simulation_result(result: dict[str, Any], output_path: str | Path) -> Path:
    """Write JSON only beneath the dedicated ignored synthetic output directory."""
    path = Path(output_path).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[2]
    safe_root = (repo_root / ".local" / "exp-sim-output").resolve()
    if not path.is_relative_to(safe_root):
        raise ValueError("Simulation output must remain under .local/exp-sim-output")
    lowered = str(path).lower()
    if any(marker.lower() in lowered for marker in PRIVATE_PATH_MARKERS):
        raise ValueError("Refusing a path associated with private or source outcomes")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

"""Reproducible, checkpointed synthetic Monte Carlo campaign runner."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import tempfile
import time
from typing import Any

import numpy as np

from .core import (
    DecisionConfig, ExperimentConfig, SensitivityRange, monte_carlo,
    summarize_replicate_results, write_simulation_result,
)

SCENARIO_NAMES = (
    "A_clean_null", "B_positive_persistent_effect", "C_random_missingness",
    "D_outcome_dependent_missingness", "E_rare_experience_harm",
    "F_positive_conversion_negative_margin", "G_purchase_acceleration",
    "H_mnar_below_commercial_hurdle", "I_complete_twin_below_hurdle",
)
FULL_CAMPAIGN_SEED = 20261113  # fresh; 003E pilot uses a distinct seed
MIN_CAMPAIGN_CUSTOMERS = 25_000
DEFAULT_CAMPAIGN_REPLICATES = 10_000
DEFAULT_BLOCK_SIZE = 500
CHECKPOINT_FORMAT = "exp-sim-replicate-block-v1"


def scenario_matrix(*, n_customers: int = MIN_CAMPAIGN_CUSTOMERS,
                    seed: int = FULL_CAMPAIGN_SEED) -> dict[str, ExperimentConfig]:
    """Return nine hypothetical scenarios; I is H's complete-data twin."""
    base = ExperimentConfig(n_customers=n_customers, seed=seed)
    viable = dict(p_repeat_180_control=0.35, contribution_per_repeat=20.0,
                  intervention_cost_per_sent=0.35)
    configs = {
        "A_clean_null": replace(base, eligible_effect=0.0, effect_180_eligible=0.0),
        "B_positive_persistent_effect": replace(base, eligible_effect=0.06,
                                                  effect_180_eligible=0.06, **viable),
        "C_random_missingness": replace(base, eligible_effect=0.06,
                                         effect_180_eligible=0.06, outcome_missingness="balanced_random",
                                         missing_rate_control=0.015, missing_rate_treatment=0.015,
                                         margin_resolution_follows_outcome=True, **viable),
        "D_outcome_dependent_missingness": replace(base, eligible_effect=0.06,
                                                    effect_180_eligible=0.06,
                                                    outcome_missingness="outcome_dependent",
                                                    missing_rate_control=0.01,
                                                    missing_rate_treatment=0.01,
                                                    missing_effect_if_repeat=2.0,
                                                    margin_resolution_follows_outcome=True, **viable),
        "E_rare_experience_harm": replace(base, eligible_effect=0.06,
                                          effect_180_eligible=0.06,
                                          p_complaint_control=0.001,
                                          complaint_effect=0.004,
                                          p_optout_control=0.01,
                                          optout_effect=0.010,
                                          guardrail_latent_correlation=0.4, **viable),
        "F_positive_conversion_negative_margin": replace(base, eligible_effect=0.08,
                                                          effect_180_eligible=0.08,
                                                          contribution_per_repeat=6.0,
                                                          intervention_cost_per_sent=5.0),
        "G_purchase_acceleration": replace(base, eligible_effect=0.06,
                                            effect_180_eligible=0.0,
                                            **viable),
        "H_mnar_below_commercial_hurdle": replace(
            base, eligible_effect=0.04, effect_180_eligible=0.04,
            outcome_missingness="outcome_dependent",
            missing_rate_control=0.012, missing_rate_treatment=0.008,
            missing_effect_if_repeat=2.0,
            margin_resolution_follows_outcome=True, **viable),
    }
    # The only DGP change from H to I is complete purchase-outcome ascertainment.
    configs["I_complete_twin_below_hurdle"] = replace(
        configs["H_mnar_below_commercial_hurdle"], outcome_missingness="complete")
    if tuple(configs) != SCENARIO_NAMES:
        raise RuntimeError("Scenario matrix order or membership changed unexpectedly")
    validate_scenario_matrix(configs)
    b, g = configs["B_positive_persistent_effect"], configs["G_purchase_acceleration"]
    if {k: v for k, v in asdict(b).items() if k != "effect_180_eligible"} != {
            k: v for k, v in asdict(g).items() if k != "effect_180_eligible"}:
        raise RuntimeError("B and G must differ only in their Day-180 eligible treatment effect")
    h, i = configs["H_mnar_below_commercial_hurdle"], configs["I_complete_twin_below_hurdle"]
    if {k: v for k, v in asdict(h).items() if k != "outcome_missingness"} != {
            k: v for k, v in asdict(i).items() if k != "outcome_missingness"}:
        raise RuntimeError("H and I must differ only in purchase-outcome ascertainment")
    return configs


def validate_scenario_matrix(configs: dict[str, ExperimentConfig]) -> None:
    if tuple(configs) != SCENARIO_NAMES:
        raise ValueError(f"Expected exactly the prespecified scenario names in order: {SCENARIO_NAMES}")
    for name, config in configs.items():
        config.validate()
        if config.outcome_missingness != "complete" and not config.margin_resolution_follows_outcome:
            raise ValueError(f"{name}: unresolved outcomes require linked financial masking")


def _population_repeat_probability(config: ExperimentConfig, *, treatment: bool) -> float:
    control = config.p_early_repeat + (1 - config.p_early_repeat) * config.p_late_repeat
    if not treatment:
        return control
    eligible_fraction = ((1 - config.p_early_repeat) * (1 - config.p_optout_pre_day21)
                         * config.p_operationally_contactable)
    return control + eligible_fraction * config.eligible_effect


def scenario_truth(config: ExperimentConfig, scenario_name: str | None = None,
                   decision_config: DecisionConfig = DecisionConfig()) -> dict[str, Any]:
    """Analytic synthetic truth plus explicitly non-guaranteed decision expectations."""
    pi = ((1 - config.p_early_repeat) * (1 - config.p_optout_pre_day21)
          * config.p_operationally_contactable)
    margin90 = pi * (config.eligible_effect * config.contribution_per_repeat
                     - config.intervention_cost_per_sent)
    margin180 = pi * (config.effect_180_eligible * config.contribution_per_repeat
                      - config.intervention_cost_per_sent)
    expected_missing: dict[str, float | None] = {"control": 0.0, "treatment": 0.0}
    if config.outcome_missingness == "balanced_random":
        expected_missing = {"control": config.missing_rate_control,
                            "treatment": config.missing_rate_control}
    elif config.outcome_missingness == "differential":
        expected_missing = {"control": config.missing_rate_control,
                            "treatment": config.missing_rate_treatment}
    elif config.outcome_missingness == "outcome_dependent":
        for arm, assigned_treatment in (("control", False), ("treatment", True)):
            base_rate = (config.missing_rate_treatment if assigned_treatment
                         else config.missing_rate_control)
            repeat_probability = _population_repeat_probability(config, treatment=assigned_treatment)
            expected_missing[arm] = base_rate * (1 + config.missing_effect_if_repeat * repeat_probability)

    expected_resolved_risk: dict[str, float] = {}
    for arm, assigned_treatment in (("control", False), ("treatment", True)):
        risk = _population_repeat_probability(config, treatment=assigned_treatment)
        if config.outcome_missingness == "outcome_dependent":
            base_rate = (config.missing_rate_treatment if assigned_treatment
                         else config.missing_rate_control)
            resolved_repeat = risk * (1 - base_rate * (1 + config.missing_effect_if_repeat))
            resolved_nonrepeat = (1 - risk) * (1 - base_rate)
            expected_resolved_risk[arm] = resolved_repeat / (resolved_repeat + resolved_nonrepeat)
        else:
            expected_resolved_risk[arm] = risk
    expected_resolved_rd = expected_resolved_risk["treatment"] - expected_resolved_risk["control"]
    expected_resolved_bias = expected_resolved_rd - pi * config.eligible_effect
    arm_allocation = config.allocation_treatment
    expected_resolved_n_t = config.n_customers * arm_allocation * (1 - expected_missing["treatment"])
    expected_resolved_n_c = config.n_customers * (1 - arm_allocation) * (1 - expected_missing["control"])
    expected_resolved_rd_se = float(np.sqrt(
        expected_resolved_risk["treatment"] * (1 - expected_resolved_risk["treatment"]) / expected_resolved_n_t
        + expected_resolved_risk["control"] * (1 - expected_resolved_risk["control"]) / expected_resolved_n_c))
    missing_diff = abs(expected_missing["treatment"] - expected_missing["control"])
    overall_missing = (arm_allocation * expected_missing["treatment"]
                       + (1 - arm_allocation) * expected_missing["control"])
    expected_outcome_diagnostics_pass = (
        1 - overall_missing >= decision_config.min_outcome_completeness
        and missing_diff <= decision_config.max_differential_missingness)
    expected_margin_completeness = {arm: 1 - rate for arm, rate in expected_missing.items()}
    expected_margin_completeness_pass = (
        min(expected_margin_completeness.values()) >= decision_config.min_margin_completeness
        and missing_diff <= decision_config.max_differential_margin_missingness)

    expectations = {
        "A_clean_null": (False, False, False, "No conversion or margin benefit; no adoption is the target behavior."),
        "B_positive_persistent_effect": (True, True, False, "Provisional adoption and later confirmation are plausible."),
        "C_random_missingness": (True, True, False, "Ignorable missingness below the completeness threshold; adoption and confirmation are plausible."),
        "D_outcome_dependent_missingness": (True, True, False, "MNAR may pass observable diagnostics; adoption/confirmation are plausible but resolved-outcome bias remains possible."),
        "E_rare_experience_harm": (False, False, False, "True customer-experience harms exceed guardrail margins; adoption should be blocked by guardrails."),
        "F_positive_conversion_negative_margin": (False, False, False, "Conversion benefit cannot overcome negative contribution margin; adoption should be blocked commercially."),
        "G_purchase_acceleration": (True, False, True, "Day-90 adoption is plausible; the later margin gate should roll back because acceleration disappears."),
        "H_mnar_below_commercial_hurdle": (False, True, False, "True Day-90 margin is below the £0.50 hurdle, so adoption is not warranted. MNAR can pass outcome diagnostics and modestly inflate the resolved risk difference; a false provisional adoption is possible but not guaranteed. If it occurs, Day-180 margin is positive under the £0 threshold, so confirmation is not false by the Day-180 commercial rule."),
        "I_complete_twin_below_hurdle": (False, True, False, "Complete ascertainment with H's same below-hurdle truth; false adoption remains possible from sampling variation under the unchanged commercial rule."),
    }
    expected = expectations.get(scenario_name or "", (None, None, None,
                "No scenario-level expected decision class supplied."))
    complaint_itt_harm = pi * config.p_delivery * config.complaint_effect
    optout_itt_harm = pi * config.p_delivery * config.optout_effect
    return {
        "eligible_population_fraction": pi,
        "population_itt_rd_90": pi * config.eligible_effect,
        "population_itt_rd_180": pi * config.effect_180_eligible,
        "population_incremental_margin_90": margin90,
        "population_incremental_margin_180": margin180,
        "complaint_itt_risk_difference": complaint_itt_harm,
        "optout_itt_risk_difference": optout_itt_harm,
        "expected_missing_fraction_by_arm": expected_missing,
        "expected_overall_outcome_completeness": 1 - overall_missing,
        "expected_absolute_outcome_missingness_difference": missing_diff,
        "expected_observable_outcome_diagnostics_pass_at_truth_rates": expected_outcome_diagnostics_pass,
        "expected_margin_completeness_by_arm": expected_margin_completeness,
        "expected_margin_completeness_gate_pass_at_truth_rates": expected_margin_completeness_pass,
        "expected_resolved_risk_by_arm_under_ascertainment": expected_resolved_risk,
        "expected_resolved_risk_difference_under_ascertainment": expected_resolved_rd,
        "expected_resolved_risk_difference_bias_vs_population_itt": expected_resolved_bias,
        "expected_resolved_risk_difference_standard_error_approx": expected_resolved_rd_se,
        "expected_resolved_bias_in_standard_error_units": (expected_resolved_bias / expected_resolved_rd_se
                                                              if expected_resolved_rd_se > 0 else None),
        "missingness_mechanism": config.outcome_missingness,
        "financial_mask_linked_to_outcome_resolution": config.margin_resolution_follows_outcome,
        "day90_adoption_scientifically_plausible": expected[0],
        "day180_confirmation_scientifically_plausible": expected[1],
        "day180_rollback_scientifically_plausible": expected[2],
        "expected_decision_behavior_not_guaranteed": expected[3],
        "day180_independent_replication": False,
        "false_statistical_rejection_definition": "Under a true zero ITT, any two-sided rejection; under a nonzero ITT, rejection in the direction opposite the known population ITT.",
        "day90_margin_below_commercial_hurdle": margin90 < decision_config.min_margin_per_customer,
        "day180_margin_below_confirmation_threshold": margin180 < decision_config.min_margin_180_point,
        "persistence_interpretation": "population-level cumulative risk difference; not same-customer persistent purchase identity",
        "decision_thresholds_used_for_truth_class": {
            "min_margin_per_customer_90": decision_config.min_margin_per_customer,
            "min_margin_per_customer_180": decision_config.min_margin_180_point,
            "complaint_margin": decision_config.complaint_margin,
            "optout_margin": decision_config.optout_margin,
        },
    }


class CampaignTimeLimit(TimeoutError):
    pass


_ACTIVE_DEADLINE = 0.0
_ACTIVE_MEMORY_CAP_BYTES = 0


def _timeout_handler(signum: int, frame: Any) -> None:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = raw if sys.platform == "darwin" else raw * 1024
    if _ACTIVE_MEMORY_CAP_BYTES and peak_bytes > _ACTIVE_MEMORY_CAP_BYTES:
        raise MemoryError("Scenario exceeded its sampled peak-RSS limit")
    remaining = _ACTIVE_DEADLINE - time.monotonic()
    if remaining <= 0:
        raise CampaignTimeLimit("Campaign or scenario exceeded its wall-clock deadline")
    signal.setitimer(signal.ITIMER_REAL, min(1.0, remaining))


def _validate_memory_limit(memory_limit_mib: int) -> None:
    if memory_limit_mib < 256:
        raise ValueError("memory_limit_mib must be at least 256 MiB")


def _peak_rss_mib() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _campaign_root(output_dir: str | Path) -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[2]
    allowed = (repo_root / ".local" / "exp-sim-output").resolve()
    out_dir = Path(output_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir = out_dir.resolve()
    if not out_dir.is_relative_to(allowed):
        raise ValueError("Campaign output must remain under .local/exp-sim-output")
    lowered = str(out_dir).lower()
    if any(marker in lowered for marker in ("b2b3", "insight-004", "historical", "customer-data")):
        raise ValueError("Campaign output path matches a private/source-data marker")
    return repo_root, out_dir


def _source_fingerprint() -> str:
    module_dir = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in ("core.py", "campaign.py"):
        digest.update(name.encode("utf-8"))
        digest.update((module_dir / name).read_bytes())
    return digest.hexdigest()


def _write_block(path: Path, *, scenario: str, fingerprint: str,
                 rows: list[dict[str, Any]], runtime_seconds: float,
                 peak_rss_mib: float) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: row["replicate_id"])
    ids = [int(row["replicate_id"]) for row in ordered]
    if not ids or ids != list(range(ids[0], ids[-1] + 1)):
        raise ValueError("A checkpoint block must contain a non-empty contiguous replicate-ID range")
    row_lines = [_canonical(row) for row in ordered]
    rows_digest = hashlib.sha256(("\n".join(row_lines) + "\n").encode("utf-8")).hexdigest()
    header = {"format": CHECKPOINT_FORMAT, "scenario": scenario,
              "fingerprint": fingerprint, "start": ids[0], "stop": ids[-1] + 1,
              "row_count": len(ordered), "rows_sha256": rows_digest,
              "runtime_seconds": runtime_seconds,
              "peak_process_rss_mib": peak_rss_mib}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as zipped:
                zipped.write((_canonical(header) + "\n").encode("utf-8"))
                for line in row_lines:
                    zipped.write((line + "\n").encode("utf-8"))
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return header


def _read_blocks(directory: Path, *, scenario: str, fingerprint: str,
                 replicates: int) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[int, dict[str, Any]] = {}
    headers = []
    for path in sorted(directory.glob("block-*.jsonl.gz")):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                header = json.loads(stream.readline())
                rows = [json.loads(line) for line in stream if line.strip()]
        except (OSError, EOFError, json.JSONDecodeError) as exc:
            raise ValueError(f"Corrupt checkpoint block: {path}") from exc
        if (header.get("format") != CHECKPOINT_FORMAT or header.get("scenario") != scenario
                or header.get("fingerprint") != fingerprint):
            raise ValueError(f"Incompatible checkpoint block: {path}")
        ids = [row.get("replicate_id") for row in rows]
        start, stop = header.get("start"), header.get("stop")
        if (not isinstance(start, int) or not isinstance(stop, int) or stop <= start
                or ids != list(range(start, stop)) or len(rows) != header.get("row_count")
                or stop > replicates):
            raise ValueError(f"Invalid checkpoint row range or count: {path}")
        digest = hashlib.sha256(("\n".join(_canonical(row) for row in rows) + "\n").encode("utf-8")).hexdigest()
        if digest != header.get("rows_sha256"):
            raise ValueError(f"Checkpoint checksum mismatch: {path}")
        for row in rows:
            replicate_id = int(row["replicate_id"])
            if replicate_id in by_id:
                raise ValueError(f"Duplicate replicate ID {replicate_id} across checkpoints")
            by_id[replicate_id] = row
        headers.append(header)
    return by_id, headers


def _scenario_fingerprint(*, scenario: str, config: ExperimentConfig,
                          scenario_seed: np.random.SeedSequence, seed: int,
                          replicates: int, margin_bootstrap_reps: int,
                          sensitivity: SensitivityRange,
                          decision_config: DecisionConfig) -> str:
    return _hash_value({
        "scenario": scenario, "dgp": asdict(config), "campaign_seed": seed,
        "scenario_seed_spawn_key": list(scenario_seed.spawn_key),
        "replicates": replicates, "margin_bootstrap_reps": margin_bootstrap_reps,
        "sensitivity": asdict(sensitivity), "decision_config": asdict(decision_config),
        "missingness_assumptions_approved": True,
        "code_sha256": _source_fingerprint(), "checkpoint_format": CHECKPOINT_FORMAT,
    })


def _scenario_seed_sequences(seed: int) -> list[np.random.SeedSequence]:
    """Create stable streams, deliberately pairing I with H via common random numbers."""
    streams = np.random.SeedSequence(seed).spawn(len(SCENARIO_NAMES))
    streams[SCENARIO_NAMES.index("I_complete_twin_below_hurdle")] = streams[
        SCENARIO_NAMES.index("H_mnar_below_commercial_hurdle")]
    return streams


def campaign_configuration_fingerprint(
    *, seed: int = FULL_CAMPAIGN_SEED,
    n_customers: int = MIN_CAMPAIGN_CUSTOMERS,
    replicates: int = DEFAULT_CAMPAIGN_REPLICATES,
    margin_bootstrap_reps: int = 1000,
) -> str:
    """Return the code- and configuration-bound fingerprint without running trials."""
    configs = scenario_matrix(n_customers=n_customers, seed=seed)
    scenario_seeds = _scenario_seed_sequences(seed)
    sensitivity = SensitivityRange(-0.10, 0.10, True,
                                   "HYPOTHETICAL SYNTHETIC STRESS RANGE; NOT OWNER APPROVED")
    decision_config = DecisionConfig()
    return _hash_value({
        "seed": seed, "n_customers": n_customers, "replicates": replicates,
        "margin_bootstrap_reps": margin_bootstrap_reps,
        "scenario_fingerprints": {
            name: _scenario_fingerprint(
                scenario=name, config=config, scenario_seed=scenario_seeds[i], seed=seed,
                replicates=replicates, margin_bootstrap_reps=margin_bootstrap_reps,
                sensitivity=sensitivity, decision_config=decision_config)
            for i, (name, config) in enumerate(configs.items())},
    })


def _binary_probability(values: list[bool], *, mask: list[bool] | None = None) -> dict[str, Any]:
    selected = ([bool(value) for value, keep in zip(values, mask) if keep]
                if mask is not None else [bool(value) for value in values])
    n = len(selected)
    k = sum(selected)
    p = k / n if n else None
    if n:
        from .core import wilson_interval
        ci = list(wilson_interval(k, n))
        mcse = float(np.sqrt(p * (1 - p) / n))
    else:
        ci, mcse = [None, None], None
    return {"estimate": p, "mcse": mcse, "ci95_wilson": ci,
            "numerator": k, "denominator": n}


def _paired_binary_difference(h: list[bool], i: list[bool]) -> dict[str, Any]:
    if len(h) != len(i) or not h:
        raise ValueError("Paired comparison requires equally sized, non-empty replicate vectors")
    differences = np.asarray(h, dtype=float) - np.asarray(i, dtype=float)
    estimate = float(differences.mean())
    mcse = float(differences.std(ddof=1) / np.sqrt(len(differences))) if len(differences) > 1 else None
    # A conservative finite-sample interval avoids a misleading zero-width
    # normal interval when a small pilot has no discordant pairs.
    half = min(1.0, float(np.sqrt(2 * np.log(2 / 0.05) / len(differences))))
    return {
        "estimate_h_minus_i": estimate, "mcse_paired": mcse,
        "ci95_conservative_hoeffding": [max(-1.0, estimate - half), min(1.0, estimate + half)],
        "h_only_events": int(np.sum(differences > 0)),
        "i_only_events": int(np.sum(differences < 0)),
        "ties": int(np.sum(differences == 0)), "denominator_pairs": len(differences),
        "method": "replicate-level paired difference; common random numbers",
    }


def summarize_h_i_comparison(h_rows: list[dict[str, Any]], i_rows: list[dict[str, Any]],
                             decision_config: DecisionConfig = DecisionConfig()) -> dict[str, Any]:
    """Compare H and I using matched replicate IDs and verified shared seed keys."""
    h_by_id = {int(row["replicate_id"]): row for row in h_rows}
    i_by_id = {int(row["replicate_id"]): row for row in i_rows}
    if not h_rows or h_by_id.keys() != i_by_id.keys():
        raise ValueError("H/I comparison requires identical non-empty replicate ID sets")
    ids = sorted(h_by_id)
    if any(h_by_id[k]["seed_key"] != i_by_id[k]["seed_key"] for k in ids):
        raise ValueError("H/I rows do not share the pre-specified paired random stream")

    def false_adoption(row: dict[str, Any]) -> bool:
        return bool(row["day90_provisional"] and
                    row["true_margin90_population"] < decision_config.min_margin_per_customer)

    def false_d180(row: dict[str, Any]) -> bool:
        return bool(row["day180_confirm"] and
                    row["true_margin180_population"] < decision_config.min_margin_180_point)

    def selected_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "false_provisional_adoption": _binary_probability(
                [false_adoption(r) for r in rows], mask=[
                    r["true_margin90_population"] < decision_config.min_margin_per_customer for r in rows]),
            "false_day180_confirmation": _binary_probability(
                [false_d180(r) for r in rows], mask=[
                    r["true_margin180_population"] < decision_config.min_margin_180_point for r in rows]),
            "false_day180_confirmation_given_provisional_adoption": _binary_probability(
                [false_d180(r) for r in rows], mask=[
                    r["day90_provisional"] and
                    r["true_margin180_population"] < decision_config.min_margin_180_point for r in rows]),
            "primary_analysis_inconclusive": _binary_probability([r["primary_inconclusive"] for r in rows]),
            "margin_gate_pass": _binary_probability([r["margin_gate_90"] == "PASS" for r in rows]),
            "margin_gate_fail": _binary_probability([r["margin_gate_90"] == "FAIL" for r in rows]),
            "margin_gate_inconclusive": _binary_probability([r["margin_gate_90"] == "INCONCLUSIVE" for r in rows]),
            "financial_completeness_gate_not_pass": _binary_probability([r["margin_completeness_gate_90"] != "PASS" for r in rows]),
            "complaint_guardrail_pass": _binary_probability([r["complaint_state"] == "PASS" for r in rows]),
            "complaint_guardrail_fail": _binary_probability([r["complaint_state"] == "FAIL" for r in rows]),
            "optout_guardrail_pass": _binary_probability([r["optout_state"] == "PASS" for r in rows]),
            "optout_guardrail_fail": _binary_probability([r["optout_state"] == "FAIL" for r in rows]),
            "both_guardrails_pass": _binary_probability([
                r["complaint_state"] == "PASS" and r["optout_state"] == "PASS" for r in rows]),
        }

    h_false = [false_adoption(h_by_id[k]) for k in ids]
    i_false = [false_adoption(i_by_id[k]) for k in ids]
    return {
        "label": "HYPOTHETICAL SYNTHETIC PAIRED COMPARISON; NOT BUSINESS EVIDENCE",
        "comparison": "H minus I; identical randomised population and stochastic components, differing only in outcome ascertainment",
        "pairing_verified": True, "replicate_ids": ids,
        "H": selected_metrics([h_by_id[k] for k in ids]),
        "I": selected_metrics([i_by_id[k] for k in ids]),
        "false_provisional_adoption_h_minus_i": _paired_binary_difference(h_false, i_false),
        "interpretation": "Synthetic within-generator contrast for the ascertainment mechanism; not a real-world causal estimate. Individual false adoptions can arise from chance under the unchanged decision rule.",
    }


def run_campaign(
    *, replicates: int = 20, n_customers: int = MIN_CAMPAIGN_CUSTOMERS,
    seed: int = FULL_CAMPAIGN_SEED, margin_bootstrap_reps: int = 1000,
    block_size: int = DEFAULT_BLOCK_SIZE, max_seconds: int = 180,
    scenario_timeout_seconds: int = 60, memory_limit_mib: int = 1536,
    output_dir: str | Path = ".local/exp-sim-output/EXP-SIM-003E/smoke",
    resume: bool = False, allow_small_sample: bool = False,
) -> dict[str, Any]:
    global _ACTIVE_DEADLINE, _ACTIVE_MEMORY_CAP_BYTES
    if replicates < 1 or margin_bootstrap_reps < 1 or block_size < 1:
        raise ValueError("replicates, bootstrap repetitions, and block_size must be positive")
    if n_customers < MIN_CAMPAIGN_CUSTOMERS and not allow_small_sample:
        raise ValueError("Campaign trials require >=25,000 customers; set allow_small_sample only for smoke checks")
    if max_seconds < 1 or scenario_timeout_seconds < 1:
        raise ValueError("Time limits must be positive")
    _validate_memory_limit(memory_limit_mib)
    repo_root, out_dir = _campaign_root(output_dir)
    configs = scenario_matrix(n_customers=n_customers, seed=seed)
    scenario_seeds = _scenario_seed_sequences(seed)
    sensitivity = SensitivityRange(-0.10, 0.10, True,
                                  "HYPOTHETICAL SYNTHETIC STRESS RANGE; NOT OWNER APPROVED")
    decision_config = DecisionConfig()
    campaign_fingerprint = campaign_configuration_fingerprint(
        seed=seed, n_customers=n_customers, replicates=replicates,
        margin_bootstrap_reps=margin_bootstrap_reps)
    manifest_path = out_dir / "campaign-manifest.json"
    if manifest_path.exists():
        if not resume:
            raise FileExistsError("Campaign output already has a manifest; use --resume or choose a new output path")
        try:
            old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Corrupt campaign manifest; refusing resume") from exc
        if old_manifest.get("configuration_fingerprint") != campaign_fingerprint:
            raise ValueError("Campaign manifest is incompatible with requested configuration/code")
    elif resume and any(out_dir.rglob("block-*.jsonl.gz")):
        # Every block is independently self-describing, but a missing manifest
        # could hide an interrupted configuration change; fail closed.
        raise ValueError("Checkpoint blocks exist without their campaign manifest")

    if not resume and out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError("Output directory is not empty; choose a fresh path or resume compatible checkpoints")
    out_dir.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGALRM, _timeout_handler)
    started = time.monotonic()
    global_deadline = started + max_seconds
    manifest: dict[str, Any] = {
        "label": "HYPOTHETICAL SYNTHETIC CAMPAIGN; NOT BUSINESS EVIDENCE",
        "status": "RUNNING", "configuration_fingerprint": campaign_fingerprint,
        "seed": seed, "seed_scheme": (f"SeedSequence(campaign seed).spawn({len(SCENARIO_NAMES)}); I reuses H's scenario key for paired common random numbers; stable replicate-ID child keys"),
        "replicates_per_scenario": replicates, "customers_per_replicate": n_customers,
        "small_sample_override_flag_supplied": bool(allow_small_sample),
        "sample_size_below_assurance_minimum": n_customers < MIN_CAMPAIGN_CUSTOMERS,
        "allocation": {"treatment": round(n_customers * 0.5), "control": n_customers - round(n_customers * 0.5)},
        "margin_bootstrap_reps": margin_bootstrap_reps, "block_size": block_size,
        "memory_limit_mib_sampled_peak_rss": memory_limit_mib,
        "max_wall_seconds": max_seconds, "scenario_timeout_seconds": scenario_timeout_seconds,
        "sensitivity_range": asdict(sensitivity), "day180_independent_replication": False,
        "paired_scenarios": {"H_mnar_below_commercial_hurdle": "shared stochastic scenario stream with I",
                             "I_complete_twin_below_hurdle": "paired to H; only outcome ascertainment differs"},
        "scenarios": {},
    }
    if resume and manifest_path.exists():
        manifest["previous_status"] = old_manifest.get("status")
    _atomic_json(manifest, manifest_path)

    stop_status: str | None = None
    for scenario_index, (name, config) in enumerate(configs.items()):
        scenario_seed = scenario_seeds[scenario_index]
        fingerprint = _scenario_fingerprint(
            scenario=name, config=config, scenario_seed=scenario_seed, seed=seed,
            replicates=replicates, margin_bootstrap_reps=margin_bootstrap_reps,
            sensitivity=sensitivity, decision_config=decision_config)
        scenario_dir = out_dir / name
        if not scenario_dir.resolve().is_relative_to(out_dir.resolve()):
            raise ValueError("Scenario directory resolves outside the approved output root")
        scenario_dir.mkdir(parents=True, exist_ok=True)
        rows_by_id, headers = _read_blocks(scenario_dir, scenario=name,
                                           fingerprint=fingerprint, replicates=replicates)
        scenario_started = time.monotonic()
        for chunk_start in range(0, replicates, block_size):
            chunk_stop = min(replicates, chunk_start + block_size)
            while True:
                missing_ids = [i for i in range(chunk_start, chunk_stop) if i not in rows_by_id]
                if not missing_ids:
                    break
                # Existing blocks may use another block size. Evaluate only a
                # missing contiguous run; stable replicate IDs define all RNG.
                run_start = missing_ids[0]
                run_ids = [run_start]
                for replicate_id in missing_ids[1:]:
                    if replicate_id == run_ids[-1] + 1 and len(run_ids) < block_size:
                        run_ids.append(replicate_id)
                    else:
                        break
                run_stop = run_ids[-1] + 1
                remaining_global = global_deadline - time.monotonic()
                remaining_scenario = scenario_timeout_seconds - (time.monotonic() - scenario_started)
                allowance = min(remaining_global, remaining_scenario)
                if allowance <= 0:
                    stop_status = "INCOMPLETE_TIME_LIMIT"
                    manifest["scenarios"][name] = {"status": "TIME_LIMIT", "completed_replicates": len(rows_by_id)}
                    break
                _ACTIVE_DEADLINE = min(global_deadline, scenario_started + scenario_timeout_seconds)
                _ACTIVE_MEMORY_CAP_BYTES = memory_limit_mib * 1024 * 1024
                signal.setitimer(signal.ITIMER_REAL, min(1.0, allowance))
                block_started = time.monotonic()
                try:
                    block = monte_carlo(
                        config, replicates=run_stop - run_start,
                        seed_sequence=scenario_seed, replicate_start=run_start,
                        sensitivity_range=sensitivity, decision_config=decision_config,
                        margin_bootstrap_reps=margin_bootstrap_reps,
                        missingness_assumptions_approved=True,
                    )
                    block_rows = block["replicate_results"]
                    block_path = scenario_dir / f"block-{run_start:08d}-{run_stop:08d}.jsonl.gz"
                    if not block_path.resolve().is_relative_to(out_dir.resolve()):
                        raise ValueError("Unsafe checkpoint block output path")
                    block_runtime = time.monotonic() - block_started
                    block_peak_rss = _peak_rss_mib()
                    header = _write_block(block_path, scenario=name,
                                          fingerprint=fingerprint, rows=block_rows,
                                          runtime_seconds=block_runtime,
                                          peak_rss_mib=block_peak_rss)
                    for row in block_rows:
                        rows_by_id[row["replicate_id"]] = row
                    headers.append(header)
                    manifest["scenarios"][name] = {
                        "status": "RUNNING", "completed_replicates": len(rows_by_id),
                        "checkpoint_blocks": len(headers),
                        "latest_block_runtime_seconds": time.monotonic() - block_started,
                        "latest_block_peak_process_rss_mib": block_peak_rss,
                        "checkpoint_directory": str(block_path.parent.relative_to(repo_root)),
                    }
                    _atomic_json(manifest, manifest_path)
                except CampaignTimeLimit:
                    stop_status = "INCOMPLETE_TIME_LIMIT"
                    manifest["scenarios"][name] = {"status": "TIME_LIMIT", "completed_replicates": len(rows_by_id)}
                    break
                except MemoryError:
                    stop_status = "INCOMPLETE_MEMORY_LIMIT"
                    manifest["scenarios"][name] = {"status": "MEMORY_LIMIT", "completed_replicates": len(rows_by_id)}
                    break
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
            if stop_status:
                break
        if stop_status:
            break
        expected_ids = list(range(replicates))
        if sorted(rows_by_id) != expected_ids:
            raise ValueError(f"Scenario {name} has missing or unexpected replicate IDs after checkpoint resume")
        rows = [rows_by_id[i] for i in expected_ids]
        summary = summarize_replicate_results(
            config, rows, seed=seed, seed_sequence=scenario_seed,
            sensitivity_range=sensitivity, decision_config=decision_config,
            margin_bootstrap_reps=margin_bootstrap_reps,
        )
        summary.pop("replicate_results")
        summary.update({
            "scenario_name": name, "scenario_truth": scenario_truth(config, name, decision_config),
            "decision_parameters": asdict(decision_config),
            "replicate_record_format": "gzip JSONL checkpoint blocks; one synthetic-only row per replicate",
            "replicate_record_blocks": [
                {"path": str((scenario_dir / f"block-{h['start']:08d}-{h['stop']:08d}.jsonl.gz").relative_to(repo_root)),
                 "start": h["start"], "stop": h["stop"],
                 "runtime_seconds": h.get("runtime_seconds"),
                 "peak_process_rss_mib": h.get("peak_process_rss_mib"),
                 "sha256_uncompressed_rows": h["rows_sha256"]}
                for h in sorted(headers, key=lambda x: x["start"])],
            "scenario_runtime_seconds_this_invocation": time.monotonic() - scenario_started,
            "peak_process_rss_mib": _peak_rss_mib(),
        })
        summary_path = scenario_dir / "summary.json"
        if not summary_path.resolve().is_relative_to(out_dir.resolve()):
            raise ValueError("Unsafe scenario summary output path")
        _atomic_json(summary, summary_path)
        manifest["scenarios"][name] = {
            "status": "COMPLETE", "completed_replicates": replicates,
            "checkpoint_blocks": len(headers),
            "summary_path": str(summary_path.relative_to(repo_root)),
            "runtime_seconds_this_invocation": time.monotonic() - scenario_started,
            "peak_process_rss_mib": _peak_rss_mib(),
            "primary_inconclusive_rate": summary["probability_metrics"]["primary_statistical_inconclusive_rate"],
            "provisional_adoption": summary["probability_metrics"]["day90_provisional_adoption"],
        }
        _atomic_json(manifest, manifest_path)
        if time.monotonic() >= global_deadline:
            stop_status = "INCOMPLETE_TIME_LIMIT"
            break

    manifest["status"] = stop_status or ("COMPLETE" if len(manifest["scenarios"]) == len(configs)
                                         and all(v.get("status") == "COMPLETE" for v in manifest["scenarios"].values())
                                         else "INCOMPLETE")
    if manifest["status"] == "COMPLETE":
        h_name, i_name = "H_mnar_below_commercial_hurdle", "I_complete_twin_below_hurdle"
        h_idx, i_idx = SCENARIO_NAMES.index(h_name), SCENARIO_NAMES.index(i_name)
        h_fp = _scenario_fingerprint(
            scenario=h_name, config=configs[h_name], scenario_seed=scenario_seeds[h_idx], seed=seed,
            replicates=replicates, margin_bootstrap_reps=margin_bootstrap_reps,
            sensitivity=sensitivity, decision_config=decision_config)
        i_fp = _scenario_fingerprint(
            scenario=i_name, config=configs[i_name], scenario_seed=scenario_seeds[i_idx], seed=seed,
            replicates=replicates, margin_bootstrap_reps=margin_bootstrap_reps,
            sensitivity=sensitivity, decision_config=decision_config)
        h_rows, _ = _read_blocks(out_dir / h_name, scenario=h_name,
                                 fingerprint=h_fp,
                                 replicates=replicates)
        i_rows, _ = _read_blocks(out_dir / i_name, scenario=i_name,
                                 fingerprint=i_fp,
                                 replicates=replicates)
        comparison = summarize_h_i_comparison(
            [h_rows[k] for k in range(replicates)], [i_rows[k] for k in range(replicates)],
            decision_config=decision_config)
        comparison["campaign_configuration_fingerprint"] = campaign_fingerprint
        comparison["seed"] = seed
        comparison_path = out_dir / "comparisons" / "H_vs_I.json"
        if not comparison_path.resolve().is_relative_to(out_dir.resolve()):
            raise ValueError("Unsafe H/I comparison output path")
        _atomic_json(comparison, comparison_path)
        manifest["H_I_comparison"] = {
            "path": str(comparison_path.relative_to(repo_root)),
            "pairing_verified": comparison["pairing_verified"],
            "false_provisional_adoption_h_minus_i": comparison["false_provisional_adoption_h_minus_i"],
        }
    manifest["elapsed_seconds_this_invocation"] = time.monotonic() - started
    manifest["peak_process_rss_mib"] = _peak_rss_mib()
    manifest["smoke_results_are_not_precise_operating_characteristics"] = replicates < 5000
    _atomic_json(manifest, manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a synthetic-only, resumable CRM experiment campaign.")
    parser.add_argument("--replicates", type=int, default=20, help="Use 10,000 for the planned full campaign")
    parser.add_argument("--customers", type=int, default=MIN_CAMPAIGN_CUSTOMERS)
    parser.add_argument("--seed", type=int, default=FULL_CAMPAIGN_SEED)
    parser.add_argument("--margin-bootstrap-reps", type=int, default=1000)
    parser.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--scenario-timeout-seconds", type=int, default=60)
    parser.add_argument("--memory-limit-mib", type=int, default=1536)
    parser.add_argument("--output-dir", default=".local/exp-sim-output/EXP-SIM-003E/smoke")
    parser.add_argument("--resume", action="store_true", help="Resume only from matching intact replicate blocks")
    parser.add_argument("--allow-small-sample", action="store_true", help="Allow <25k only for explicitly bounded smoke runs")
    args = parser.parse_args()
    result = run_campaign(replicates=args.replicates, n_customers=args.customers,
                          seed=args.seed, margin_bootstrap_reps=args.margin_bootstrap_reps,
                          block_size=args.block_size, max_seconds=args.max_seconds,
                          scenario_timeout_seconds=args.scenario_timeout_seconds,
                          memory_limit_mib=args.memory_limit_mib,
                          output_dir=args.output_dir, resume=args.resume,
                          allow_small_sample=args.allow_small_sample)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .core import ExperimentConfig, SensitivityRange, monte_carlo, write_simulation_result


def scenario_config(name: str, *, n: int, seed: int) -> ExperimentConfig:
    base = ExperimentConfig(n_customers=n, seed=seed)
    if name == "complete":
        return base
    if name == "balanced_random_missing":
        return replace(base, outcome_missingness="balanced_random", missing_rate_control=0.02, missing_rate_treatment=0.02)
    if name == "differential_missing":
        return replace(base, outcome_missingness="differential", missing_rate_control=0.01, missing_rate_treatment=0.08)
    if name == "outcome_dependent_missing":
        return replace(base, outcome_missingness="outcome_dependent", missing_rate_control=0.03, missing_rate_treatment=0.03, missing_effect_if_repeat=2.0, margin_resolution_follows_outcome=True)
    if name == "eligibility_dilution":
        return replace(base, p_early_repeat=0.55, p_optout_pre_day21=0.10, eligible_effect=0.05)
    if name == "rare_guardrails":
        return replace(base, p_complaint_control=0.001, p_optout_control=0.01, complaint_effect=0.0, optout_effect=0.0)
    if name == "unprofitable_lift":
        return replace(base, eligible_effect=0.05, contribution_per_repeat=3.0, intervention_cost_per_sent=5.0, effect_180_eligible=-0.02)
    if name == "null":
        return replace(base, eligible_effect=0.0, effect_180_eligible=0.0)
    raise ValueError(f"Unknown scenario: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a wholly synthetic CRM experiment Monte Carlo campaign.")
    parser.add_argument("--scenario", choices=["complete", "balanced_random_missing", "differential_missing", "outcome_dependent_missing", "eligibility_dilution", "rare_guardrails", "unprofitable_lift", "null"], default="complete")
    parser.add_argument("--n", type=int, default=4000)
    parser.add_argument("--replicates", type=int, default=50)
    parser.add_argument("--seed", type=int, default=33001)
    parser.add_argument("--output", default=".local/exp-sim-output/EXP-SIM-002/smoke.json")
    parser.add_argument("--unapproved-range", action="store_true", help="Exercise fail-closed range fallback")
    args = parser.parse_args()

    cfg = scenario_config(args.scenario, n=args.n, seed=args.seed)
    rng = None if args.unapproved_range else SensitivityRange(-0.10, 0.10, True, "HYPOTHETICAL SYNTHETIC RANGE; NOT OWNER APPROVED")
    result = monte_carlo(cfg, replicates=args.replicates, seed=args.seed + 1, sensitivity_range=rng)
    result["scenario"] = args.scenario
    result["sensitivity_range_status"] = "unapproved" if rng is None else rng.label
    root = Path(__file__).resolve().parents[2]
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    print(write_simulation_result(result, output))
    print(result)


if __name__ == "__main__":
    main()

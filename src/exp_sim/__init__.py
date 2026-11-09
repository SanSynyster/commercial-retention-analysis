"""Synthetic-only CRM experiment simulation utilities."""

from .core import (
    DecisionConfig,
    ExperimentConfig,
    SensitivityRange,
    analyze_trial,
    decide_adoption,
    generate_trial,
    monte_carlo,
    newcombe_interval,
    write_simulation_result,
)

__all__ = [
    "DecisionConfig",
    "ExperimentConfig",
    "SensitivityRange",
    "analyze_trial",
    "decide_adoption",
    "generate_trial",
    "monte_carlo",
    "newcombe_interval",
    "write_simulation_result",
]

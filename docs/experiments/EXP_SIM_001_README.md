# EXP-SIM synthetic CRM experiment framework

This package generates artificial customer-level trial records only. It does not load transactions, B2B-3 outcomes, CRM data, or customer identifiers. Defaults and scenarios are hypothetical.

## Focused test and smoke commands

From the repository root:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_exp_sim.py' -v
.venv/bin/python -m src.exp_sim.run --scenario null --n 1000 --replicates 20 --seed 301 --output .local/exp-sim-output/EXP-SIM-002/null-smoke.json
.venv/bin/python -m src.exp_sim.run --scenario outcome_dependent_missing --n 1000 --replicates 20 --seed 302 --output .local/exp-sim-output/EXP-SIM-002/mnar-smoke.json
```

Other runner scenarios: `complete`, `balanced_random_missing`, `differential_missing`, `eligibility_dilution`, `rare_guardrails`, and `unprofitable_lift`. Small smoke outputs validate plumbing only; they are not precise operating characteristics. Large campaigns are configurable but were not part of EXP-SIM-002.

The runner uses a labeled hypothetical range for synthetic analysis only. `--unapproved-range` exercises the fail-closed `INCONCLUSIVE / NOT AUTHORISED` path. Output can be written only beneath `.local/exp-sim-output/`.

## Interpretation

`generate_trial` returns a `SyntheticTrial` with separate `.records` (analyst-visible trial information) and `.truth` (simulation-only scoring information). `analyze_trial` and the decision engine accept only `.records`; hidden outcome states and the missingness-mechanism label cannot affect a decision. Monte Carlo compares estimates and decisions with `.truth` only in its evaluation layer.

Primary analysis is assignment-based Newcombe RD among resolved outcomes, targeting the all-randomised ITT under its stated resolution assumptions. It is not automatically unbiased under treatment-dependent missingness. Diagnostics use observable completeness, arm differences and ascertainment-rule parity. The preapproved plausible-departure sensitivity range remains mandatory; worst/best bounds are descriptive only.

Pre-Day-21 opt-outs only affect eligibility. Post-randomisation opt-out events and complaints are separately generated; treatment effects apply only to delivered customers, while rates are compared by randomized assignment. Day-90 provisional adoption and Day-180 confirmation/rollback are separate states. Conversion significance alone cannot authorize adoption, and insufficient Day-180 financial records trigger rollback from provisional expansion.

`SeedSequence.spawn` gives distinct reproducible replicate and component streams; Monte Carlo probabilities include MCSE and effective denominators. The number of bootstrap repetitions used for each margin estimate is reported; use at least 1,000 for operating-characteristic campaigns. No synthetic range, parameter or run grants owner approval for a real experiment.

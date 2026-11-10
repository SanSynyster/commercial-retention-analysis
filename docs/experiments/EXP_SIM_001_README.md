# EXP-SIM synthetic CRM experiment framework

This package generates artificial customer-level trial records only. It does not load transactions, B2B-3 outcomes, CRM data, or customer identifiers. Defaults and scenarios are hypothetical.

## Focused test and smoke commands

From the repository root:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_exp_sim.py' -v
.venv/bin/python -m src.exp_sim.run --scenario null --n 1000 --replicates 20 --seed 301 --output .local/exp-sim-output/EXP-SIM-002/null-smoke.json
.venv/bin/python -m src.exp_sim.run --scenario outcome_dependent_missing --n 1000 --replicates 20 --seed 302 --output .local/exp-sim-output/EXP-SIM-002/mnar-smoke.json
.venv/bin/python -m src.exp_sim.campaign --replicates 20 --customers 25000 --seed 20261112 --margin-bootstrap-reps 1000 --block-size 10 --max-seconds 600 --scenario-timeout-seconds 180 --memory-limit-mib 1536 --output-dir .local/exp-sim-output/EXP-SIM-003D/calibration-verified
```

Other runner scenarios: `complete`, `balanced_random_missing`, `differential_missing`, `eligibility_dilution`, `rare_guardrails`, and `unprofitable_lift`. The `outcome_dependent_missing` runner configuration couples purchase-linked financial-record resolution to 90-day purchase-outcome resolution. Small smoke outputs validate plumbing only; they are not precise operating characteristics. Large campaigns are configurable but were not part of EXP-SIM-002.

The runner uses a labeled hypothetical range for synthetic analysis only. `--unapproved-range` exercises the fail-closed `INCONCLUSIVE / NOT AUTHORISED` path. Output can be written only beneath `.local/exp-sim-output/`.

`src.exp_sim.campaign` defaults to at least 25,000 customers per replicate (12,500 assigned to each arm); this is motivated by guardrail assurance planning, not observed customer volumes. Under the reviewed synthetic assumptions, each guardrail has approximately 80% individual assurance at this allocation, while the probability both pass is approximately 66%. Individual assurance is not joint assurance; a real-trial assurance target requires separate owner approval. Smaller samples are available only for explicit smoke tests. The eight hypothetical families are clean null, persistent positive effect, random missingness, outcome-dependent missingness, rare experience harms, positive conversion with negative contribution margin, purchase acceleration, and H: MNAR with positive conversion effect but true Day-90 margin below the commercial hurdle. H is a false-commercial-adoption stress test; it does not guarantee false adoption. Any scenario with unresolved purchase outcomes must link financial-record resolution to purchase-outcome resolution; validation fails closed otherwise. Pilot memory is guarded by one-second sampled peak RSS (not an OS-enforced hard cap), with per-scenario and total wall-clock deadlines. Replicate result rows are stored as atomic gzip JSONL blocks with deterministic IDs, checksum validation and compatible resume. Changing block boundaries does not change replicate streams or final statistics. Do not interpret a small calibration pilot as an operating-characteristic estimate.

The full campaign remains unexecuted and requires separate authorization. The prepared configuration uses 10,000 replicates per scenario, 25,000 customers per replicate, 1,000 margin bootstrap repetitions, and campaign seed `20261111`, distinct from the EXP-SIM-003B, 003C, and 003D calibration seeds. `SeedSequence(campaign_seed).spawn(8)` creates non-overlapping scenario streams; replicate IDs extend each scenario key. Its planned worst-case binomial MCSE is 0.005. Choose a fresh output directory; resume only when campaign fingerprint, code, DGP, decision thresholds, sensitivity range and sample configuration match.

The earlier EXP-SIM-003B pilot and all EXP-SIM-003C calibration directories remain preserved as historical evidence. They are superseded for campaign-launch planning by the 003D matrix, fresh fingerprint and H stress test. No prior calibration files are deleted or overwritten.

Future full-campaign command (planning only; do not run without separate owner authorization):

```sh
.venv/bin/python -m src.exp_sim.campaign \
  --replicates 10000 --customers 25000 --seed 20261111 \
  --margin-bootstrap-reps 1000 --block-size 500 \
  --max-seconds 86400 --scenario-timeout-seconds 10800 \
  --memory-limit-mib 1536 \
  --output-dir .local/exp-sim-output/EXP-SIM-003D/full-10000
```

## Interpretation

`generate_trial` returns a `SyntheticTrial` with separate `.records` (analyst-visible trial information) and `.truth` (simulation-only scoring information). `analyze_trial` and the decision engine accept only `.records`; hidden outcome states and the missingness-mechanism label cannot affect a decision. Monte Carlo compares estimates and decisions with `.truth` only in its evaluation layer.

Primary analysis is assignment-based Newcombe RD among resolved outcomes, targeting the all-randomised ITT under its stated resolution assumptions. It is not automatically unbiased under treatment-dependent missingness. Diagnostics use observable completeness, arm differences and ascertainment-rule parity. The preapproved plausible-departure sensitivity range remains mandatory; worst/best bounds are descriptive only.

Pre-Day-21 opt-outs only affect eligibility. Post-randomisation opt-out events and complaints are separately generated; treatment effects apply only to delivered customers, while rates are compared by randomized assignment. Day-90 provisional adoption and Day-180 confirmation/rollback are separate states. Conversion significance alone cannot authorize adoption, and insufficient Day-180 financial records trigger rollback from provisional expansion.

Day-180 uses the same synthetic customers and correlated purchase process as Day-90. It is later follow-up, not an independent replication or independent safeguard. B and G share commercial assumptions and Day-90 effect; only the Day-180 effect differs. B has a persistent population-level cumulative risk difference, not necessarily the same individuals making persistent incremental purchases. G is a hypothetical purchase-acceleration case whose Day-90 probability difference is offset by catch-up by Day 180. C uses 1.5% balanced random missingness; D has equal base missingness by arm but missingness depends on hidden purchase outcomes, so equal base rates do not guarantee observable parity diagnostics pass. E's hypothetical delivered-customer harms produce assigned-arm risk differences above the prespecified guardrail margins.

`SeedSequence.spawn` gives distinct reproducible replicate and component streams. Passing the same `SeedSequence` to `generate_trial` is repeatable; the generator clones its immutable seed identity before spawning. Monte Carlo probabilities include plug-in MCSE, effective denominators and Wilson intervals, which remain informative when a smoke estimate is zero. Tipping-point distance output includes its grid resolution. The number of bootstrap repetitions used for each margin estimate is reported; use at least 1,000 for operating-characteristic campaigns. No synthetic range, parameter or run grants owner approval for a real experiment.

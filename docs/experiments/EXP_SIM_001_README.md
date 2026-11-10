# EXP-SIM synthetic CRM experiment framework

This package generates artificial customer-level trial records only. It does not load transactions, B2B-3 outcomes, CRM data, or customer identifiers. Defaults and scenarios are hypothetical.

## Focused test and smoke commands

From the repository root:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_exp_sim.py' -v
.venv/bin/python -m src.exp_sim.run --scenario null --n 1000 --replicates 20 --seed 301 --output .local/exp-sim-output/EXP-SIM-002/null-smoke.json
.venv/bin/python -m src.exp_sim.run --scenario outcome_dependent_missing --n 1000 --replicates 20 --seed 302 --output .local/exp-sim-output/EXP-SIM-002/mnar-smoke.json
.venv/bin/python -m src.exp_sim.campaign --replicates 10 --customers 25000 --seed 20261114 --margin-bootstrap-reps 1000 --block-size 5 --max-seconds 360 --scenario-timeout-seconds 120 --memory-limit-mib 1536 --output-dir .local/exp-sim-output/EXP-SIM-003E/calibration-final-review
```

Other runner scenarios: `complete`, `balanced_random_missing`, `differential_missing`, `eligibility_dilution`, `rare_guardrails`, and `unprofitable_lift`. The `outcome_dependent_missing` runner configuration couples purchase-linked financial-record resolution to 90-day purchase-outcome resolution. Small smoke outputs validate plumbing only; they are not precise operating characteristics. Large campaigns are configurable but were not part of EXP-SIM-002.

The runner uses a labeled hypothetical range for synthetic analysis only. `--unapproved-range` exercises the fail-closed `INCONCLUSIVE / NOT AUTHORISED` path. Output can be written only beneath `.local/exp-sim-output/`.

`src.exp_sim.campaign` defaults to at least 25,000 customers per replicate (12,500 assigned to each arm), motivated by guardrail assurance planning rather than observed customer volumes. The approved target is approximately 80% assurance for each guardrail individually; joint passage is a separately reported operating characteristic (about 66% under the reviewed synthetic assumptions), not an 80% target. Smaller samples are available only for explicit smoke tests. The nine hypothetical families are A–G, H (outcome-dependent missingness with true Day-90 margin below the £0.50 hurdle), and I (H's complete-ascertainment twin). H and I share all random streams for assignment, eligibility, potential outcomes, delivery, guardrails, and financial noise; only the outcome-resolution mechanism differs. H/I use common random numbers and produce a paired synthetic comparison. H's false-adoption probability includes ordinary sampling variation under the accepted commercial rule; the H-minus-I contrast estimates the within-generator change associated with the missingness mechanism and does not mean missingness caused every false adoption. Any scenario with unresolved outcomes must link financial-record resolution to purchase-outcome resolution; validation fails closed otherwise. Pilot memory is guarded by one-second sampled peak RSS (not an OS-enforced hard cap), with per-scenario and total wall-clock deadlines. Replicate rows are stored as atomic gzip JSONL blocks with deterministic IDs, checksums and compatible resume. Do not interpret a small calibration pilot as an operating-characteristic estimate.

The full campaign is not launched. Approved planning is 9 scenarios × 10,000 replicates = 90,000 replicates; N=25,000; 1,000 margin-bootstrap repetitions; full seed `20261113`, distinct from earlier calibration seeds. `SeedSequence(campaign_seed).spawn(9)` creates scenario streams; I intentionally reuses H's scenario key for paired common random numbers. The planned full configuration fingerprint is `19c52e86b2328d97bcce14229ce3b4efa4f8d2e3f96a1473b8822e4e9b31965b`. It supersedes the prior eight-scenario fingerprint. At R=10,000 the worst-case binomial MCSE is 0.005; at p=0.05 it is approximately 0.00218. Every probability includes an effective denominator, plug-in MCSE and Wilson interval; continuous metrics use replicate-based standard errors, and H-minus-I uses paired replicate differences with paired MCSE and a conservative Hoeffding interval.

Rare-event precision: at p=0.001 and R=10,000, plug-in MCSE is about 0.000316; if there are zero events, the two-sided 95% Wilson upper bound is about 0.000384. If a pre-specified upper-bound target of 0.001 is required, evaluate the actual Wilson bound after R=10,000. A proposed relative-MCSE target of 20% would require approximately `R ≥ (1-p_hat)/(0.2² × p_hat)` for nonzero rare-event rates; for an absolute MCSE target δ use `R ≥ p_hat(1-p_hat)/δ²`. Treat these formulas as planning approximations and calculate Wilson precision with the actual binomial count. Report the estimate and denominator even when precision is insufficient. An extension recommendation requires separate owner approval and a new output directory/configuration fingerprint; use the same seed and scenario keys with the larger total R, regenerating replicate IDs from zero so H/I pairing and provenance remain exact. Never auto-extend, change thresholds, or choose a favorable seed.

Earlier EXP-SIM-003B pilot, all EXP-SIM-003C calibration directories, and the 003D calibration outputs remain preserved as historical evidence. They are superseded for campaign-launch planning by the 003E nine-scenario matrix, paired H/I design and fresh fingerprint. No prior calibration files are deleted or overwritten.

Future full-campaign command (planning only; do not run without separate owner authorization):

```sh
.venv/bin/python -m src.exp_sim.campaign \
  --replicates 10000 --customers 25000 --seed 20261113 \
  --margin-bootstrap-reps 1000 --block-size 500 \
  --max-seconds 21600 --scenario-timeout-seconds 21600 \
  --memory-limit-mib 1536 \
  --output-dir .local/exp-sim-output/EXP-SIM-003E/full-10000
```

Resume command for each subsequent approximately six-hour stage:

```sh
.venv/bin/python -m src.exp_sim.campaign \
  --replicates 10000 --customers 25000 --seed 20261113 \
  --margin-bootstrap-reps 1000 --block-size 500 \
  --max-seconds 21600 --scenario-timeout-seconds 21600 \
  --memory-limit-mib 1536 \
  --output-dir .local/exp-sim-output/EXP-SIM-003E/full-10000 --resume
```

Before every resume, confirm the manifest fingerprint equals `19c52e86b2328d97bcce14229ce3b4efa4f8d2e3f96a1473b8822e4e9b31965b`, completed block ranges are contiguous and checksums validate. Do not change scenario definitions after the first full-campaign block. The 1.5 GiB guard is sampled RSS rather than an OS-enforced hard limit. The 003E pilot provides a fresh runtime estimate; prior timing estimates should not be carried forward without adjustment.

## Interpretation

`generate_trial` returns a `SyntheticTrial` with separate `.records` (analyst-visible trial information) and `.truth` (simulation-only scoring information). `analyze_trial` and the decision engine accept only `.records`; hidden outcome states and the missingness-mechanism label cannot affect a decision. Monte Carlo compares estimates and decisions with `.truth` only in its evaluation layer.

Primary analysis is assignment-based Newcombe RD among resolved outcomes, targeting the all-randomised ITT under its stated resolution assumptions. It is not automatically unbiased under treatment-dependent missingness. Diagnostics use observable completeness, arm differences and ascertainment-rule parity. The preapproved plausible-departure sensitivity range remains mandatory; worst/best bounds are descriptive only.

Pre-Day-21 opt-outs only affect eligibility. Post-randomisation opt-out events and complaints are separately generated; treatment effects apply only to delivered customers, while rates are compared by randomized assignment. Day-90 provisional adoption and Day-180 confirmation/rollback are separate states. Conversion significance alone cannot authorize adoption, and insufficient Day-180 financial records trigger rollback from provisional expansion.

Day-180 uses the same synthetic customers and correlated purchase process as Day-90. It is later follow-up, not an independent replication or independent safeguard. B and G share commercial assumptions and Day-90 effect; only the Day-180 effect differs. B has a persistent population-level cumulative risk difference, not necessarily the same individuals making persistent incremental purchases. G is a hypothetical purchase-acceleration case whose Day-90 probability difference is offset by catch-up by Day 180. C uses 1.5% balanced random missingness; D has equal base missingness by arm but missingness depends on hidden purchase outcomes, so equal base rates do not guarantee observable parity diagnostics pass. E's hypothetical delivered-customer harms produce assigned-arm risk differences above the prespecified guardrail margins.

`SeedSequence.spawn` gives distinct reproducible replicate and component streams. Passing the same `SeedSequence` to `generate_trial` is repeatable; the generator clones its immutable seed identity before spawning. Monte Carlo probabilities include plug-in MCSE, effective denominators and Wilson intervals, which remain informative when a smoke estimate is zero. Tipping-point distance output includes its grid resolution. The number of bootstrap repetitions used for each margin estimate is reported; use at least 1,000 for operating-characteristic campaigns. No synthetic range, parameter or run grants owner approval for a real experiment.

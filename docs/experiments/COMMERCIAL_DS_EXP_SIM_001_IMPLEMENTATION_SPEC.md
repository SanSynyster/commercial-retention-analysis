# EXP-SIM-001/002 — Synthetic Implementation Specification

**Scope:** synthetic-only generator, analysis and Monte Carlo validation. No customer/source data, CRM, or experiment execution.

## Precedence

1. EXP-SAP-004 governs its amended topics: plausible-departure tipping sensitivity and unapproved-range fallback; guardrail assurance as a pre-launch planning gate; order-status clarification/supersession; and same-day ambiguous orders as non-events.
2. EXP-SAP-003 governs otherwise: all-randomised ITT risk difference; resolved-outcome Newcombe interval/test; observable resolution diagnostics and assumptions; descriptive worst/best bounds; complaint/opt-out risk-difference upper-bound gates; margin and 180-day rollback requirements.
3. EXP-DESIGN-002 governs remaining definitions, including one-time customer assignment at t0, symmetric Day-21 eligibility, 90-day outcome convention, and BAU parity.

## Simulator and analyst layers

`SyntheticTrial.records` contains only analyst-visible columns. `SyntheticTrial.truth` separately carries potential outcomes, actual DGP mechanism, finite-population SATE and population parameters for Monte Carlo scoring. The analysis and decision functions accept only the analyst-visible DataFrame and never inspect simulator truth. Hidden labels cannot change a decision when records are held constant. The evaluator may compare analysis outputs with simulator truth after each replicate.

The DGP uses explicit independent SeedSequence substreams for assignment, eligibility, outcomes, delivery, guardrails, resolution, administration, margin and bootstrapping. Monte Carlo replicates use `SeedSequence.spawn`; each trial gets distinct child streams. Results are deterministic for a fixed configuration and serial campaign order.

## Synthetic trial rules

Customer IDs and purchase outcomes are entirely artificial. Eligibility is computed from assignment-independent pre-Day-21 variables: no earlier repeat, no pre-Day-21 opt-out and operational contactability. The configurable eligible treatment effect applies only to eligible treated customers. Under this DGP, population ITT RD is `P(eligible) × effect among eligible`; the evaluator separately records the realised finite-population SATE. A null scenario sets the eligible effect to zero.

Pre-Day-21 opt-out status is used only for eligibility. Post-randomisation opt-out events are a separate synthetic outcome and are not formed by OR-ing the pre-Day-21 flag. Complaint and post-randomisation opt-out harm effects apply only to customers whose intervention was delivered; guardrail estimates remain ITT by randomised assignment. Baseline event probabilities are specified on the full simulated population. A Gaussian copula option controls complaint/opt-out association.

Outcome resolution mechanisms, including outcome-dependent missingness, exist only in simulator truth and affect generated observed/missing values. The analyst sees completeness by arm, differential missingness and ascertainment-rule parity only. A reviewer-approved-assumption input plus observable diagnostics gates interpretation; the program does not use the known synthetic mechanism to decide. Thus MNAR scenarios can appear to pass/adopt if the observed diagnostics and frozen illustrative departure range permit it; the evaluator must then score incorrect adoption against truth.

## Statistical analysis and decisions

The sole primary estimator is the assignment-based resolved-outcome Newcombe hybrid-score risk difference, treatment minus control, with the interval-dual two-sided 5% test. The target remains the all-randomised ITT RD and relies on the specified missingness assumptions; resolved-outcome analysis is not inherently unbiased. The accepted EXP-SAP-004 departure sensitivity is retained. Worst/best bounds are descriptive only. No approved sensitivity range means `INCONCLUSIVE / NOT AUTHORISED`.

The Day-90 record separates conversion evidence, sensitivity robustness, ascertainment, margin completeness/viability and experience guardrails. An uninformative guardrail is `INCONCLUSIVE`; a definitive harm rule can be `FAIL`. No outcomes in both arms or no resolved outcomes are inconclusive. Day-90 provisional adoption requires all gates to pass and retains a holdout. A separate Day-180 assessment confirms or rolls back; missing/inadequate required financial records at Day 180 trigger rollback. The later state does not rewrite the recorded Day-90 decision.

## Operational protections

Same-day split orders that do not qualify as a repeat remain resolved non-events; a secondary classification sensitivity is calculated only among resolved customers. First-order status errors are retained in ITT; a flagged-record exclusion is reported only as a sensitivity. There are no discretionary post-randomisation exclusions.

The package has no source-data readers. Output writing is limited to `.local/exp-sim-output/` and rejects paths associated with private/source outcomes. Private experiment-design roots are ignored by a narrow `.gitignore` rule; synthetic results are likewise ignored.

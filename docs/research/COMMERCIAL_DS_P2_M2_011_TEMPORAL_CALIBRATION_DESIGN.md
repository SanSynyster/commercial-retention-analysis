# M2-011 — Temporal Robustness and Calibration Design

## Recommendation

Use the existing frozen Model B (RFM) and Model C (11-feature) as fixed scorers and conduct a **predeclared, explicitly exploratory sequential backtest** over the already-used July–November 2011 test period. Keep the published July–November metrics intact. Add monthly diagnostics for ranking, probability accuracy and targeting stability, and simulate a one-parameter, lagged intercept adjustment for Model C. This can establish whether a simple update is worth testing; it cannot provide independent confirmation or deployment evidence because the same holdout has already been examined and only three later calibration-evaluation months are available.

Do not refit either purchase model, use test-period outcomes contemporaneously, or tune a calibration method to these results. A confirmatory calibration claim requires a new later time period with mature outcomes.

## Research questions

1. How do monthly prevalence, discrimination, probability error and targeting precision/lift vary across July–November 2011?
2. Does a lagged intercept-only adjustment improve later-month probability accuracy as prevalence changes?
3. Is Model C's ranking stable month to month and does it add practically meaningful ranking value over Model B at 5%, 10% and 20% capacity?

These are observational prediction questions. Neither ranking nor calibration estimates the incremental effect of contacting a customer.

## Data, fixed models and what is already known

Use only the verified M2-004 monthly snapshot dataset, its matching manifest and the existing M2-008 model and test-prediction artifacts. Preserve the 365-day feature history, 30-day outcome, eligibility, source coverage rules, 11-feature order and M2-007 train/test split. Keep the trained Model B and C fixed. The base models were fitted on January–June 2011 labels available by 1 July 2011; their July–November predictions are out of time relative to those fits.

Already reported and independently reproduced in M2-008/M2-009: aggregate test ROC-AUC, average precision, Brier score and calibration diagnostics; monthly prevalence and ROC-AUC; pooled 5%, 10% and 20% capacity precision/lift; and pooled prediction summaries. M2-009 also noted monthly prediction means and seasonal underprediction. These remain completed baseline results, not new findings.

New summaries proposed here are month-specific average precision, Brier score, calibration-in-the-large, capacity precision/lift, paired RFM-versus-full ranking differences, and a sequential lagged-calibration simulation. They are exploratory analyses of the same already-inspected holdout, not a fresh confirmatory test.

## Experimental timeline and label availability

At a decision timestamp `T`, a snapshot's label is usable for fitting a later calibrator only when its complete outcome window is observable and `outcome_window_end_exclusive <= T`. In this dataset the window is `[T, T + 30 days)`, so its label becomes available at `T + 30 days` (subject to source coverage). Unknown and immature rows are never used. Do not infer inactivity through a source coverage gap.

The primary sequential calibration exercise starts at the 1 September decision point, after two preceding test months have matured. Refit only the calibration intercept at each boundary, using baseline Model C predictions and labels from prior test snapshots whose labels are mature by that boundary:

| Decision boundary | Calibration snapshots available from prior test months | Evaluation month | Approximate evaluation snapshots |
| --- | --- | --- | ---: |
| 1 September 2011 | July and August (8,640) | September | 4,324 |
| 1 October 2011 | July–September (12,964) | October | 4,364 |
| 1 November 2011 | July–October (17,328) | November | 4,344 |

Counts are based on the M2-008 monthly table; implementation must verify availability row by row from the actual exclusive outcome end and coverage fields rather than relying on the table. July labels mature by 31 July; August by 31 August; September by 1 October; October by 31 October. Thus every calibration row above is available before the month it calibrates. July and August remain uncalibrated warm-up months and are not included in the sequential calibrated-versus-uncalibrated primary comparison.

Monthly decision anchors are not always 30 days apart. Fixed 30-day label windows can overlap when adjacent anchors are fewer than 30 days apart (for example, February to March), so repeated rows and outcomes are dependent. The July–November anchors are 31, 31, 30 and 31 days apart; their outcome windows are adjacent or separated, not overlapping. Preserve all snapshot records and account for customer clustering in uncertainty summaries.

## Calibration method

Use one simple candidate: **intercept-only logistic recalibration with slope fixed at one**. For each eligible historical row with frozen Model C probability `p`, fit scalar `delta` on the prior matured calibration pool by maximum likelihood:

`q = logistic(logit(p) + delta)`

This corrects a lagged prevalence/level shift while preserving the exact within-month ranking and therefore leaves ROC-AUC and capacity ordering unchanged. It cannot correct a slope error or changing feature/outcome relationships. If probabilities are at a numerical boundary, clip only for the logit calculation using a fixed documented epsilon (recommend `1e-6`); do not alter the frozen raw predictions. If the calibration pool lacks both outcome classes or optimization is non-finite, mark that month's adjustment unavailable and report raw Model C results; do not switch methods.

Do not use in-sample January–June predictions to fit calibration: they are resubstitution scores from the same rows used to fit the base model. Do not use July/August labels to calibrate predictions for those same months. Do not include a row until its own label is mature. Do not fit an isotonic or flexible slope model on these limited months.

## Evaluation and comparison hierarchy

**Primary exploratory calibration comparison:** on September–November rows, compare frozen raw Model C probabilities with sequentially adjusted probabilities using paired snapshot-weighted Brier score difference (`adjusted − raw`, lower is better). Report the point difference and customer-cluster bootstrap interval. Also report monthly Brier score and calibration-in-the-large, defined as observed prevalence minus mean predicted probability, before and after adjustment. Show the calibration pool sizes and fitted `delta` at each date. A lower Brier score alone is not enough: discuss whether monthly calibration-in-the-large improves without a material deterioration in any evaluation month.

**Temporal robustness and ranking (exploratory):** report, by month for Models B and C, ROC-AUC, average precision, prevalence, Brier score, calibration-in-the-large, and precision/lift at 5%, 10% and 20% of that month's eligible mature rows. Use `ceil(capacity × monthly row count)` and the already specified tie rule. Compare C minus B AUC, average precision and capacity precision descriptively; do not imply significance or select a model after seeing these comparisons. Intercept adjustment does not change ranks, so its AUC and capacity ranking should equal raw Model C; verify this as an integrity check.

For uncertainty in row-weighted metrics, use paired resampling of customer clusters, retaining all that customer's rows in each relevant calibration and evaluation period and preserving sampled cluster multiplicity. For the sequential calibration comparison, resample the full timeline by customer, refit each date's scalar `delta` using only the resampled prior mature rows, and evaluate on the resampled later month. Report valid/omitted replicates and use a percentile interval. This captures within-customer dependence conditional on these months; it does not represent independent temporal replication. With only three calibrated evaluation months, monthly variation should be shown directly, not summarized as if there were many independent periods.

No new threshold selection, model tuning, or post-hoc subgroup claims. Do not use row-level significance tests that treat repeated customer-month observations as independent.

## What can and cannot be concluded

The current timeline is sufficient for a **leakage-respecting historical simulation**: July/August mature labels can inform September, and the calibration pool expands for October and November. It is not sufficient for an independent confirmatory calibration study: the holdout outcomes and performance have already been inspected, the simulation has only three evaluation months, the data end shortly after the test period, and all observations come from one historical retail setting. Customer bootstrap uncertainty cannot fix the lack of independent future periods. Any apparent improvement should motivate prospective validation, not a claim that recalibration will remain beneficial.

The sequential intercept specifically addresses a prevalence-level shift. It cannot establish calibration under a new season, customer mix, product assortment or source population. Ranking lift is descriptive of natural purchasing propensity and is not CRM uplift. A prospective campaign needs randomised treatment/control assignment to estimate incremental impact.

## Exact next implementation milestone

Implement **M2-012: exploratory sequential calibration and monthly robustness diagnostics** using the frozen M2-008 predictions and verified dataset only. Add a small analysis entry point and focused tests for label availability at each boundary, maturity/coverage filtering, calibration-pool chronology, intercept-only rank preservation, customer-cluster bootstrap multiplicity, and reproducibility. Produce aggregate-only output outside Git for row-level predictions and a concise report in `docs/research/`. Do not refit Models B/C. Before any future confirmatory claim, obtain a new later observation period with mature 30-day labels and predeclare the evaluation before inspecting its outcomes.

No unresolved decision is needed to conduct this bounded exploratory milestone. The owner should approve a new data source or prospective collection before any claim of independent temporal or calibration validation.

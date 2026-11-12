# M1-006 — Acquisition Look-back and Day-21 Temporal Feasibility

## Executive finding

The approved 12-month acquisition proxy leaves a usable but narrow Day-21 cohort. From 5,852 identifiable canonical customers, 1,613 have a full 12-month qualifying-history burn-in; 1,324 are Day-21 eligible. Of those, 838 have fully mature 90-day labels: 312 positive and 526 negative (37.23% positive). A simple chronological baseline is narrowly feasible with a July 1, 2011 as-of cutoff and a later mature test window, but the available sample and short test period do not support tuning, subgroup claims, or strong generalisation claims.

This assessment uses the verified M1-004 customer cohort at `source_data/uci_online_retail_ii/day21_customer_cohort_m1_004.parquet`; it applies the look-back as a read-only filter and does not alter that cohort or source data. No model was trained.

## Contracts and acquisition rule

The owner-approved decision is recorded in `docs/recovery/COMMERCIAL_DS_001_DECISION_LOG.md` (P-17 / D-002-07): use a 12-month acquisition proxy, retain observed-look-back metadata, disclose the pseudo-boundary, and do not claim first-ever acquisition. The 6- and 9-month options in `docs/recovery/COMMERCIAL_DS_002_DECISION_PROPOSAL.md` are sensitivities, not replacements for the primary population. Older proposed/open-question wording in `docs/recovery/COMMERCIAL_DS_001_DATA_CONTRACTS.md` and the earlier supersession notes is superseded by that approval and the owner's current clarification.

The verified corrected-V2 source begins at `2009-12-01 07:45:00`. The primary burn-in threshold is therefore the same calendar date one year later, `2010-12-01 07:45:00`; acquisition-proxy customers have their first qualifying timestamp at or after that boundary. The earliest qualifying timestamp actually present among those customers is `2010-12-01 12:36:00`. This establishes 12 months of observed qualifying-history opportunity, not a known first-ever purchase; pre-source activity remains unobserved.

Canonical qualifying purchases remain those defined by the Phase 1 corrected-V2 rules: identified customer, qualifying merchandise lines, and canonical customer/invoice occasion grouping. The M1-004 timestamp rule uses the earliest valid qualifying line timestamp in an occasion; repeat purchase is on a strictly later qualifying calendar date. The Day-21 rule and maturity definition are documented in `src/day21_cohort.py` and the M1-004 implementation report.

## Population and label accounting

Counts below use the Day-21 decision timestamp and the approved outcome interval `(decision, decision + 90 days]`. A complete label requires the full deadline to be observable. A positive can be observed before full maturity; such rows are known positives but are kept separate from the fixed-horizon evaluation cohort.

| Acquisition-history / Day-21 accounting | Customers |
| --- | ---: |
| Identifiable canonical customers | 5,852 |
| Insufficient 12-month observed qualifying history (first qualifying timestamp before threshold) | 4,239 |
| Sufficient 12-month observed qualifying history | 1,613 |
| Sufficient-history customers without observable Day-21 point | 94 |
| Sufficient-history customers repeated by Day 21; ineligible | 195 |
| Sufficient-history Day-21 eligible | 1,324 |
| **Eligible total without look-back restriction** (comparison only) | **4,947** |

The 12-month eligible cohort reconciles as follows:

| Outcome status among 1,324 eligible | Customers |
| --- | ---: |
| Fully mature positive | 312 |
| Fully mature negative | 526 |
| Observed positive, incomplete 90-day horizon | 168 |
| Unknown / immature, no observed positive | 318 |
| **Total** | **1,324** |

Thus 838 labels (312 positive, 526 negative) are fully mature. The complete-case positive prevalence is `312 / 838 = 37.23%`. There are 1,006 known outcomes if partial-horizon observed positives are included; those partial positives are not part of the primary fixed-horizon evaluation set. Unknowns are not negatives.

The 4,239 insufficient-history customers are outside the approved primary acquisition-proxy population. Their later observed Day-21 outcomes do not repair missing acquisition look-back and must not be pooled into the primary training set. The 94 sufficient-history customers with no observable decision point and the 195 already repeated by Day 21 are not eligible predictions.

Eligible decision months are concentrated in the observed acquisition period: Dec-2010 46; Jan-2011 40; Feb 75; Mar 135; Apr 135; May 106; Jun 93; Jul 78; Aug 101; Sep 88; Oct 207; Nov 174; Dec 46. Later rows are predominantly immature: Oct–Dec contribute 427 of 1,324 eligible customers, but none has a fully mature 90-day outcome by source end. Overall 486 eligible customers have incomplete horizons (168 observed partial positives and 318 unknowns).

## Chronological cutoff assessment

For each cutoff `c`, the training population is acquisition-proxy eligible customers with decision time before `c`. Complete training labels are only those whose 90-day deadline is at or before `c`; partial positives observed by `c` are shown separately and are not used in the complete-case primary baseline. “Unresolved at cutoff” means neither a complete label nor an observed positive was available as of `c`; eventual outcomes are shown in parentheses only to describe the retrospective source.

The test window in each row is eligible customers with decision times at/after `c` and no later than the last decision timestamp with a complete 90-day horizon (approximately `2011-09-10 12:50`). Test labels are fully mature at source end. The 486 later eligible customers are excluded from fixed-horizon testing as immature.

| As-of cutoff | Prior eligible | Training labels available by cutoff (mature + / −) | Partial positives known by cutoff | Unresolved at cutoff (eventual + / −) | Mature test n (+ / −) | Test prevalence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2011-03-01 | 161 | 0 (0 / 0) | 11 | 150 (30 / 120) | 677 (271 / 406) | 40.0% |
| 2011-04-01 | 296 | 46 (4 / 42) | 30 | 220 (52 / 168) | 542 (226 / 316) | 41.7% |
| 2011-05-01 | 431 | 85 (16 / 69) | 53 | 293 (70 / 223) | 407 (173 / 234) | 42.5% |
| 2011-06-01 | 537 | 169 (41 / 128) | 81 | 287 (57 / 230) | 301 (133 / 168) | 44.2% |
| **2011-07-01** | **630** | **304 (90 / 214)** | **80** | **246 (45 / 201)** | **208 (97 / 111)** | **46.6%** |
| 2011-08-01 | 708 | 444 (143 / 301) | 68 | 196 (35 / 161) | 130 (66 / 64) | 50.8% |

A January 1, 2011 split, as proposed before applying acquisition look-back, has no complete 90-day training labels available: the earliest eligible decision is in late December 2010 and its label deadline is in March 2011. This is the acquisition-look-back defect identified by independent review.

**Recommended initial split:** freeze July 1, 2011 as the as-of cutoff; fit a predeclared, low-complexity interpretable baseline only on the 304 mature labels (90 positive, 214 negative), then evaluate once on the 208 mature later decisions (97 positive, 111 negative). Do not use partial positives to augment training: their label observation is outcome-dependent and incomplete follow-up creates asymmetric ascertainment. The 246 unresolved pre-cutoff rows were not label-available at the cutoff and must not be treated as training negatives. The test set is short and prevalence rises from 29.6% in mature training to 46.6% in test, indicating material calendar drift/seasonality. This supports a feasibility baseline, not tuning or a robust performance claim. A separate validation partition would leave too little data; do not tune against the test set.

## Feasibility conclusion and alternatives

The 12-month primary question is **statistically and operationally feasible only for a small, predeclared baseline with a single chronological test**. It is not adequately supported for broad model comparison, hyperparameter selection, subgroup analysis, or stable performance estimation. The small training set is the binding constraint even though the overall mature eligible count is 838.

Scientifically defensible paths if stronger evaluation is required:

1. **Preferred:** extend historical source coverage backward, then retain the approved 12-month qualifying look-back and the same Day-21 estimand. This increases acquisition-proxy and chronological training support without changing the target population definition.
2. **Different research population, owner approval required:** analyze first-observed customers with insufficient look-back as a separately named left-censored population. Do not describe them as acquisition-proxy customers or pool them into the primary estimate.
3. **Sensitivity only:** report predeclared 9- or 6-month look-back cohorts alongside the 12-month primary result. This changes the observed-history criterion and cannot replace the approved primary population merely to increase sample size.

A related historical review, `docs/recovery/COMMERCIAL_DS_003_STAGE_B1_INDEPENDENT_REVIEW.md`, recommends excluding any identified source activity before first qualifying occasion (including non-qualifying categories). That stricter any-activity rule was marked pending owner decision and is distinct from the approved 12-month qualifying-history burn-in used here. Applying it to the primary population requires explicit owner approval; it was not silently imposed.

## Candidate Day-21 features and leakage boundary

This report assesses cohort feasibility, not features. Candidate initial features should be derived only from qualifying information observable by the decision timestamp: first qualifying occasion merchandise value, quantity and product diversity; count of qualifying occasions on the first purchase date; and first-purchase weekday/month. They should be calculated from the existing canonical line/occasion definitions and checked with a truncation test. Country can be considered only after a documented, reliable customer-level aggregation rule. Returns/cancellations require a supported event-time definition; full-history return state or post-cutoff records must not be used. Lifetime totals, later purchase history, outcome maturity, and follow-up length are not Day-21 predictors.

## Limitations and owner decision

- The acquisition flag is a 12-month observed qualifying-history proxy, not a verified first-ever acquisition date; the source is left-censored before Dec-2009 and unidentified customers cannot be linked.
- The 90-day outcome is right-censored at the actual source boundary. Immature rows remain unknown; no activity is inferred during gaps or after the source end.
- Test support is just 208 customers over a short calendar window, with evident prevalence drift.
- **Owner decision if the primary rule is to change:** whether non-qualifying identified activity within/before the qualifying-history burn-in should disqualify the acquisition proxy. Existing review calls that alternative pending; current calculations follow the approved qualifying-purchase look-back.

## Recommended next action

Proceed to a scoped M1 update that applies the approved 12-month eligibility filter and reports the July 1 as-of / mature later-test split, while preserving unknown and not-yet-available labels. Keep the first evaluation predeclared and simple. Before changing the acquisition definition to exclude any-category prior activity, obtain owner approval. If the goal is a more statistically stable evaluation than this narrow baseline, recover a longer historical transaction span while retaining the 12-month rule.

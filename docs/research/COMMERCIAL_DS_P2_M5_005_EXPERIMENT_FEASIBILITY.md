# M5-005 — CRM Experiment Feasibility Dashboard

## Result

Replaced the Experiment Feasibility placeholder with an interactive planning page. It calculates hypothetical scenarios in memory using the frozen M4 functions; it does not use customer data, estimate an effect, launch a campaign or change the M4 research outputs.

## Design represented

The page describes the proposed single-wave experiment among established customers who meet current contact eligibility requirements. The primary M4 design selects the top 10% by 365-day qualifying purchase-date frequency, using an outcome-independent prespecified tie-break, then persistently randomizes customers 1:1. Treatment is assigned one non-discount study email; control receives no study email, while both arms continue comparable business-as-usual treatment. The primary outcome is 30-day net customer contribution margin, analyzed by intention to treat as the difference in mean outcomes by assignment.

This is a proposed design only. No experiment has been launched and no causal CRM uplift has been measured.

## Reused calculations and conventions

`src/experiment_feasibility_metrics.py` is a small presentation adapter. It calls the existing M4 functions in `src/crm_pilot_feasibility.py`:

- `allocate_enrollment`: `ceil(eligible × capacity)` enrollment; for scenario arithmetic an odd extra customer goes to treatment.
- `mean_difference_mde`: normal-approximation MDE for the treatment-control mean difference, two-sided α=0.05 and 80% power.
- `commercial_scenarios`: gross increment less one contact cost per treatment assignment, total contribution, cohort-average contribution and break-even gross increment.
- `capacity_sensitivity`: recomputes allocation and MDE at the M4 capacities 10%, 20%, 50% and 100%.

For a live trial, randomization determines the arm assignment; the odd-extra convention is only the calculator's deterministic scenario allocation. Costs are charged to every treatment assignment according to M4 arithmetic, even if delivery fails.

## Inputs and outputs

All input values are visibly marked hypothetical. Defaults are existing M4 grid values: 10,000 eligible customers, 10% enrollment, £50 30-day outcome SD, £1 gross increment per treatment assignment and £0.20 contact cost per treatment assignment. Population is bounded from 100 to 1,000,000; the other controls use the frozen M4 scenario grids, with a £0.20 gross-increment choice added to make break-even at the default contact cost directly selectable.

At those defaults the page shows 1,000 enrolled customers (500 treatment, 500 control), an approximate MDE of £8.86 per randomized customer, net hypothetical ITT effect of £0.80 per treatment assignment, total incremental campaign contribution of £400, average net contribution of £0.40 per enrolled customer and a £0.20 break-even gross increment. The net ITT contrast (`g − c`) is intentionally distinct from total contribution divided by all enrolled customers (`n_t × (g − c) / n_enrolled`). The latter is a cohort-average budget quantity and is not compared with MDE.

The sensitivity chart uses M4's capacity formula at the selected eligible population and outcome SD. For the default 10,000 population and £50 SD, the MDE is approximately £8.86 at 10% capacity, £6.26 at 20%, £3.96 at 50% and £2.80 at 100%. Wider capacities add lower-frequency customers, change the selected population and potentially change the estimand; the 10% design remains the primary M4 proposal.

The page directly compares the magnitude of the assumed net ITT effect (`|g − c|`) with the displayed MDE. Below MDE, the text says the sample is not designed for 80% power to detect an effect of that magnitude and that positive hypothetical contribution is not adequate power. At or above MDE, it says the assumption meets the approximate threshold while statistical significance is not guaranteed. For nonnegative effects this reuses M4's `net_effect_at_or_above_approx_80pct_power_mde` comparison flag; negative effects are compared by absolute magnitude for the two-sided interpretation. The comparison uses the arm-mean ITT contrast, never the cohort-average contribution per enrollee.

## Limitations and operational decisions

No causal CRM uplift has been measured. Current eligibility, consent, contactability, customer/entity linkage, contribution margins, send costs, contact suppression rules and return/adjustment lag are unknown. Contact displacement and comparable business-as-usual communications need operational decisions. The hypothetical SD is not measured from the historical retail data. MDE depends on that assumed variability and a normal approximation that may be affected by skew, outliers, unequal variance, household clustering and incomplete finance linkage. MDE is a planning quantity, not expected campaign uplift, a realized significance result or a rollout decision.

Before any launch, CRM and finance owners must supply eligibility and consent rules, the randomization unit, current margin and cost definitions, outcome maturity, a minimum worthwhile ITT effect, budget and harm guardrails.

## Verification

The new page tests agree with the M4 reference example at 10,000 eligible, 10% capacity, £50 SD, £1 gross increment and £0.20 cost. They cover allocation, MDE, economic decomposition, break-even, input validation, sensitivity values, rendered controls, capacity updates and below/above/break-even/negative effect interpretations. No dependency or data bundle was added, and the frozen M4 calculator was not modified.

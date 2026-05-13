# Incrementality Simulation Summary

## 1. Purpose

This simulation estimates whether the proposed second purchase accelerator campaign could create positive commercial value after accounting for natural repeat behaviour, campaign cost, discount cost, contribution margin, and cannibalisation risk.

The goal is not to claim measured campaign impact. No real exposed/control campaign data exists in the public dataset. The goal is to define the commercial decision logic that should be used once the CRM experiment is launched.

Core question:

> How much incremental second purchase uplift is required before the campaign should scale?

---

## 2. Baseline Context

The model uses the current retention analysis as the behavioural baseline.

Current observed inputs:

- Valid customers: 4,338
- Repeat customers: 2,845
- One-time customers: 1,493
- Observed second purchase conversion: 65.6%
- Scenario audience proxy: 1,493 one-time customers

The one-time customer count is used as a practical MVP audience proxy. In a live business setting, this would represent future customers who become eligible after first purchase and have not repeated by the CRM trigger point.

---

## 3. Model Logic

The model compares expected treatment behaviour against a control baseline.

Core calculation flow:

1. Estimate incremental conversion.
2. Convert incremental conversion into incremental second orders.
3. Estimate gross incremental revenue using average second-order value.
4. Convert revenue into gross margin using a contribution margin assumption.
5. Reduce value for estimated pull-forward/cannibalisation.
6. Subtract discount cost.
7. Subtract campaign operating cost.
8. Evaluate net incremental value and break-even uplift.

The model intentionally separates gross uplift from net incremental value. This prevents the campaign from being judged successful only because short-term revenue increased.

---

## 4. Scenario Results

| Scenario | Incremental Conversion | Incremental Orders | Gross Incremental Revenue | Net Incremental Value | Break-Even Uplift | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Conservative | 1.4pp | 21.2 | GBP 9,384 | GBP 1,694 | 0.1pp | Test cautiously |
| Base | 4.4pp | 65.9 | GBP 29,255 | GBP 8,393 | 0.1pp | Scale candidate |
| Optimistic | 7.4pp | 110.7 | GBP 49,127 | GBP 19,585 | 0.0pp | Scale candidate |

Interpretation:

- The conservative case remains positive, but the assumed pull-forward rate is high at 40%, so it should be treated cautiously.
- The base case creates positive net incremental value after estimated costs and cannibalisation.
- The optimistic case is a strong scale candidate if guardrail metrics remain healthy.

---

## 5. What This Means Commercially

The CRM campaign should not be scaled simply because treatment conversion is higher than control. It should scale only if the treatment effect survives the commercial value test.

The most important commercial readout is:

> Positive behavioural uplift must translate into positive net incremental value after discounting, operating cost, and pull-forward risk.

In the current scenario setup, the base case suggests that a second purchase accelerator can be economically attractive if it achieves roughly a 4.4 percentage point conversion uplift versus control and does not create excessive cannibalisation.

---

## 6. Cannibalisation Readout

Cannibalisation is the main risk.

The campaign may generate purchases earlier without creating much additional long-term demand. That still may be valuable if earlier repeat activity improves cash flow, customer momentum, or later purchase frequency, but it should not be reported as fully incremental revenue.

Recommended interpretation by measurement window:

- If treatment wins at 30 days but control catches up by 90 days, the campaign mainly accelerates timing.
- If treatment maintains a conversion or revenue gap at 90 days, the case for true incrementality is stronger.
- If uplift is positive but margin is weak, the campaign should be redesigned before scaling.

---

## 7. Scale Criteria

The campaign should be considered a scale candidate only if all conditions are met:

- Treatment second purchase conversion is higher than control.
- Incremental conversion exceeds break-even uplift.
- Net incremental value is positive.
- Pull-forward/cannibalisation does not erase the 90-day treatment gap.
- Discount cost does not create margin erosion.
- Guardrails such as unsubscribe rate, complaint rate, and refund rate remain acceptable.

Recommended decision framework:

- Scale if net incremental value is positive and guardrails are healthy.
- Iterate if behavioural uplift is positive but economics are weak.
- Do not scale if uplift is mainly cannibalised or discount-led.

---

## 8. Outputs Created

The simulation notebook creates two processed outputs:

- `data/processed/incrementality_scenarios.csv`
- `data/processed/incrementality_sensitivity.csv`

These can be used in dashboarding or final project documentation to show the economic logic behind the CRM recommendation.

---

## 9. Strategic Recommendation

The project should move forward with a controlled second purchase accelerator test, but the campaign should only scale after exposed vs control results prove positive net incremental value.

One-line recommendation:

> Use CRM to accelerate second purchase behaviour, but evaluate success through net incremental value rather than gross uplift.

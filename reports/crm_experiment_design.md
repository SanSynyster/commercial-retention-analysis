# CRM Experiment Design: Second Purchase Accelerator

## 1. Executive Summary

The retention analysis shows that repeat behaviour is commercially important, but repeat timing is slower than ideal.

Current analytical context:

- Identifiable customers generated ~£8.9M in analytical purchase revenue.
- Repeat-order revenue represents ~79.3% of identifiable revenue.
- Repeat-customer revenue represents ~93.1% of identifiable revenue.
- Second purchase conversion is ~65.6%.
- Median time to second purchase is ~50 days.
- The top 10% of customers contribute ~61% of identifiable revenue.

The main opportunity is not simply to fix retention from a weak base. Customers already show willingness to return. The commercial opportunity is to accelerate lifecycle velocity by encouraging customers to make their second purchase earlier, while validating whether the campaign creates incremental value rather than only pulling forward purchases that would have happened naturally.

Recommended MVP test:

> Launch a controlled second purchase accelerator campaign for one-time buyers who have not repeated by day 21 after first purchase.

---

## 2. Business Problem

The business appears reliant on repeat purchasing and a relatively narrow high-value customer segment. This creates two linked challenges:

- Revenue dependency: a large share of revenue is generated after the first order.
- Lifecycle timing: the median customer who repeats takes ~50 days to make a second purchase.

If customers naturally return but do so slowly, the business may be leaving short-term revenue and customer momentum on the table. Earlier repeat activity could improve customer productivity, reduce reliance on acquisition volume, and help broaden repeat behaviour beyond the top customer decile.

The test should answer:

> Can targeted CRM engagement increase or accelerate second purchase behaviour in a commercially incremental way?

---

## 3. Test Hypothesis

Primary hypothesis:

> A targeted lifecycle CRM intervention sent around day 21 after first purchase will increase second purchase conversion and reduce time to second purchase versus a holdout control group.

Commercial hypothesis:

> The campaign will generate positive net incremental value after accounting for natural repeat behaviour, discount cost, operating cost, and cannibalisation risk.

Strategic hypothesis:

> Accelerating second purchase behaviour can improve customer productivity before the business invests more aggressively in acquisition scaling.

---

## 4. Target Audience

The MVP audience should be intentionally narrow so the test is operationally simple and analytically clean.

Eligibility criteria:

- Customer has exactly one valid order.
- Customer has a non-null `CustomerID`.
- Customer has not made a second valid order by day 21 after first purchase.
- First order has positive analytical revenue.
- Customer is contactable through the relevant CRM channel.
- Customer is not already in another conflicting promotional lifecycle campaign.

Recommended exclusions:

- Customers with refunded or cancelled first orders if operational data allows.
- Customers who unsubscribed or are not marketable.
- Customers with unresolved service issues if available.
- Customers in countries or channels where campaign execution is not supported.

Why day 21:

- It is early enough to intervene before the current ~50-day median repeat point.
- It avoids messaging immediately after purchase when natural engagement may still be high.
- It sits inside the project's recommended day 14-30 second purchase acceleration window.

---

## 5. Experiment Design

Recommended design:

- Test type: randomized controlled CRM experiment.
- Unit of randomization: customer.
- Treatment group: receives the second purchase accelerator campaign.
- Control group: receives no second purchase accelerator campaign during the measurement window.
- Split: 80% treatment / 20% control for an MVP rollout, or 50% / 50% if statistical precision is the priority.
- Trigger timing: day 21 after first valid purchase if no repeat order has occurred.
- Measurement windows: 30, 60, and 90 days after eligibility.

The control group is essential. Without a control group, the analysis cannot separate campaign impact from natural repeat behaviour.

Recommended randomization rules:

- Randomize once at eligibility.
- Keep customers in their assigned group for the full measurement window.
- Do not allow control customers to receive the same campaign later during the test window.
- Exclude customers from overlapping tests that target the same lifecycle behaviour.

---

## 6. Campaign Concept

Campaign objective:

> Encourage the second purchase earlier without creating unnecessary discount dependency.

Recommended MVP creative direction:

- Personalised follow-up based on first purchase category where possible.
- Product recommendation or complementary product prompt.
- Reminder of value proposition rather than defaulting immediately to a discount.
- Clear call to action to make a second purchase.

Recommended test treatment:

- Day 21 message: reminder/recommendation-led second purchase prompt.
- Optional day 28 follow-up: only for customers who did not open, click, or purchase.

Discount approach:

- Start with a low- or no-discount treatment if feasible.
- If discounting is required, keep it controlled and explicitly include discount cost in net incremental value.
- Avoid evaluating success only on gross revenue, because discount-led uplift can look positive while reducing contribution margin.

---

## 7. Primary KPI

Primary KPI:

> Second purchase conversion rate.

Definition:

- Percentage of eligible customers who place a second valid order within the measurement window.

Formula:

```text
Second purchase conversion = customers with second valid order / eligible customers
```

Primary comparison:

```text
Treatment second purchase conversion - Control second purchase conversion
```

The primary KPI should be measured at 30, 60, and 90 days. A shorter window captures acceleration. A longer window helps identify whether the campaign created incremental repeat behaviour or mainly pulled purchases forward.

---

## 8. Secondary KPIs

Secondary KPIs:

- Median days to second purchase.
- Mean days to second purchase.
- Repeat-order revenue per eligible customer.
- Average order value of second purchase.
- Purchase frequency during the measurement window.
- Share of customers making a third purchase within 90 days, if sample size allows.

Interpretation guidance:

- Higher conversion and lower days to second purchase is the strongest positive signal.
- Lower days to second purchase without higher 90-day conversion may indicate timing acceleration rather than incremental demand.
- Higher revenue with lower margin may not be commercially attractive if discounts are used.

---

## 9. Commercial KPIs

The experiment should evaluate commercial value, not only behaviour.

Recommended commercial KPIs:

- Incremental orders.
- Incremental revenue.
- Incremental revenue per eligible customer.
- Estimated contribution margin.
- Discount cost.
- Campaign operating cost.
- Net incremental value.
- Revenue efficiency.

Core formulas:

```text
Incremental conversion = treatment conversion - control conversion
```

```text
Incremental orders = eligible treatment customers * incremental conversion
```

```text
Incremental revenue = incremental orders * treatment second-order AOV
```

```text
Net incremental value = incremental gross margin - discount cost - operating cost
```

The business should only scale the campaign if the incremental economics are positive and the result is not explained entirely by pull-forward behaviour.

---

## 10. Guardrail Metrics

Guardrails protect against a campaign that improves short-term revenue while damaging customer quality or margin.

Recommended guardrails:

- Unsubscribe rate.
- Spam or complaint rate.
- Discount redemption dependency.
- Gross margin erosion.
- Return/refund rate after campaign purchase.
- Customer service contact rate, if available.
- Long-term purchase rate after the second order.

Decision rule:

> Do not scale the campaign if primary KPI uplift is positive but guardrails show material customer experience, deliverability, or margin deterioration.

---

## 11. Incrementality and Cannibalisation

The main measurement risk is confusing gross uplift with incremental value.

Possible outcomes:

- True incrementality: treatment customers purchase and control customers do not.
- Timing acceleration: treatment customers purchase earlier, but control customers catch up later.
- Cannibalisation: the campaign uses a discount on customers who would have purchased anyway.
- Negative economics: revenue increases but margin falls after discount and campaign costs.

How to detect timing acceleration:

- Compare treatment vs control at 30 days.
- Compare treatment vs control again at 60 and 90 days.
- If treatment wins at 30 days but the gap closes by 90 days, the campaign likely accelerated timing more than it created new demand.
- If treatment maintains a conversion or revenue gap through 90 days, the case for incrementality is stronger.

Recommended interpretation:

> Acceleration is still valuable if earlier cash flow, customer momentum, or downstream repeat behaviour improves enough to justify cost. But it should not be reported as fully incremental revenue without control-group evidence.

---

## 12. Measurement Plan

Recommended measurement windows:

- Day 0: customer becomes eligible and is randomized.
- Day 0-30: short-term activation and acceleration readout.
- Day 0-60: medium-term repeat behaviour readout.
- Day 0-90: incrementality and cannibalisation check.

Required analysis cuts:

- Treatment vs control conversion.
- Treatment vs control days to second purchase.
- Treatment vs control revenue per eligible customer.
- Treatment vs control margin proxy if available.
- Results by first-order revenue band.
- Results by customer country, if sample size allows.
- Results by first-purchase month or cohort, if sample size allows.

Minimum reporting table:

| Metric | Treatment | Control | Difference | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Second purchase conversion | TBD | TBD | TBD | Primary behavioural uplift |
| Median days to second purchase | TBD | TBD | TBD | Lifecycle acceleration |
| Revenue per eligible customer | TBD | TBD | TBD | Commercial productivity |
| Estimated margin per customer | TBD | TBD | TBD | Economic quality |
| Unsubscribe rate | TBD | TBD | TBD | Customer experience guardrail |

---

## 13. Success Criteria

The MVP should be considered successful if it meets all core conditions:

- Treatment second purchase conversion is higher than control.
- Treatment median days to second purchase is lower than control.
- Incremental revenue per eligible customer is positive.
- Net incremental value is positive after discount and operating costs.
- Guardrail metrics remain within acceptable limits.
- The treatment effect does not disappear entirely by the 90-day readout.

Recommended scale decision:

- Scale if conversion uplift and net incremental value are both positive with acceptable guardrails.
- Iterate if conversion improves but economics are weak.
- Do not scale if uplift is mainly cannibalised or driven by uneconomic discounting.

---

## 14. Operational Rollout Plan

Recommended MVP rollout:

1. Define eligible customer audience daily.
2. Randomly assign eligible customers to treatment or control.
3. Trigger treatment CRM message at day 21 after first purchase.
4. Suppress control customers from the campaign during the measurement window.
5. Track customer purchases for 30, 60, and 90 days after eligibility.
6. Report treatment vs control results using the KPI framework above.
7. Decide whether to scale, iterate, or stop.

Operational requirements:

- Reliable first purchase date.
- Reliable customer identifier.
- Valid order flag aligned to project KPI definitions.
- Campaign exposure tracking.
- Holdout/control flag.
- Purchase tracking after eligibility.
- Discount/cost tracking if incentives are used.

---

## 15. Key Risks and Mitigations

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| Natural repeat behaviour misread as campaign uplift | Customers already show repeat propensity | Use randomized control group |
| Pull-forward mistaken for incrementality | Campaign may accelerate purchases that would happen anyway | Compare 30, 60, and 90 day results |
| Discount dependency | Incentives can train customers to wait for offers | Start with low/no-discount creative where possible |
| Margin erosion | Revenue uplift may not equal profit uplift | Include discount and operating cost in net value |
| Overlapping campaigns | Attribution becomes unclear | Suppress conflicting lifecycle campaigns |
| Small sample size | Results may be noisy | Treat MVP as directional unless sample size is sufficient |
| Concentration bias | High-value customers may dominate revenue results | Report both conversion and revenue per customer |

---

## 16. Strategic Recommendation

The recommended next commercial action is to launch a controlled second purchase accelerator MVP before scaling broader acquisition or discount-led retention activity.

Rationale:

- Repeat behaviour already drives the majority of identifiable revenue.
- Second purchase conversion is relatively strong, but repeat timing is slow.
- A day 21 lifecycle trigger directly targets the gap between first purchase and the current ~50-day median repeat point.
- A holdout design allows the business to distinguish genuine incremental value from natural repeat behaviour.
- The test creates a disciplined path from analytical insight to operational CRM execution.

One-line recommendation:

> Test earlier second-purchase activation for one-time buyers, but scale only if the campaign proves incremental value beyond natural repeat behaviour and remains economically efficient.

# CRM Priority Strategy

## 1. Purpose

This report combines lifecycle segmentation, lapse-risk modelling, and second-purchase propensity scoring into one operational CRM prioritisation framework.

The goal is to answer:

> Which customers should CRM prioritise, what action should they receive, and why?

This layer turns the project from analysis into an actionable customer decision system.

---

## 2. Inputs

The CRM priority layer combines:

- `customer_segments.csv`: lifecycle segment, revenue, value flags, accelerator eligibility.
- `lapse_risk_scores.csv`: predicted 90-day lapse risk and risk band.
- `second_purchase_propensity_scores.csv`: early lifecycle second-purchase propensity score and propensity band.

Outputs:

- `crm_customer_priority_scores.csv`
- `crm_priority_summary.csv`

---

## 3. Priority Groups

| Priority Group | Customers | Revenue Share | Recommended Action |
| --- | ---: | ---: | --- |
| P1 High-Value Lapse Prevention | 22 | 4.5% | Personalised retention intervention; avoid blanket discounting |
| P2 High-Value Watchlist | 24 | 2.4% | Light-touch VIP reminder or product discovery |
| P3 Second Purchase Acceleration | 515 | 2.4% | Day 21 second purchase accelerator test |
| P4 Standard Lapse Prevention | 1,281 | 8.1% | Automated replenishment or reactivation trigger |
| P5 Standard Nurture | 714 | 7.0% | Low-cost reminder or product education |
| P6 Winback Pool | 291 | 3.9% | Selective winback test with strict incrementality guardrails |
| P7 Standard Lifecycle | 1,491 | 71.6% | Maintain standard lifecycle messaging |

---

## 4. Commercial Interpretation

The priority output creates a clear CRM operating model.

Key findings:

- 22 high-value customers are both commercially important and high lapse risk.
- These P1 customers represent only 0.5% of customers but 4.5% of revenue.
- 515 customers are eligible for second-purchase acceleration.
- 1,281 standard-value customers are high lapse risk and suitable for scalable automated reactivation.
- 71.6% of revenue sits in standard lifecycle, meaning much of the highest-value base does not require aggressive intervention right now.

This supports a disciplined CRM strategy:

> Use high-touch effort only where customer value and risk justify it. Use low-cost automation for broader risk pools. Avoid unnecessary discounts for low-risk customers.

---

## 5. Action Strategy

### P1 High-Value Lapse Prevention

Objective:

- Protect concentrated revenue before high-value customers lapse.

Recommended treatment:

- Personalised retention message.
- Product recommendation or replenishment prompt.
- VIP service or loyalty recognition.
- Avoid blanket discounting unless tested.

Measurement:

- Purchase within 90 days.
- Retained revenue.
- Incremental revenue vs holdout.
- Margin after incentive cost.

### P2 High-Value Watchlist

Objective:

- Maintain engagement without over-intervening.

Recommended treatment:

- Light-touch VIP nurture.
- Product discovery.
- Early access or loyalty content.

Measurement:

- Recency movement.
- Repeat purchase rate.
- Revenue retention.

### P3 Second Purchase Acceleration

Objective:

- Convert one-time buyers into repeat customers earlier.

Recommended treatment:

- Day 21 second purchase accelerator.
- Recommendation-led message.
- Controlled exposed vs holdout design.

Measurement:

- Second purchase conversion.
- Days to second purchase.
- Net incremental value.

### P4 Standard Lapse Prevention

Objective:

- Recover or reactivate broader high-risk customers at controlled cost.

Recommended treatment:

- Automated replenishment reminder.
- Reactivation trigger.
- Low-cost channel first.

Measurement:

- Reactivation conversion.
- Incremental revenue per customer.
- Campaign cost per retained customer.

### P5 Standard Nurture

Objective:

- Keep medium-risk customers engaged without heavy incentives.

Recommended treatment:

- Product education.
- Reminder messaging.
- Non-discount content.

Measurement:

- Engagement.
- Repeat purchase rate.
- Movement into lower-risk band.

### P6 Winback Pool

Objective:

- Test selective recovery without overspending on low-propensity customers.

Recommended treatment:

- Limited winback test.
- Strict holdout design.
- Incentives only if margin supports them.

Measurement:

- Winback conversion.
- Net incremental value.
- Discount dependency.

### P7 Standard Lifecycle

Objective:

- Avoid unnecessary intervention for customers who do not require urgent action.

Recommended treatment:

- Maintain standard lifecycle messaging.
- No urgent discounting.
- Monitor risk movement over time.

Measurement:

- Revenue retention.
- Movement into risk bands.
- Ongoing purchase cadence.

---

## 6. Dashboard Use

The CRM priority outputs support dashboard views such as:

- Customers by CRM priority group.
- Revenue by CRM priority group.
- High-value high-risk customer count.
- Revenue exposure in P1 and P2 groups.
- Second purchase accelerator audience size.
- Average lapse risk by priority group.
- Recommended CRM action by group.
- Priority-ranked customer table.

Most useful executive dashboard message:

> The business can protect concentrated revenue by prioritising a small high-value risk group, while using automation for broader lapse prevention and second-purchase acceleration.

---

## 7. Experimentation Implications

The priority layer should feed CRM testing rather than bypass it.

Recommended experiments:

1. High-value lapse prevention test.
2. Second purchase accelerator test.
3. Standard lapse prevention automation test.
4. Selective winback test.

Each test should include:

- Exposed group.
- Holdout group.
- Incremental revenue measurement.
- Margin and discount guardrails.
- 30/60/90-day readouts where relevant.

The priority score identifies who to test. It does not prove that a CRM intervention will work.

---

## 8. Strategic Recommendation

Use the CRM priority score as the operational layer connecting analytics to action.

Recommended rollout order:

1. Start with P1 high-value lapse prevention because the group is small and revenue exposure is meaningful.
2. Run the P3 second purchase accelerator as the early lifecycle growth test.
3. Use P4 standard lapse prevention for scalable automated reactivation.
4. Keep P7 customers out of unnecessary discounting and monitor risk movement.

One-line recommendation:

> Prioritise CRM by customer value, lapse risk, and lifecycle stage rather than sending broad retention campaigns to everyone.

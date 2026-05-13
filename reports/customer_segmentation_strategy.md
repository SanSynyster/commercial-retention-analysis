# Customer Segmentation Strategy

## 1. Purpose

This report translates the retention analysis into operational customer lifecycle segments for CRM planning, dashboarding, and commercial prioritisation.

The segmentation answers:

> Which customers should receive which lifecycle treatment?

The output supports the broader project recommendation: accelerate second purchase behaviour, protect high-value customers, and reduce dependence on a narrow revenue-concentrated segment.

---

## 2. Methodology

The segmentation uses customer-level metrics from the retention analysis and order-level timing rebuilt from the clean transaction layer.

Inputs:

- `customer_metrics.parquet`
- `clean_transactions.parquet`

Outputs:

- `customer_segments.csv`
- `customer_segment_summary.csv`

The segmentation includes one mutually exclusive `primary_segment` and supporting flags.

Supporting flags include:

- `is_high_value`
- `is_one_time_customer`
- `is_early_repeater`
- `is_delayed_repeater`
- `is_at_risk`
- `is_lapsed`
- `is_second_purchase_accelerator_eligible`

This structure keeps the dataset simple for dashboards while preserving tactical CRM targeting detail.

---

## 3. Segment Definitions

| Segment | Definition | Recommended CRM Action |
| --- | --- | --- |
| High-Value Repeat Customer | Repeat customer in the top revenue decile and not currently at-risk or lapsed | VIP retention or loyalty treatment |
| Delayed Repeater | Repeat customer whose second purchase took more than 30 days | Cadence acceleration and replenishment flow |
| Early Repeater | Repeat customer whose second purchase occurred within 30 days | Reinforce repeat behaviour and cross-sell |
| Second Purchase Accelerator Eligible | One-time customer, at least 21 days after first purchase, not lapsed | Day 21 second purchase accelerator |
| At-Risk Customer | Customer with 60-89 days since last purchase | Reminder or replenishment trigger |
| High-Value At-Risk | Top-decile customer with 60-89 days since last purchase | Priority re-engagement before lapse |
| Lapsed Customer | Customer with 90+ days since last purchase | Low-cost winback or reactivation test |
| High-Value Lapsed | Top-decile customer with 90+ days since last purchase | Priority winback with high-touch messaging |
| One-Time Buyer | One-order customer not yet eligible for accelerator or assigned to higher-priority segment | Monitor until accelerator eligibility |
| Low-Value Active Customer | Active lower-priority customer not assigned elsewhere | Low-cost nurture and product discovery |

---

## 4. Segment Sizing

| Primary Segment | Customers | Revenue Share | Customer Share | CRM Priority |
| --- | ---: | ---: | ---: | --- |
| High-Value Repeat Customer | 388 | 56.9% | 8.9% | Protect and retain |
| Delayed Repeater | 1,078 | 15.3% | 24.9% | Accelerate cadence |
| Lapsed Customer | 1,426 | 8.6% | 32.9% | Winback selectively |
| Early Repeater | 490 | 8.5% | 11.3% | Cross-sell and reinforce |
| At-Risk Customer | 472 | 4.5% | 10.9% | Re-engage before lapse |
| High-Value Lapsed | 23 | 3.0% | 0.5% | Priority winback |
| Second Purchase Accelerator Eligible | 309 | 1.3% | 7.1% | MVP accelerator audience |
| High-Value At-Risk | 21 | 1.3% | 0.5% | High-priority intervention |
| One-Time Buyer | 131 | 0.5% | 3.0% | Monitor until eligible |

Important note:

- 515 customers meet the second purchase accelerator eligibility flag.
- 309 customers receive `Second Purchase Accelerator Eligible` as their primary segment.
- The remaining eligible customers are assigned to higher-priority primary segments such as at-risk or high-value at-risk.

This is intentional. The `primary_segment` is designed for simple operational planning, while the supporting flags preserve broader campaign eligibility.

---

## 5. Commercial Interpretation

The segmentation reinforces the core project story.

Key observations:

- A small high-value repeat segment generates the majority of revenue.
- A large delayed-repeater group suggests there is room to improve lifecycle velocity.
- Lapsed customers are numerous but lower in revenue share, so winback should be selective rather than heavily discounted by default.
- The second purchase accelerator audience is commercially important as a lifecycle intervention point, even though its current revenue share is small.
- At-risk and high-value at-risk customers should be prioritised before they become harder to recover.

The segmentation makes the CRM strategy more precise:

> Do not send every customer the same retention campaign. Use lifecycle status, repeat timing, revenue value, and recency to choose the right treatment.

---

## 6. Recommended CRM Strategy By Segment

### High-Value Repeat Customer

Objective:

- Protect revenue concentration.
- Reduce churn risk among the most commercially important customers.

Recommended actions:

- Loyalty recognition.
- VIP messaging.
- Early access or premium product discovery.
- Non-discount value reinforcement where possible.

Measurement:

- Repeat frequency.
- Revenue retention.
- Recency movement.
- High-value churn rate.

### Second Purchase Accelerator Eligible

Objective:

- Convert one-time buyers into repeat customers earlier.

Recommended actions:

- Day 21 lifecycle trigger.
- Product recommendation or replenishment prompt.
- Controlled exposed vs holdout experiment.
- Avoid default discounting unless needed.

Measurement:

- Second purchase conversion.
- Days to second purchase.
- Net incremental value.
- 30/60/90-day treatment vs control gap.

### Delayed Repeater

Objective:

- Shorten repeat cadence.
- Increase customer productivity.

Recommended actions:

- Replenishment reminders.
- Timing-based nudges before expected repeat date.
- Cross-sell based on previous order behaviour.

Measurement:

- Time between orders.
- Repeat frequency.
- Revenue per customer.

### Early Repeater

Objective:

- Reinforce healthy repeat behaviour.
- Encourage third purchase and category expansion.

Recommended actions:

- Cross-sell flow.
- Loyalty onboarding.
- Product discovery messaging.

Measurement:

- Third purchase conversion.
- AOV.
- Category expansion.

### At-Risk and High-Value At-Risk

Objective:

- Prevent customer lapse before inactivity becomes entrenched.

Recommended actions:

- Reminder flow.
- Replenishment trigger.
- High-value customers receive prioritised or more personalised messaging.

Measurement:

- Reactivation rate.
- Recency improvement.
- Incremental revenue vs control.

### Lapsed and High-Value Lapsed

Objective:

- Recover customers selectively without over-investing in low-propensity users.

Recommended actions:

- Low-cost winback for general lapsed customers.
- Higher-touch winback for high-value lapsed customers.
- Test incentives carefully and measure net value.

Measurement:

- Winback conversion.
- Net incremental value.
- Discount dependency.
- Post-winback repeat rate.

---

## 7. Dashboard Use

The segmentation outputs can support dashboard views such as:

- Customers by primary segment.
- Revenue by primary segment.
- Segment revenue share vs customer share.
- High-value at-risk customer count.
- Second purchase accelerator eligible audience.
- Lapsed customer volume and revenue exposure.
- Recommended CRM action by segment.

Most useful dashboard message:

> Revenue is concentrated among high-value repeat customers, but lifecycle growth depends on converting and accelerating lower-maturity customer segments.

---

## 8. Strategic Recommendation

Use the segmentation layer to operationalise the CRM roadmap.

Priority order:

1. Protect high-value repeat customers.
2. Launch the second purchase accelerator test for eligible one-time buyers.
3. Re-engage high-value at-risk customers before they lapse.
4. Improve cadence for delayed repeaters.
5. Use selective winback for lapsed customers.

One-line recommendation:

> Move from broad retention messaging to lifecycle-specific CRM treatments based on customer value, repeat maturity, and recency risk.

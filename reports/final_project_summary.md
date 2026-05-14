# Final Project Summary

## Executive Summary

This project analyses retention, lifecycle revenue, customer concentration, and predictive CRM prioritisation for a DTC-style ecommerce business using the UCI Online Retail dataset.

The analysis shows that repeat behaviour is commercially important, but revenue is concentrated and repeat timing is slower than ideal. The recommended strategy is to move away from broad retention messaging and toward targeted CRM actions based on customer value, lifecycle stage, and predicted risk.

One-line conclusion:

> Repeat revenue is strong, but the business should protect high-value customers at lapse risk and accelerate second purchase behaviour through controlled CRM experimentation.

---

## Key Commercial Findings

| Finding | Evidence | Commercial Meaning |
| --- | --- | --- |
| Repeat behaviour drives revenue | Repeat-order revenue is 79.3% of identifiable revenue | Retention is central to commercial performance |
| Repeat customers are highly valuable | Repeat-customer revenue is 93.1% of identifiable revenue | Existing customer productivity matters more than acquisition volume alone |
| Customers return, but slowly | Second purchase conversion is 65.6%, median days to second purchase is 50 | Opportunity is lifecycle acceleration, not only retention repair |
| Revenue is concentrated | Top 10% of customers generate 61.4% of identifiable revenue | High-value customer protection is a strategic priority |
| Lapse-risk ML is actionable | Top risk decile lapse rate is 75.8% vs 47.3% baseline | Predictive scoring can prioritise retention intervention |

---

## Data Foundation

The project starts with transaction-level cleaning and KPI governance.

Current audit outputs:

- Total rows analysed: 541,909
- Duplicate rows identified: 5,268
- Missing CustomerID rows: 24.9%
- Gross positive purchase revenue: GBP 10.67M
- Net transactional revenue: GBP 9.77M
- Identifiable customer revenue: GBP 8.91M
- Identifiable revenue coverage: 83.5%
- Valid customers: 4,338
- Valid orders: 18,532

The data model separates finance-style reconciliation metrics from behavioural lifecycle metrics. Customer-level retention analysis is calculated only on identifiable customers.

---

## Predictive Analytics Summary

### Second Purchase Propensity

The second purchase model predicts whether a first-time buyer will repeat within 60 days.

Current readout:

- ROC-AUC: 0.520
- PR-AUC: 0.391
- Top 10% precision: 44.0%
- Test baseline repeat rate: 36.7%
- Top decile lift: 1.20x

Interpretation:

- Directionally useful for prioritisation.
- Not strong enough as an automated production targeting engine.
- Best used to tailor early lifecycle messaging within a controlled CRM test.

### Lapse Risk

The lapse model predicts whether an existing customer will have no valid purchase in the next 90 days.

Current readout:

- ROC-AUC: 0.753
- PR-AUC: 0.690
- Top 10% precision: 75.8%
- Test baseline lapse rate: 47.3%
- Top decile lift: 1.60x

Interpretation:

- Strongest ML component in the project.
- Provides a credible predictive risk signal.
- Supports high-value lapse prevention and prioritised retention action.

---

## CRM Priority Strategy

The final customer action layer combines lifecycle segmentation, lapse-risk ML, second-purchase propensity, and value flags.

| Priority Group | Customers | Revenue Share | Recommended Action |
| --- | ---: | ---: | --- |
| P1 High-Value Lapse Prevention | 22 | 4.5% | Personalised retention intervention |
| P2 High-Value Watchlist | 24 | 2.4% | VIP nurture |
| P3 Second Purchase Acceleration | 515 | 2.4% | Day 21 second purchase accelerator |
| P4 Standard Lapse Prevention | 1,281 | 8.1% | Automated reactivation |
| P5 Standard Nurture | 714 | 7.0% | Low-cost nurture |
| P6 Winback Pool | 291 | 3.9% | Selective winback |
| P7 Standard Lifecycle | 1,491 | 71.6% | Standard messaging |

The highest-priority operational group is P1:

- 22 customers
- 0.5% of customer base
- 4.5% of revenue
- Average lapse-risk score: 0.79

This is the clearest group for high-touch intervention because it combines high commercial value with high predicted risk.

---

## Experimentation Recommendation

The project recommends CRM action, but not blind scaling.

Priority experiments:

1. High-value lapse prevention test.
2. Second purchase accelerator test.
3. Standard lapse prevention automation test.
4. Selective winback test.

Each experiment should include:

- Exposed group.
- Holdout group.
- Incremental revenue measurement.
- Margin and discount guardrails.
- 30/60/90-day readouts where relevant.

The predictive models identify who to prioritise. They do not prove that CRM intervention causes uplift. Incrementality must be measured through control groups.

---

## Dashboard Narrative

The dashboard should tell a simple executive story:

1. Repeat revenue is commercially important.
2. Repeat timing is slower than ideal.
3. Revenue is concentrated among high-value customers.
4. Lapse-risk ML identifies customers who need attention.
5. CRM priority scoring translates analytics into action.

Recommended dashboard sections:

- Executive Overview
- Revenue and Retention
- Customer Concentration
- Cohort Retention
- Customer Segments
- Predictive ML
- CRM Priority Actions

---

## Limitations

The project is a public-data simulation.

Key limitations:

- No marketing channel data.
- No CRM exposure or campaign response history.
- No true treatment/control test data.
- No customer demographics.
- Product taxonomy is limited.
- Incrementality is simulated, not measured from real campaigns.

These limitations are handled explicitly by separating propensity prediction from causal uplift and by recommending controlled CRM testing before scaling.

---

## Final Recommendation

The business should use a targeted CRM operating model:

1. Prioritise P1 high-value lapse prevention.
2. Run the P3 second purchase accelerator as an early lifecycle experiment.
3. Use P4 automation for scalable lapse prevention.
4. Keep low-risk customers out of unnecessary discounting.
5. Measure all CRM interventions through exposed vs holdout incrementality.

Final statement:

> The project demonstrates how commercial analytics can move from descriptive retention reporting to predictive, value-aware CRM prioritisation with disciplined incrementality measurement.

# ML Summary: Lapse Risk Model

## 1. Purpose

This model predicts whether an existing customer is likely to lapse, defined as having no valid purchase in the next 90 days.

The model supports CRM retention prioritisation by identifying customers who should receive re-engagement before inactivity becomes entrenched.

Core question:

> Which existing customers are most likely to have no purchase in the next 90 days, and which high-value customers should CRM prioritise?

This is a predictive risk model, not a causal uplift model. It predicts natural lapse risk; it does not prove that CRM intervention will prevent lapse.

---

## 2. Modelling Approach

Model grain:

- One row per customer per monthly snapshot.

Target:

- `lapsed_next_90_days`

Target definition:

- `1` if the customer has no valid purchase in the 90 days after the snapshot date.
- `0` if the customer has at least one valid purchase in the 90 days after the snapshot date.

Design:

- Monthly rolling snapshots.
- Features use only behaviour before the snapshot date.
- Snapshots without a full 90-day target window are excluded.
- Train/test split is time-based, with earlier snapshots used for training and later snapshots used for testing.

This is more credible than a simple static churn flag because it mimics how a business would score active customers over time.

---

## 3. Features Used

The model uses behavioural features available at each snapshot:

- Recency days.
- Customer age days.
- Active days.
- Average days between orders.
- Orders per active day.
- Total orders.
- Revenue.
- Average order value.
- Average order quantity.
- Average order lines.
- Days to second purchase.
- Repeat customer flag.
- High-value customer flag.
- UK vs international customer group.
- Snapshot month.

Excluded features:

- Future purchases inside the 90-day target window.
- Any CRM exposure or campaign response data.
- Any post-snapshot revenue or lifecycle status.

---

## 4. Model Results

Three models were trained:

- Logistic regression baseline.
- Random forest classifier.
- Histogram gradient boosting classifier.

The selected model is chosen for CRM targeting performance, prioritising precision in the top 20% risk band and using ROC-AUC as the secondary tie-breaker.

| Model | Test Rows | Test Target Rate | ROC-AUC | PR-AUC | Precision Top 10% | Precision Top 20% | Brier Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Histogram Gradient Boosting | 9,425 | 47.3% | 0.753 | 0.690 | 75.8% | 73.8% | 0.206 |
| Random Forest | 9,425 | 47.3% | 0.757 | 0.689 | 74.8% | 72.9% | 0.198 |
| Logistic Regression | 9,425 | 47.3% | 0.750 | 0.684 | 74.3% | 72.3% | 0.204 |

Interpretation:

- The lapse model is materially stronger than the second purchase propensity model.
- All three models perform similarly, suggesting the behavioural features contain stable predictive signal.
- The selected model is useful for CRM prioritisation and risk ranking.
- The model should still be validated through exposed vs control CRM measurement before claiming intervention impact.

---

## 5. Lift By Risk Decile

The scored test set was ranked by predicted lapse risk.

| Risk Decile | Customers | Observed Lapse Rate | Lift vs Test Average | High-Value Customers |
| --- | ---: | ---: | ---: | ---: |
| Top 10% | 943 | 75.8% | 1.60x | 9 |
| 10-20% | 942 | 71.8% | 1.52x | 26 |
| 20-30% | 943 | 65.1% | 1.38x | 17 |
| 30-40% | 942 | 60.2% | 1.27x | 9 |
| 40-50% | 943 | 55.9% | 1.18x | 11 |
| 50-60% | 942 | 51.9% | 1.10x | 18 |
| 60-70% | 942 | 38.4% | 0.81x | 29 |
| 70-80% | 943 | 30.3% | 0.64x | 44 |
| 80-90% | 942 | 19.0% | 0.40x | 144 |
| Bottom 10% | 943 | 5.0% | 0.11x | 634 |

Interpretation:

- The top risk decile has a 75.8% observed lapse rate versus a 47.3% test baseline.
- The bottom risk decile has only a 5.0% observed lapse rate.
- The model separates high-risk and low-risk customers clearly enough to support CRM prioritisation.
- High-value customers are concentrated in lower-risk bands, but there are still high-value customers in top risk bands who should be prioritised.

---

## 6. Feature Importance

Top directional drivers from the selected model, based on permutation importance:

| Feature | Importance |
| --- | ---: |
| Active days | 0.054 |
| Revenue | 0.029 |
| Total orders | 0.015 |
| Average order quantity | 0.014 |
| Average order lines | 0.008 |
| Average order value | 0.005 |
| Recency days | 0.005 |
| Average days between orders | 0.001 |
| Orders per active day | 0.001 |
| Country group | 0.000 |

Interpretation:

- Lifecycle depth and monetary value are stronger predictors than first-order-only features.
- Active days, revenue, and total orders provide meaningful risk signal.
- Recency contributes, but the model is not only a simple recency rule.
- Feature importance is predictive, not causal.

---

## 7. Commercial Use

Recommended CRM use:

- Score customers monthly for lapse risk.
- Prioritise high-risk customers for retention or reactivation messaging.
- Prioritise high-value high-risk customers for more personalised intervention.
- Avoid discounting low-risk customers who are likely to remain active naturally.
- Use risk deciles to compare treatment response and incremental value in CRM tests.

Recommended action logic:

- High-value + high risk: priority retention intervention.
- High risk: automated reactivation or replenishment trigger.
- Medium risk: light-touch reminder or nurture.
- Low risk: maintain standard lifecycle messaging.

---

## 8. Outputs Created

The notebook creates:

- `data/processed/lapse_risk_model_metrics.csv`
- `data/processed/lapse_risk_scores.csv`
- `data/processed/lapse_risk_lift.csv`
- `data/processed/lapse_risk_feature_importance.csv`

Current regenerated output status:

- `lapse_risk_model_metrics.csv`: 3 models x 13 fields.
- `lapse_risk_scores.csv`: 3,317 latest-snapshot customers x 14 fields.
- `lapse_risk_lift.csv`: 10 risk deciles x 6 fields.
- `lapse_risk_feature_importance.csv`: 15 features x 2 fields.

These outputs can support dashboard views such as:

- Lapse risk distribution.
- High-risk customer counts.
- High-value high-risk customer counts.
- Lapse rate by risk decile.
- Recommended CRM action by risk band.
- Feature importance.

---

## 9. Limitations

Important limitations:

- The model predicts natural lapse risk, not causal retention impact.
- The public dataset does not include CRM exposure, email engagement, acquisition source, or customer demographics.
- The latest scored snapshot is constrained by the dataset end date and the need for a full 90-day target window.
- Some high-risk customers may be low commercial priority if their value is low.
- Lapse-prevention value must still be measured through exposed vs control CRM tests.

---

## 10. Recommendation

The lapse risk model is the strongest ML component in the project so far and should be positioned as the main predictive analytics layer.

Recommended use:

> Use lapse risk scores to prioritise retention intervention, especially for high-value customers, then validate incremental impact through controlled CRM testing.

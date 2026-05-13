# ML Summary: Second Purchase Propensity Model

## 1. Purpose

This model predicts whether a first-time buyer will make a second purchase within 60 days.

The model supports the CRM lifecycle strategy by helping prioritise customers for the second purchase accelerator campaign.

Core question:

> Which first-time buyers are more likely to repeat within the next 60 days, based only on information available at first purchase?

This is a propensity model, not a causal uplift model. It predicts likelihood of repeat behaviour; it does not prove that CRM will cause that behaviour.

---

## 2. Modelling Approach

Model grain:

- One row per customer at first valid order.

Target:

- `repeat_within_60_days`

Target definition:

- `1` if the customer made a second valid order within 60 days of first purchase.
- `0` otherwise.

Why 60 days:

- The project found median time to second purchase is ~50 days.
- A 60-day window is commercially aligned to lifecycle acceleration.
- It provides enough time to observe repeat behaviour while remaining relevant for CRM timing.

Leakage control:

- Features are limited to first-order information.
- Customers without at least 60 days of observation after first purchase are excluded.
- Train/test split is time-based using first purchase date, not random sampling.

---

## 3. Features Used

The model uses features available at or immediately after first purchase:

- First order revenue.
- First order quantity.
- Number of order lines.
- Number of unique products.
- Basket diversity ratio.
- Average unit price.
- Revenue per order line.
- Revenue per unique product.
- UK vs non-UK customer flag.
- Product-description keyword flags for gift, set, bag, christmas, and jumbo.
- First order hour.
- Whether first order revenue was above median.
- Country.
- First order month.
- First order weekday.

Excluded features:

- Future purchase behaviour.
- Customer revenue after first purchase.
- Repeat customer flags.
- Any post-first-order lifecycle variables.

This keeps the model usable for real CRM scoring after a customer's first purchase.

---

## 4. Model Results

Three models were trained:

- Logistic regression baseline.
- Random forest classifier.
- Histogram gradient boosting classifier.

The selected model is chosen for CRM targeting performance, prioritising precision in the top 20% score band and using ROC-AUC as the secondary tie-breaker. This matches the business use case: prioritising customers for a campaign, not classifying every customer perfectly.

| Model | Test Rows | Test Target Rate | ROC-AUC | PR-AUC | Precision Top 10% | Precision Top 20% | Brier Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Histogram Gradient Boosting | 746 | 36.7% | 0.520 | 0.391 | 44.0% | 40.0% | 0.249 |
| Logistic Regression | 746 | 36.7% | 0.542 | 0.382 | 33.3% | 39.3% | 0.244 |
| Random Forest | 746 | 36.7% | 0.535 | 0.389 | 36.0% | 39.3% | 0.246 |

Interpretation:

- Model discrimination remains modest, especially on ROC-AUC.
- The gradient boosting model is selected because it performs best in the highest-priority score bands.
- This is a deliberate targeting tradeoff: logistic regression has the highest ROC-AUC, but gradient boosting has the strongest top-decile and top-20% precision for CRM prioritisation.
- The model is more useful for ranking and prioritisation than for broad yes/no prediction.
- This should be used as a CRM decision-support layer, not as a fully automated production targeting engine.

---

## 5. Lift By Propensity Decile

The scored test set was ranked into deciles by predicted propensity.

| Score Decile | Customers | Observed Repeat Rate | Lift vs Test Average |
| --- | ---: | ---: | ---: |
| Top 10% | 75 | 44.0% | 1.20x |
| 10-20% | 75 | 36.0% | 0.98x |
| 20-30% | 74 | 33.8% | 0.92x |
| 30-40% | 75 | 40.0% | 1.09x |
| 40-50% | 74 | 41.9% | 1.14x |
| 50-60% | 75 | 32.0% | 0.87x |
| 60-70% | 74 | 31.1% | 0.85x |
| 70-80% | 75 | 37.3% | 1.02x |
| 80-90% | 74 | 32.4% | 0.88x |
| Bottom 10% | 75 | 38.7% | 1.05x |

Interpretation:

- The top score decile has the strongest observed repeat rate at 44.0%.
- The lift curve is not monotonic, which confirms model signal is limited and should be used cautiously.
- Score bands are more useful operationally than exact probabilities.
- This reinforces that the model should support prioritisation, not replace experiment-based decision-making.

Propensity band readout on the test set:

| Propensity Band | Customers | Observed Repeat Rate | Average Score |
| --- | ---: | ---: | ---: |
| Low propensity | 491 | 36.3% | 0.261 |
| Medium propensity | 190 | 35.3% | 0.465 |
| High propensity | 65 | 44.6% | 0.630 |

---

## 6. Feature Importance

Top directional drivers from the selected model, based on permutation importance:

| Feature | Importance |
| --- | ---: |
| First order hour | 0.013 |
| First order revenue | 0.010 |
| First order weekday | 0.004 |
| Order lines | 0.004 |
| Unique products | 0.003 |
| First order quantity | 0.003 |
| Contains set keyword | 0.003 |
| Country | 0.003 |
| Contains christmas keyword | 0.000 |
| First order month | 0.000 |

Interpretation:

- Permutation importance shows weak individual feature effects, consistent with modest overall model discrimination.
- First-order timing, first-order value, basket structure, and product-description keywords provide small directional signal.
- Country remains useful as a model input, but no single feature should be interpreted as a strong standalone predictor.
- Feature importance is predictive, not causal. It should not be interpreted as proof that changing a feature would cause a higher repeat rate.

---

## 7. Commercial Use

Recommended CRM use:

- Use propensity scores as a prioritisation layer for one-time buyers.
- Combine scores with lifecycle eligibility rules from `customer_segments.csv`.
- Avoid discounting high-propensity customers by default because they may repeat naturally.
- Test stronger nudges for lower-propensity customers, but only with holdout measurement.
- Use score deciles to compare campaign response and incremental value by predicted propensity band.

Recommended targeting logic:

- High propensity: light-touch reminder or product recommendation.
- Medium propensity: standard second purchase accelerator.
- Low propensity: test differentiated messaging or stronger value proposition, but monitor economics closely.

---

## 8. Limitations

Important limitations:

- The public dataset does not include CRM exposure or marketing response data.
- The model predicts natural repeat propensity, not causal treatment response.
- ROC-AUC is modest, so model scores should be treated as directional.
- Product category information is limited and inferred only through product codes/descriptions.
- Dataset seasonality may influence first-order month importance.
- Results should be validated with real campaign outcomes before production use.

The right next step is not to over-optimise this offline model. The better next step is to use it inside the CRM experiment design and evaluate whether propensity bands show different incremental response patterns.

---

## 9. Outputs Created

The notebook creates:

- `data/processed/second_purchase_model_metrics.csv`
- `data/processed/second_purchase_propensity_scores.csv`
- `data/processed/second_purchase_propensity_lift.csv`
- `data/processed/second_purchase_propensity_bands.csv`
- `data/processed/second_purchase_feature_importance.csv`

Current regenerated output status:

- `second_purchase_model_metrics.csv`: 3 models x 13 fields.
- `second_purchase_propensity_scores.csv`: 3,731 scored customers x 12 fields.
- `second_purchase_propensity_lift.csv`: 10 score deciles x 5 fields.
- `second_purchase_propensity_bands.csv`: 6 split/band rows x 5 fields.
- `second_purchase_feature_importance.csv`: 19 features x 2 fields.

The regenerated scoring file now matches the current notebook schema and excludes reverted experimental fields such as `country_group` and product-history propensity features.

These outputs can support dashboard views such as:

- Model performance summary.
- Propensity score distribution.
- Repeat rate by score decile.
- CRM action by propensity band.
- Feature importance.

---

## 10. Recommendation

The second purchase propensity model should be included as a decision-support layer, not as a standalone automation engine.

Recommended use:

> Use propensity scores to prioritise and tailor the second purchase accelerator, then validate true commercial value through exposed vs control experiment measurement.

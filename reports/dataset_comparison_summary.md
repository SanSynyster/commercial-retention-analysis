# Dataset Comparison Summary

## Purpose

This report compares the original one-year Online Retail workbook with the expanded two-year Online Retail II CSV.

The goal is to test whether the current project baseline is contained inside the expanded dataset and whether the retention and CRM framework remains directionally stable on a longer history.

---

## Dataset Relationship

The expanded dataset is not independent from the current baseline. It contains the full current one-year dataset and adds an earlier year of trading history.

| Check | Result |
| --- | ---: |
| V1 rows | 541,909 |
| V2 rows | 1,067,371 |
| V1 rows found in V2 | 541,909 |
| V1 rows found in V2 | 100.0% |
| V1 invoices found in V2 | 100.0% |
| V1 customers found in V2 | 100.0% |
| V1 stock codes found in V2 | 100.0% |

Interpretation:

- V2 should be framed as an expanded two-year history, not as a fully independent validation dataset.
- The right comparison is baseline one-year performance versus longer-history performance.
- The overlap check confirms the current project baseline is embedded in V2.

---

## KPI Comparison

| Metric | V1 Current One-Year | V2 Expanded Two-Year |
| --- | ---: | ---: |
| Total rows | 541,909 | 1,067,371 |
| Duplicate rows | 5,268 | 34,335 |
| Missing customer ID | 24.9% | 22.8% |
| Identifiable customer revenue | GBP 8.91M | GBP 17.74M |
| Identifiable revenue coverage | 83.5% | 84.6% |
| Valid customers | 4,338 | 5,878 |
| Valid orders | 18,532 | 36,969 |
| Second purchase conversion | 65.6% | 72.4% |
| Median days to second purchase | 50 | 55 |
| Repeat-order revenue share | 79.3% | 86.2% |
| Repeat-customer revenue share | 93.1% | 96.8% |
| Top 10% revenue share | 61.4% | 63.9% |

Interpretation:

- The longer two-year view shows stronger repeat behaviour and higher repeat revenue dependency.
- Second purchase conversion increases from 65.6% to 72.4%, but median time to second purchase lengthens from 50 to 55 days.
- Customer concentration remains high in both versions, with the top decile contributing more than 60% of revenue.
- The core commercial story is stable: repeat behaviour is valuable, revenue is concentrated, and lifecycle timing still matters.

---

## Predictive Model Comparison

| Model Layer | V1 Selected Model | V1 ROC-AUC | V1 Top-20 Precision | V2 Selected Model | V2 ROC-AUC | V2 Top-20 Precision |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Second purchase propensity | Hist gradient boosting | 0.520 | 40.0% | Random forest | 0.596 | 48.0% |
| Lapse risk | Hist gradient boosting | 0.753 | 73.8% | Hist gradient boosting | 0.807 | 92.1% |

Interpretation:

- The second purchase model improves on the longer history, but still remains a prioritisation signal rather than a production-grade targeting engine.
- The lapse-risk model strengthens materially on the expanded dataset and remains the most credible predictive layer.
- Model selection is allowed to vary by dataset because the comparison tests pipeline robustness, not fixed-model deployment.

---

## CRM Priority Comparison

| Metric | V1 Current One-Year | V2 Expanded Two-Year |
| --- | ---: | ---: |
| P1 high-value lapse customers | 22 | 37 |
| P1 revenue share | 4.5% | 4.8% |

Interpretation:

- The highest-priority CRM group remains small but commercially meaningful in both datasets.
- This supports the current recommendation to use high-touch intervention selectively for high-value customers with elevated lapse risk.

---

## Final Takeaway

The expanded V2 dataset confirms the current project is not just a one-off analysis hardcoded to one file. After adding column mapping and configurable input/output paths, the same analytical framework runs successfully on both the one-year and two-year dataset versions.

One-line conclusion:

> V2 contains the full V1 baseline and strengthens the same commercial story: repeat revenue is powerful, customer concentration remains material, and CRM should prioritise high-value lapse prevention and lifecycle acceleration with controlled incrementality measurement.

> **Historical implementation documentation — not a production deployment or current corrected-V2 model.** The code and runbook below describe the earlier exploratory lapse workflow. Its scores and operating recommendations have not been independently reproduced under the corrected-V2 contracts. Current research status and validated results are documented in the [README](../README.md) and [research status](RESEARCH_STATUS.md).

---

# Historical Lapse-Model Implementation (Exploratory)

## Purpose

The earlier churn-prediction implementation refactors the notebook lapse-risk logic into reusable Python modules and a command-line entrypoint. It was designed to predict whether a customer would have no valid purchase in the next 90 days and write notebook-compatible outputs. This describes historical code capability, not a deployed or corrected-V2 validated scoring service.

The earlier model was predictive rather than causal. Its historical scores do not establish intervention impact or current CRM suitability.

## Implementation

| Asset | Purpose |
| --- | --- |
| `src/churn_prediction.py` | Feature engineering, rolling snapshots, model training, scoring, lift, and output writing |
| `src/run_churn_prediction.py` | CLI entrypoint for dataset-specific model runs |
| `src/validation.py` | Lapse-risk output schema and score validation |
| `tests/test_pipeline.py` | Snapshot leakage, target labelling, and output validation tests |

## Runbook

Run the core pipeline first so the model has processed transactions:

```bash
make pipeline-v1
```

Train and score the lapse-risk model:

```bash
make churn-v1
```

Validate all lightweight tests:

```bash
make test
```

## Model Design

| Element | Definition |
| --- | --- |
| Grain | Customer x monthly snapshot |
| Target | `lapsed_next_90_days` |
| Positive class | Customer has no valid purchase in the 90 days after the snapshot date |
| Feature window | Orders before the snapshot date only |
| Observation rule | Snapshots without a full 90-day future window are excluded |
| Split | Time-based split: earlier snapshots train, later snapshots test |
| Selection metric | Precision in the top 20% risk band, with ROC-AUC as secondary tie-breaker |

## Features

The model uses behavioral features available before each snapshot:

- Recency days.
- Customer age days.
- Active days.
- Average days between orders.
- Orders per active day.
- Total orders.
- Revenue and average order value.
- Average order quantity and order lines.
- Days to second purchase.
- Repeat customer flag.
- High-value flag within each snapshot.
- UK vs international customer group.
- Snapshot month.

## Outputs

| Output | Purpose |
| --- | --- |
| `lapse_risk_model_metrics.csv` | Candidate model evaluation and selected-model evidence |
| `lapse_risk_scores.csv` | Latest full-observation customer risk scores and bands |
| `lapse_risk_lift.csv` | Test-set risk decile lift |
| `lapse_risk_feature_importance.csv` | Permutation importance on the test set |
| `lapse_risk_model.joblib` | Serialized selected sklearn pipeline |

## Leakage Controls

- Snapshot features are built only from orders where `order_date < snapshot_date`.
- The target is calculated from orders in the future 90-day window only.
- Time-based train/test split prevents future snapshots from influencing model validation.
- Tests verify that future orders do not inflate pre-snapshot order counts or revenue.

## Proposed Deployment Extension (Not Implemented)

In a warehouse or Databricks deployment, the same contract should be preserved:

- dbt/Spark builds the customer-order feature table.
- The model scores a monthly customer snapshot.
- Scores are written back to a governed mart for CRM activation.
- CRM impact is measured separately through treatment/control experiment marts.

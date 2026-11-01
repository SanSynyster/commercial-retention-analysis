# Historical V1 model metric discrepancy

This note preserves conflicting values recorded in the earlier exploratory V1 lapse-model materials. The V1 lapse summary reports histogram-gradient-boosting ROC-AUC **0.753** and PR-AUC **0.690** (`reports/ml_lapse_risk_summary.md`). The earlier agent handover records V1 baseline ROC-AUC **0.759** and PR-AUC **0.692** (`COMMERCIAL_DS_001_AGENT_HANDOVER.md`). The old project summary also reports ROC-AUC **0.759**. These values are not reconciled here; no value is selected as correct. No replacement metric is inferred.

The second-purchase propensity model is recorded as a historical negative finding: the earlier report gives ROC-AUC **0.520** and PR-AUC **0.391**, and the decision log says to retire it from CRM scoring. It is not an approved scoring policy or a corrected-V2 model result.

These historical model results have not been independently reproduced under the corrected-V2 source, taxonomy, purchase-occasion, and temporal contracts. They do not establish deployment, causal CRM impact, or current predictive performance. Corrected-V2 validation and B2B-1 status are documented separately; B2B-1 independent re-review remains pending.

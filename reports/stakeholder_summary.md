# Initial Data Audit Summary

> **Historical V1 descriptive summary.** Figures below are not corrected-V2 results. Suggested campaign actions are hypotheses for future evaluation, not causal findings or approved deployment recommendations; no campaign experiment is represented here as completed.


## Key Findings

- Total rows analysed: 541,909
- Gross positive purchase revenue: £10.67M
- Net transactional revenue: £9.77M
- Refund/cancellation revenue: -£0.90M
- Valid identifiable customers: 4,338
- Valid identifiable orders: 18,532

## Key Risks & Caveats

- 24.9% of rows are missing CustomerID values, limiting lifecycle analysis coverage.
- Refunds and cancellations are materially significant and must be treated separately from behavioural retention metrics.
- Duplicate rows were identified and require further validation before removal.
- Revenue definitions must remain clearly separated between gross purchase revenue and net transactional revenue.

## Next Steps

- Validate duplicate row behaviour
- Build customer metrics layer
- Create monthly retention cohorts
- Analyse first-to-second purchase conversion
- Build customer concentration analysis
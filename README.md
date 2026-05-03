

# Commercial Retention Analysis

Customer retention and repeat purchase analysis project simulating a commercial analytics workflow for a DTC nutrition e-commerce business.

This project focuses on:

- customer retention analysis
- repeat purchase behaviour
- cohort analysis
- customer concentration analysis
- revenue reconciliation
- lifecycle revenue metrics
- commercial KPI governance

The workflow is designed to reflect realistic analytics practices used across CRM, Commercial Analytics, and Finance teams.

---

## Project Objectives

The main goals of this project are to:

1. Build a clean analytical transaction layer
2. Create customer-level lifecycle metrics
3. Analyse retention cohorts and repeat purchase behaviour
4. Investigate revenue concentration and customer inequality
5. Establish transparent KPI definitions and reconciliation logic
6. Produce stakeholder-ready commercial insights

---

## Tech Stack

- Python
- pandas
- DuckDB
- Jupyter Notebooks
- SQL
- Git/GitHub
- Tableau Public (planned)

---

## Repository Structure

```text
commercial-retention-analysis/
│
├── data/
│   ├── raw/
│   ├── processed/
│
├── notebooks/
│   ├── 01_data_cleaning.ipynb
│   ├── 02_retention_analysis.ipynb
│
├── sql/
│   ├── customer_metrics.sql
│   ├── retention_cohorts.sql
│   ├── customer_concentration.sql
│
├── dashboards/
│
├── reports/
│   ├── stakeholder_summary.md
│   ├── kpi_definitions.md
│
├── src/
│
├── README.md
└── requirements.txt
```

---

## Current Sprint Scope

### Deliverables

- Data audit
- Clean transaction layer
- Revenue reconciliation
- Customer metrics table
- Monthly retention cohorts
- Customer lifecycle revenue split
- Customer concentration analysis
- Stakeholder summary report

---

## Current Audit Highlights

Initial findings from the first data audit:

- Total rows analysed: 541,909
- Duplicate rows identified: 5,268
- Missing CustomerID rows: 24.9%
- Gross positive purchase revenue: ~£10.67M
- Net transactional revenue: ~£9.77M
- Refund/cancellation revenue: ~-£0.90M
- Identifiable customer revenue coverage: ~83.5%

---

## Notes

This project uses the UCI Online Retail dataset as a public simulation dataset for commercial analytics workflows.

The dataset does not fully represent a modern subscription-based nutrition business, so conclusions should be interpreted directionally rather than as production business truth.


# Commercial Retention Analysis

End-to-end customer retention and lifecycle analysis simulating a commercial analytics workflow for a DTC e-commerce business.

The project focuses on understanding:

- how repeat purchase behaviour drives revenue,
- whether retention is broad or concentrated,
- and how lifecycle insights can inform CRM strategy and business decisions.

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

## Key Insights

- ~79% of revenue is driven by repeat-order behaviour
- ~93% of identifiable revenue comes from repeat customers
- Second purchase conversion is ~65%, but occurs with a median delay of 50 days
- Top 10% of customers contribute ~61% of revenue

These findings suggest retention is functioning, but performance is heavily dependent on a relatively small group of high-value customers, with slower-than-optimal repeat timing.

---

## Business Value

This analysis enables:

- Identification of retention vs acquisition dependency
- Understanding of customer concentration risk
- Definition of CRM trigger windows for repeat engagement
- Alignment between CRM, Commercial Analytics, and Finance KPI definitions

The workflow demonstrates how analytical outputs translate into actionable business decisions.

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

## Dataset Context

This project uses the UCI Online Retail dataset as a public simulation.

While not fully representative of a modern DTC subscription business, it is sufficient for analysing:

- retention mechanics
- repeat purchase behaviour
- customer concentration

All insights should be interpreted directionally rather than as production business metrics.


# Commercial Retention Analysis

End-to-end customer retention, lifecycle analytics, and CRM strategy simulation for a DTC e-commerce business.

The project simulates a real commercial analytics workflow covering:

- transactional data auditing,
- KPI governance and revenue reconciliation,
- retention and cohort analysis,
- lifecycle revenue modelling,
- customer concentration analysis,
- CRM experimentation strategy,
- incrementality measurement,
- and executive-level commercial decision support.

---

## Project Objectives

1. Build a clean analytical transaction layer
2. Create customer-level lifecycle and retention metrics
3. Analyse repeat purchase behaviour and retention cohorts
4. Investigate customer concentration and revenue dependency
5. Establish transparent KPI definitions and revenue reconciliation logic
6. Develop CRM lifecycle acceleration strategies
7. Design operational CRM experimentation frameworks
8. Translate analytical findings into commercial recommendations

---

## Key Insights

Key analytical findings from Sprint 1:

- ~79% of identifiable revenue is driven by repeat-order behaviour
- ~93% of identifiable revenue comes from repeat customers
- Second purchase conversion is ~65.6%
- Median time to second purchase is ~50 days
- Top 10% of customers contribute ~61% of revenue

These findings suggest:

- retention mechanics are functioning,
- repeat behaviour is commercially important,
- but revenue remains relatively concentrated among a smaller high-value segment.

The analysis also identified a strategic lifecycle opportunity:

> Customers appear willing to return naturally, but more slowly than optimal.

This shifted the strategic focus from:
- “fixing retention”
toward:
- accelerating lifecycle velocity and repeat timing.

---

## Business Value

This project demonstrates how commercial analytics can support:

- retention strategy prioritisation
- lifecycle acceleration decision-making
- CRM experimentation design
- revenue concentration risk analysis
- KPI governance and reconciliation
- incremental value evaluation
- and cross-functional commercial planning.

The workflow intentionally connects:

- analytical outputs,
- operational CRM execution,
- experimentation discipline,
- and commercial decision-making.

A major focus of the project is distinguishing between:

- behavioural uplift,
- timing acceleration,
- and genuine incremental commercial value.

## Tech Stack

- Python
- pandas
- DuckDB
- Jupyter Notebooks
- SQL
- Git/GitHub
- Tableau Public (planned)
- CRM experimentation concepts
- Lifecycle analytics
- Incrementality analysis

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

- Data audit and transaction validation
- Revenue reconciliation framework
- Customer lifecycle metrics
- Monthly retention cohort analysis
- Lifecycle revenue split analysis
- Customer concentration analysis
- CRM lifecycle acceleration strategy
- MVP experimentation rollout planning
- Incrementality and cannibalisation analysis
- Stakeholder-ready commercial reporting

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

## CRM & Lifecycle Strategy (Sprint 2)

Sprint 2 extends the project from descriptive analytics into operational CRM strategy.

Key areas explored:

- lifecycle acceleration
- CRM trigger windows
- second purchase optimisation
- operational rollout planning
- incrementality measurement
- cannibalisation risk
- control vs exposed experimentation
- incremental economics evaluation
- strategic prioritisation under business constraints

Example lifecycle strategy outcome:

- Prioritise second purchase acceleration before aggressive acquisition scaling
- Focus on improving customer productivity before expanding acquisition volume
- Validate incremental value through controlled experimentation before scaling CRM investment

---

## Dataset Context

This project uses the UCI Online Retail dataset as a public simulation.

While not fully representative of a modern DTC subscription business, it is sufficient for analysing:

- retention mechanics
- repeat purchase behaviour
- customer concentration

All insights should be interpreted directionally rather than as production business metrics.

The project intentionally emphasises:
- analytical reasoning,
- KPI governance,
- experimental thinking,
- commercial tradeoffs,
- and executive communication,
rather than purely technical modelling.
# Product Analytics and Experimentation Layer

## Purpose

This layer converts the CRM experiment design into dbt-backed analytical assets. It is intentionally measurement-ready rather than tutorial-style: customers receive a deterministic assignment, outcomes are measured in fixed windows, and aggregate marts expose lift, economics, and power checks.

The current dataset is historical and does not contain real campaign exposure logs. The assignment fields therefore represent a proposed randomized controlled test design and a historical backtest frame. In production, the same grain and metrics would be joined to an actual exposure table from the CRM platform.

## Experiment Definition

| Element | Definition |
| --- | --- |
| Business question | Can a day-21 CRM intervention increase or accelerate second purchase behavior? |
| Unit of randomization | Customer |
| Eligibility | Customer reached day 21 after first valid purchase without a second valid purchase |
| Assignment | Deterministic hash split, default 20% control and 80% treatment |
| Primary KPI | Second purchase conversion |
| Measurement windows | 30, 60, and 90 days after eligibility |
| Commercial readout | Incremental revenue, estimated contribution margin, campaign cost, net incremental value |

## dbt Models

| Model | Grain | Purpose |
| --- | --- | --- |
| `int_second_purchase_experiment_customers` | Customer | Eligibility date, proposed assignment, second-purchase outcome flags, and revenue windows |
| `mart_second_purchase_experiment_readout` | Measurement window x assignment | Conversion, revenue per eligible customer, and time-to-second-purchase readout |
| `mart_second_purchase_experiment_lift` | Measurement window | Treatment vs control lift, estimated economics, and scale decision |
| `mart_second_purchase_experiment_power` | One row | Approximate sample-size check for the configured minimum detectable effect |

## Metric Definitions

Second purchase conversion:

```text
Converted customers / eligible customers
```

Incremental conversion rate:

```text
Treatment conversion rate - control conversion rate
```

Incremental revenue per customer:

```text
Treatment revenue per eligible customer - control revenue per eligible customer
```

Net incremental value:

```text
Gross incremental revenue * contribution margin - treatment customers * campaign cost per customer
```

## Production Notes

- Replace proposed assignment with an immutable assignment table once a CRM platform executes the test.
- Join send, delivery, open, click, unsubscribe, and complaint events as guardrails.
- Keep the customer-level assignment grain stable even if a customer receives multiple messages.
- Report 30-day acceleration separately from 90-day incrementality to avoid mistaking pull-forward behavior for true demand creation.

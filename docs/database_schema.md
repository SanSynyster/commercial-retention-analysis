# Database Schema

## Purpose

This document shows the analytical warehouse model used by the dbt layer. It is a logical ERD for reviewer understanding rather than a physical OLTP schema. The model is optimized for retention analytics, product analytics, experimentation, churn/CLV analysis, and BI consumption.

## Model Grain

| Model | Grain | Primary Key Or Natural Key |
| --- | --- | --- |
| `stg_clean_transactions` | Transaction line | `invoice_no`, `stock_code`, `invoice_date`, line-level source fields |
| `int_customer_orders` | Customer invoice | `customer_id`, `invoice_no` |
| `int_customer_order_features` | Customer invoice | `customer_id`, `invoice_no` |
| `mart_customer_metrics` | Customer | `customer_id` |
| `mart_customer_segments` | Customer | `customer_id` |
| `mart_customer_churn_clv` | Customer | `customer_id` |
| `mart_retention_cohorts` | Cohort month x month index | `cohort_month`, `month_index` |
| `mart_customer_revenue_deciles` | Customer decile | `customer_decile` |
| `int_second_purchase_experiment_customers` | Customer | `customer_id` |
| `mart_second_purchase_experiment_readout` | Measurement window x assignment | `measurement_days`, `experiment_assignment` |
| `mart_second_purchase_experiment_lift` | Measurement window | `measurement_days` |
| `mart_second_purchase_experiment_power` | Experiment design summary | Single-row design summary |

## ERD

```mermaid
erDiagram
    STG_CLEAN_TRANSACTIONS {
        string invoice_no
        string stock_code
        string description
        int quantity
        timestamp invoice_date
        double unit_price
        bigint customer_id
        string country
        double line_revenue_gross
        boolean is_valid_order_line
        double analytical_revenue
    }

    INT_CUSTOMER_ORDERS {
        bigint customer_id
        string invoice_no
        timestamp order_date
        double order_revenue
    }

    INT_CUSTOMER_ORDER_FEATURES {
        bigint customer_id
        string invoice_no
        timestamp order_date
        double order_revenue
        int order_rank
        boolean is_first_order
        boolean is_repeat_order
        timestamp next_order_date
        int days_to_next_order
    }

    MART_CUSTOMER_METRICS {
        bigint customer_id
        int total_orders
        double revenue
        timestamp first_purchase
        timestamp last_purchase
        double aov
        int active_days
        boolean is_repeat_customer
        double first_order_revenue
        double repeat_order_revenue
        timestamp second_purchase
        int days_to_second_purchase
        int recency_days
    }

    MART_CUSTOMER_SEGMENTS {
        bigint customer_id
        string lifecycle_segment
        boolean is_high_value
        int total_orders
        double revenue
        double aov
        timestamp first_purchase
        timestamp last_purchase
        timestamp second_purchase
        int days_to_second_purchase
        int recency_days
        string crm_priority_group
    }

    MART_CUSTOMER_CHURN_CLV {
        bigint customer_id
        int total_orders
        double historical_clv
        double aov
        timestamp first_purchase
        timestamp last_purchase
        int recency_days
        boolean is_lapsed
        string churn_status
        double revenue_last_365d
        int orders_last_365d
        double observed_monthly_value
    }

    MART_RETENTION_COHORTS {
        date cohort_month
        int month_index
        int customers
        int cohort_size
        double retention_pct
    }

    MART_CUSTOMER_REVENUE_DECILES {
        string customer_decile
        int customers
        double revenue
        double customer_pct
        double revenue_pct
    }

    INT_SECOND_PURCHASE_EXPERIMENT_CUSTOMERS {
        bigint customer_id
        string first_invoice_no
        timestamp first_purchase
        double first_order_revenue
        timestamp eligibility_date
        string second_invoice_no
        timestamp second_purchase
        double second_order_revenue
        string experiment_assignment
        boolean converted_30d
        boolean converted_60d
        boolean converted_90d
    }

    MART_SECOND_PURCHASE_EXPERIMENT_READOUT {
        int measurement_days
        string experiment_assignment
        int eligible_customers
        int converted_customers
        double conversion_rate
        double second_purchase_revenue
        double revenue_per_eligible_customer
        double avg_days_to_second_purchase
        double median_days_to_second_purchase
    }

    MART_SECOND_PURCHASE_EXPERIMENT_LIFT {
        int measurement_days
        int treatment_customers
        int control_customers
        double treatment_conversion_rate
        double control_conversion_rate
        double incremental_conversion_rate
        double incremental_orders
        double gross_incremental_revenue
        double net_incremental_value
        string decision_flag
    }

    MART_SECOND_PURCHASE_EXPERIMENT_POWER {
        int eligible_customers
        int control_customers
        int treatment_customers
        double baseline_conversion_rate
        double minimum_detectable_effect
        double approximate_required_customers_per_arm
        boolean has_approximate_power_for_mde
    }

    STG_CLEAN_TRANSACTIONS ||--o{ INT_CUSTOMER_ORDERS : aggregates_to
    INT_CUSTOMER_ORDERS ||--|| INT_CUSTOMER_ORDER_FEATURES : ranks_orders
    INT_CUSTOMER_ORDER_FEATURES }o--|| MART_CUSTOMER_METRICS : rolls_up_to_customer
    MART_CUSTOMER_METRICS ||--|| MART_CUSTOMER_SEGMENTS : segments_customer
    MART_CUSTOMER_METRICS ||--|| MART_CUSTOMER_CHURN_CLV : enriches_value_and_lapse
    INT_CUSTOMER_ORDERS }o--o{ MART_RETENTION_COHORTS : contributes_to_cohort
    MART_CUSTOMER_METRICS }o--o{ MART_CUSTOMER_REVENUE_DECILES : contributes_to_decile
    INT_CUSTOMER_ORDER_FEATURES }o--|| INT_SECOND_PURCHASE_EXPERIMENT_CUSTOMERS : defines_outcomes
    MART_CUSTOMER_METRICS ||--|| INT_SECOND_PURCHASE_EXPERIMENT_CUSTOMERS : defines_eligibility
    INT_SECOND_PURCHASE_EXPERIMENT_CUSTOMERS }o--o{ MART_SECOND_PURCHASE_EXPERIMENT_READOUT : aggregates_by_assignment
    MART_SECOND_PURCHASE_EXPERIMENT_READOUT }o--|| MART_SECOND_PURCHASE_EXPERIMENT_LIFT : compares_treatment_control
    INT_SECOND_PURCHASE_EXPERIMENT_CUSTOMERS }o--|| MART_SECOND_PURCHASE_EXPERIMENT_POWER : estimates_design_power
```

## Design Notes

- Customer-level analytics are scoped to identifiable customers with valid positive purchase lines.
- `int_customer_orders` is the core fact table for lifecycle and retention logic.
- `mart_customer_metrics` is the main customer dimension-like mart for BI, segmentation, churn/CLV, and experimentation.
- Experiment marts separate customer-level eligibility/outcomes from aggregate readout and treatment-control lift.
- Revenue reconciliation is tested through dbt singular tests to keep transaction, order, and customer grains aligned.

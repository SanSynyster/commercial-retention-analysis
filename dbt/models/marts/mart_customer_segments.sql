with customers as (
    select * from {{ ref('mart_customer_metrics') }}
),

thresholds as (
    select
        quantile_cont(revenue, {{ var('high_value_percentile') }}) as high_value_revenue_threshold
    from customers
),

segmented as (
    select
        customers.*,
        customers.revenue >= thresholds.high_value_revenue_threshold as is_high_value,
        case
            when customers.total_orders = 1
                and customers.recency_days between {{ var('experiment_trigger_day') }} and {{ var('lapse_days') }} - 1
                then 'Second Purchase Accelerator'
            when customers.total_orders = 1
                and customers.recency_days >= {{ var('lapse_days') }}
                then 'One-Time Lapsed'
            when customers.total_orders > 1
                and customers.recency_days >= {{ var('lapse_days') }}
                then 'Repeat Lapsed'
            when customers.total_orders > 1
                and customers.recency_days between 60 and {{ var('lapse_days') }} - 1
                then 'Repeat At Risk'
            when customers.total_orders > 1
                then 'Active Repeat'
            else 'New Customer'
        end as lifecycle_segment
    from customers
    cross join thresholds
)

select
    customer_id,
    lifecycle_segment,
    is_high_value,
    total_orders,
    revenue,
    aov,
    first_purchase,
    last_purchase,
    second_purchase,
    days_to_second_purchase,
    recency_days,
    case
        when is_high_value and lifecycle_segment in ('Repeat Lapsed', 'Repeat At Risk') then 'P1 High-Value Lapse Prevention'
        when lifecycle_segment = 'Second Purchase Accelerator' then 'P2 Second Purchase Acceleration'
        when lifecycle_segment in ('Repeat Lapsed', 'One-Time Lapsed') then 'P3 Winback'
        when is_high_value then 'P4 High-Value Nurture'
        else 'P5 Standard Lifecycle'
    end as crm_priority_group
from segmented

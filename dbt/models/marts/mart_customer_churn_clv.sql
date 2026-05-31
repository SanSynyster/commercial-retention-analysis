with customers as (
    select * from {{ ref('mart_customer_metrics') }}
),

orders as (
    select * from {{ ref('int_customer_order_features') }}
),

clv_windows as (
    select
        customer_id,
        sum(case
            when order_date >= cast('{{ var("analysis_as_of_date") }}' as date) - interval '{{ var("clv_lookback_days") }} days'
                then order_revenue
            else 0
        end) as revenue_last_{{ var('clv_lookback_days') }}d,
        count(distinct case
            when order_date >= cast('{{ var("analysis_as_of_date") }}' as date) - interval '{{ var("clv_lookback_days") }} days'
                then invoice_no
        end) as orders_last_{{ var('clv_lookback_days') }}d
    from orders
    group by customer_id
)

select
    customers.customer_id,
    customers.total_orders,
    customers.revenue as historical_clv,
    customers.aov,
    customers.first_purchase,
    customers.last_purchase,
    customers.recency_days,
    customers.recency_days >= {{ var('lapse_days') }} as is_lapsed,
    case
        when customers.recency_days >= {{ var('lapse_days') }} then 'Lapsed'
        when customers.recency_days >= 60 then 'At Risk'
        else 'Active'
    end as churn_status,
    clv_windows.revenue_last_{{ var('clv_lookback_days') }}d,
    clv_windows.orders_last_{{ var('clv_lookback_days') }}d,
    case
        when customers.total_orders > 1 then customers.revenue / nullif(date_diff('month', customers.first_purchase, customers.last_purchase) + 1, 0)
        else customers.revenue
    end as observed_monthly_value
from customers
left join clv_windows
    on customers.customer_id = clv_windows.customer_id

with source_revenue as (
    select sum(analytical_revenue) as revenue
    from {{ ref('stg_clean_transactions') }}
    where is_valid_order_line
),

order_revenue as (
    select sum(order_revenue) as revenue
    from {{ ref('int_customer_orders') }}
)

select
    source_revenue.revenue as source_revenue,
    order_revenue.revenue as order_revenue
from source_revenue
cross join order_revenue
where abs(source_revenue.revenue - order_revenue.revenue) > 0.01

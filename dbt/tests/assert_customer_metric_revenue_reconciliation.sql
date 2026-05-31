with order_revenue as (
    select sum(order_revenue) as revenue
    from {{ ref('int_customer_orders') }}
),

customer_revenue as (
    select sum(revenue) as revenue
    from {{ ref('mart_customer_metrics') }}
)

select
    order_revenue.revenue as order_revenue,
    customer_revenue.revenue as customer_revenue
from order_revenue
cross join customer_revenue
where abs(order_revenue.revenue - customer_revenue.revenue) > 0.01

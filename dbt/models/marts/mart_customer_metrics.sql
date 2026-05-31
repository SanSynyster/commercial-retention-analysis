with customer_orders as (
    select * from {{ ref('int_customer_order_features') }}
),

customer_rollup as (
    select
        customer_id,
        count(distinct invoice_no) as total_orders,
        sum(order_revenue) as revenue,
        min(order_date) as first_purchase,
        max(order_date) as last_purchase,
        sum(case when is_first_order then order_revenue else 0 end) as first_order_revenue,
        sum(case when is_repeat_order then order_revenue else 0 end) as repeat_order_revenue,
        min(case when order_rank = 2 then order_date end) as second_purchase
    from customer_orders
    group by customer_id
)

select
    customer_id,
    total_orders,
    revenue,
    first_purchase,
    last_purchase,
    revenue / total_orders as aov,
    date_diff('day', first_purchase, last_purchase) as active_days,
    total_orders > 1 as is_repeat_customer,
    first_order_revenue,
    repeat_order_revenue,
    second_purchase,
    date_diff('day', first_purchase, second_purchase) as days_to_second_purchase,
    cast('{{ var("analysis_as_of_date") }}' as date) as analysis_as_of_date,
    date_diff('day', last_purchase, cast('{{ var("analysis_as_of_date") }}' as date)) as recency_days
from customer_rollup

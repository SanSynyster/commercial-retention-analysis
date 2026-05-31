with ranked as (
    select
        customer_id,
        invoice_no,
        order_date,
        order_revenue,
        row_number() over (
            partition by customer_id
            order by order_date, invoice_no
        ) as order_rank,
        lead(order_date) over (
            partition by customer_id
            order by order_date, invoice_no
        ) as next_order_date
    from {{ ref('int_customer_orders') }}
)

select
    customer_id,
    invoice_no,
    order_date,
    order_revenue,
    order_rank,
    order_rank = 1 as is_first_order,
    order_rank > 1 as is_repeat_order,
    next_order_date,
    date_diff('day', order_date, next_order_date) as days_to_next_order
from ranked

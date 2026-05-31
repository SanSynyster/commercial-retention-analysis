with valid_order_lines as (
    select
        customer_id,
        invoice_no,
        invoice_date,
        analytical_revenue
    from {{ ref('stg_clean_transactions') }}
    where is_valid_order_line
)

select
    customer_id,
    invoice_no,
    min(invoice_date) as order_date,
    sum(analytical_revenue) as order_revenue
from valid_order_lines
group by
    customer_id,
    invoice_no
having sum(analytical_revenue) > 0

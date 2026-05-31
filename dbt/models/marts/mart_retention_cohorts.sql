with orders_with_months as (
    select
        customer_id,
        invoice_no,
        order_date,
        date_trunc('month', order_date)::date as order_month,
        min(date_trunc('month', order_date)::date) over (
            partition by customer_id
        ) as cohort_month
    from {{ ref('int_customer_orders') }}
),

cohort_activity as (
    select
        cohort_month,
        date_diff('month', cohort_month, order_month) as month_index,
        count(distinct customer_id) as customers
    from orders_with_months
    group by
        cohort_month,
        date_diff('month', cohort_month, order_month)
),

cohort_sizes as (
    select
        cohort_month,
        customers as cohort_size
    from cohort_activity
    where month_index = 0
)

select
    cohort_activity.cohort_month,
    cohort_activity.month_index,
    cohort_activity.customers,
    cohort_sizes.cohort_size,
    cohort_activity.customers / cohort_sizes.cohort_size as retention_pct
from cohort_activity
inner join cohort_sizes
    on cohort_activity.cohort_month = cohort_sizes.cohort_month

with customer_orders as (
    select * from {{ ref('int_customer_order_features') }}
),

customer_metrics as (
    select * from {{ ref('mart_customer_metrics') }}
),

first_orders as (
    select
        customer_id,
        invoice_no as first_invoice_no,
        order_date as first_purchase,
        order_revenue as first_order_revenue
    from customer_orders
    where order_rank = 1
),

second_orders as (
    select
        customer_id,
        invoice_no as second_invoice_no,
        order_date as second_purchase,
        order_revenue as second_order_revenue
    from customer_orders
    where order_rank = 2
),

eligible_customers as (
    select
        first_orders.customer_id,
        first_orders.first_invoice_no,
        first_orders.first_purchase,
        first_orders.first_order_revenue,
        first_orders.first_purchase + interval '{{ var("experiment_trigger_day") }} days' as eligibility_date,
        second_orders.second_invoice_no,
        second_orders.second_purchase,
        second_orders.second_order_revenue,
        customer_metrics.total_orders,
        customer_metrics.revenue as customer_revenue,
        customer_metrics.aov,
        customer_metrics.recency_days
    from first_orders
    left join second_orders
        on first_orders.customer_id = second_orders.customer_id
    inner join customer_metrics
        on first_orders.customer_id = customer_metrics.customer_id
    where second_orders.second_purchase is null
        or second_orders.second_purchase > first_orders.first_purchase + interval '{{ var("experiment_trigger_day") }} days'
)

select
    customer_id,
    first_invoice_no,
    first_purchase,
    first_order_revenue,
    eligibility_date,
    second_invoice_no,
    second_purchase,
    second_order_revenue,
    total_orders,
    customer_revenue,
    aov,
    recency_days,
    case
        when abs(hash(customer_id)) % 100 < cast({{ var('experiment_control_pct') }} * 100 as integer) then 'control'
        else 'treatment'
    end as experiment_assignment,
    second_purchase is not null as converted_second_purchase,
    date_diff('day', eligibility_date, second_purchase) as days_from_eligibility_to_second_purchase,
    coalesce(second_purchase <= eligibility_date + interval '30 days', false) as converted_30d,
    coalesce(second_purchase <= eligibility_date + interval '60 days', false) as converted_60d,
    coalesce(second_purchase <= eligibility_date + interval '90 days', false) as converted_90d,
    case when second_purchase <= eligibility_date + interval '30 days' then second_order_revenue else 0 end as second_purchase_revenue_30d,
    case when second_purchase <= eligibility_date + interval '60 days' then second_order_revenue else 0 end as second_purchase_revenue_60d,
    case when second_purchase <= eligibility_date + interval '90 days' then second_order_revenue else 0 end as second_purchase_revenue_90d
from eligible_customers

with ranked as (
    select
        customer_id,
        revenue,
        row_number() over (order by revenue desc, customer_id) as customer_rank,
        count(*) over () as total_customers,
        sum(revenue) over () as total_revenue
    from {{ ref('mart_customer_metrics') }}
),

deciled as (
    select
        customer_id,
        revenue,
        total_customers,
        total_revenue,
        ntile(10) over (order by customer_rank) as decile_number
    from ranked
)

select
    case decile_number
        when 1 then 'Top 10%'
        when 2 then '10-20%'
        when 3 then '20-30%'
        when 4 then '30-40%'
        when 5 then '40-50%'
        when 6 then '50-60%'
        when 7 then '60-70%'
        when 8 then '70-80%'
        when 9 then '80-90%'
        else 'Bottom 10%'
    end as customer_decile,
    count(*) as customers,
    sum(revenue) as revenue,
    count(*) / max(total_customers) as customer_pct,
    sum(revenue) / max(total_revenue) as revenue_pct
from deciled
group by decile_number
order by decile_number

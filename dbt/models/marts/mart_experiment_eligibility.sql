with customers as (
    select * from {{ ref('mart_customer_segments') }}
)

select
    customer_id,
    first_purchase,
    last_purchase,
    revenue,
    aov,
    recency_days,
    lifecycle_segment,
    crm_priority_group,
    total_orders = 1
        and recency_days >= {{ var('experiment_trigger_day') }}
        and recency_days < {{ var('lapse_days') }} as is_second_purchase_experiment_eligible,
    case
        when abs(hash(customer_id)) % 5 = 0 then 'control'
        else 'treatment'
    end as proposed_assignment,
    cast('{{ var("analysis_as_of_date") }}' as date) as eligibility_date,
    cast('{{ var("analysis_as_of_date") }}' as date) + interval '{{ var("experiment_measurement_days") }} days' as measurement_end_date
from customers
where total_orders = 1

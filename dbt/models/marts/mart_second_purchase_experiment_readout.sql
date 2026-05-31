with experiment_customers as (
    select * from {{ ref('int_second_purchase_experiment_customers') }}
),

windowed as (
    select
        30 as measurement_days,
        experiment_assignment,
        count(*) as eligible_customers,
        sum(case when converted_30d then 1 else 0 end) as converted_customers,
        sum(second_purchase_revenue_30d) as second_purchase_revenue,
        avg(case when converted_30d then days_from_eligibility_to_second_purchase end) as avg_days_to_second_purchase,
        median(case when converted_30d then days_from_eligibility_to_second_purchase end) as median_days_to_second_purchase
    from experiment_customers
    group by experiment_assignment

    union all

    select
        60 as measurement_days,
        experiment_assignment,
        count(*) as eligible_customers,
        sum(case when converted_60d then 1 else 0 end) as converted_customers,
        sum(second_purchase_revenue_60d) as second_purchase_revenue,
        avg(case when converted_60d then days_from_eligibility_to_second_purchase end) as avg_days_to_second_purchase,
        median(case when converted_60d then days_from_eligibility_to_second_purchase end) as median_days_to_second_purchase
    from experiment_customers
    group by experiment_assignment

    union all

    select
        90 as measurement_days,
        experiment_assignment,
        count(*) as eligible_customers,
        sum(case when converted_90d then 1 else 0 end) as converted_customers,
        sum(second_purchase_revenue_90d) as second_purchase_revenue,
        avg(case when converted_90d then days_from_eligibility_to_second_purchase end) as avg_days_to_second_purchase,
        median(case when converted_90d then days_from_eligibility_to_second_purchase end) as median_days_to_second_purchase
    from experiment_customers
    group by experiment_assignment
)

select
    measurement_days,
    experiment_assignment,
    eligible_customers,
    converted_customers,
    converted_customers / nullif(eligible_customers, 0) as conversion_rate,
    second_purchase_revenue,
    second_purchase_revenue / nullif(eligible_customers, 0) as revenue_per_eligible_customer,
    avg_days_to_second_purchase,
    median_days_to_second_purchase
from windowed

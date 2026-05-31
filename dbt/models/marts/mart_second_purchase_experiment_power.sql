with experiment_base as (
    select * from {{ ref('int_second_purchase_experiment_customers') }}
),

summary as (
    select
        count(*) as eligible_customers,
        sum(case when experiment_assignment = 'control' then 1 else 0 end) as control_customers,
        sum(case when experiment_assignment = 'treatment' then 1 else 0 end) as treatment_customers,
        avg(case when converted_60d then 1.0 else 0.0 end) as baseline_conversion_rate
    from experiment_base
),

parameters as (
    select
        eligible_customers,
        control_customers,
        treatment_customers,
        baseline_conversion_rate,
        {{ var('minimum_detectable_effect_pp') }} / 100.0 as minimum_detectable_effect,
        1.96 as z_alpha_95,
        0.84 as z_power_80
    from summary
)

select
    eligible_customers,
    control_customers,
    treatment_customers,
    baseline_conversion_rate,
    minimum_detectable_effect,
    power(
        (z_alpha_95 + z_power_80)
        * sqrt(2 * baseline_conversion_rate * (1 - baseline_conversion_rate))
        / nullif(minimum_detectable_effect, 0),
        2
    ) as approximate_required_customers_per_arm,
    least(control_customers, treatment_customers) as smallest_observed_arm,
    least(control_customers, treatment_customers) >= power(
        (z_alpha_95 + z_power_80)
        * sqrt(2 * baseline_conversion_rate * (1 - baseline_conversion_rate))
        / nullif(minimum_detectable_effect, 0),
        2
    ) as has_approximate_power_for_mde
from parameters

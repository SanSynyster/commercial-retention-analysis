with readout as (
    select * from {{ ref('mart_second_purchase_experiment_readout') }}
),

treatment as (
    select *
    from readout
    where experiment_assignment = 'treatment'
),

control as (
    select *
    from readout
    where experiment_assignment = 'control'
)

select
    treatment.measurement_days,
    treatment.eligible_customers as treatment_customers,
    control.eligible_customers as control_customers,
    treatment.conversion_rate as treatment_conversion_rate,
    control.conversion_rate as control_conversion_rate,
    treatment.conversion_rate - control.conversion_rate as incremental_conversion_rate,
    treatment.revenue_per_eligible_customer as treatment_revenue_per_customer,
    control.revenue_per_eligible_customer as control_revenue_per_customer,
    treatment.revenue_per_eligible_customer - control.revenue_per_eligible_customer as incremental_revenue_per_customer,
    treatment.eligible_customers * (treatment.conversion_rate - control.conversion_rate) as incremental_orders,
    treatment.eligible_customers * (treatment.revenue_per_eligible_customer - control.revenue_per_eligible_customer) as gross_incremental_revenue,
    treatment.eligible_customers
        * (treatment.revenue_per_eligible_customer - control.revenue_per_eligible_customer)
        * {{ var('contribution_margin_pct') }} as estimated_incremental_margin,
    treatment.eligible_customers * {{ var('campaign_cost_per_treated_customer') }} as campaign_operating_cost,
    treatment.eligible_customers
        * (treatment.revenue_per_eligible_customer - control.revenue_per_eligible_customer)
        * {{ var('contribution_margin_pct') }}
        - treatment.eligible_customers * {{ var('campaign_cost_per_treated_customer') }} as net_incremental_value,
    case
        when treatment.conversion_rate - control.conversion_rate >= {{ var('minimum_detectable_effect_pp') }} / 100.0
            and treatment.eligible_customers
                * (treatment.revenue_per_eligible_customer - control.revenue_per_eligible_customer)
                * {{ var('contribution_margin_pct') }}
                - treatment.eligible_customers * {{ var('campaign_cost_per_treated_customer') }} > 0
            then 'Scale candidate'
        when treatment.conversion_rate - control.conversion_rate > 0
            then 'Promising but under MDE'
        else 'Do not scale'
    end as decision_flag
from treatment
inner join control
    on treatment.measurement_days = control.measurement_days

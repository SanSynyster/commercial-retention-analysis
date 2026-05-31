with expected as (
    select 30 as measurement_days
    union all
    select 60 as measurement_days
    union all
    select 90 as measurement_days
),

actual as (
    select measurement_days
    from {{ ref('mart_second_purchase_experiment_lift') }}
)

select expected.measurement_days
from expected
left join actual
    on expected.measurement_days = actual.measurement_days
where actual.measurement_days is null

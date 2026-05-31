select *
from {{ ref('mart_experiment_eligibility') }}
where is_second_purchase_experiment_eligible
    and proposed_assignment not in ('control', 'treatment')

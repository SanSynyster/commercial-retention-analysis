select *
from {{ ref('mart_second_purchase_experiment_readout') }}
where conversion_rate < 0
    or conversion_rate > 1
    or revenue_per_eligible_customer < 0

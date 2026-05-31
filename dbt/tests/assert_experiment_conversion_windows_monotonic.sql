select *
from {{ ref('int_second_purchase_experiment_customers') }}
where (converted_30d and not converted_60d)
    or (converted_60d and not converted_90d)

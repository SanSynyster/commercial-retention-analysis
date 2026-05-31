select *
from {{ ref('mart_retention_cohorts') }}
where retention_pct < 0
    or retention_pct > 1

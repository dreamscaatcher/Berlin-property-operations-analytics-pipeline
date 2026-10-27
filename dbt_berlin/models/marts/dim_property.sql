-- Mart: property dimension, enriched with unit counts and floor area.

with properties as (
    select * from {{ ref('stg_properties') }}
),

units as (
    select
        property_id,
        count(*)       as unit_count,
        sum(area_m2)   as total_area_m2
    from {{ ref('stg_units') }}
    group by property_id
)

select
    p.*,
    coalesce(u.unit_count, 0)      as unit_count,
    u.total_area_m2
from properties p
left join units u using (property_id)

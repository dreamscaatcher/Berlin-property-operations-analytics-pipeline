-- Staging: one clean row per property.

select
    upper(property_id)                    as property_id,
    property_name,
    city,
    district,
    property_type,
    cast(year_built as integer)           as year_built,
    cast(has_lift as boolean)             as has_lift,
    heating_source,
    cast(management_since as date)        as management_since
from {{ source('raw', 'properties') }}

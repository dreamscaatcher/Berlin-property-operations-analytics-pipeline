-- Staging: one clean row per rental unit.

select
    unit_id,
    upper(property_id)                    as property_id,
    unit_no,
    unit_type,
    cast(floor as integer)                as floor,
    cast(rooms as integer)                as rooms,
    try_cast(area_m2 as decimal(8, 1))    as area_m2
from {{ source('raw', 'units') }}

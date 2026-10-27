-- Staging: split 'P1 Notfall' into a code ('P1') and a label ('Notfall').

select
    left(priority, 2)                             as priority,
    trim(substr(priority, 4))                     as priority_label,
    cast(sla_response_hours as integer)           as sla_response_hours,
    cast(sla_resolution_hours as integer)         as sla_resolution_hours
from {{ source('raw', 'priorities') }}

-- Staging: one clean row per maintenance ticket.
-- Only cleaning here: rename, cast types, standardise values, remove junk + duplicates.
-- No joins and no business rules (those belong in marts).

with source as (

    select * from {{ source('raw', 'tickets') }}

),

cleaned as (

    select
        ticket_id,
        upper(property_id)                                   as property_id,     -- 'p562' -> 'P562'
        unit_id,
        category,
        left(priority, 2)                                    as priority,        -- 'P1 Notfall' -> 'P1'
        channel,
        contractor_id,
        coalesce(
            try_strptime(created_at, '%Y-%m-%d %H:%M:%S'),                       -- ISO text
            try_strptime(created_at, '%d.%m.%Y %H:%M')                           -- German text
        )                                                    as created_at,
        try_cast(resolved_at as timestamp)                   as resolved_at,
        status,
        status in ('Neu', 'In Bearbeitung', 'Wartet auf Material/Freigabe')
                                                             as is_open,
        cast(cost_eur as decimal(12, 2))                     as cost_eur
    from source
    where ticket_id not like 'TEST%'                                             -- drop test tickets

)

select distinct * from cleaned                                                   -- drop duplicate export rows

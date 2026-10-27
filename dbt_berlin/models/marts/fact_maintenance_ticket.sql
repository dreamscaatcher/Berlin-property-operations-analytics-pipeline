-- Mart: one row per ticket, joined to property + priority, with BUSINESS RULES:
--   resolution_hours   = hours from created to resolved
--   met_resolution_sla = resolved within the SLA hours of its priority
--                        (open/cancelled tickets -> null, they are not measured)

with tickets as (
    select * from {{ ref('stg_tickets') }}
),

priorities as (
    select * from {{ ref('stg_priorities') }}
),

properties as (
    select property_id, district, property_type from {{ ref('dim_property') }}
)

select
    t.ticket_id,
    t.property_id,
    p.district,
    p.property_type,
    t.unit_id,
    t.category,
    t.priority,
    pr.priority_label,
    t.status,
    t.is_open,
    t.created_at,
    cast(t.created_at as date)                                   as created_date,
    date_trunc('month', t.created_at)::date                      as created_month,
    t.resolved_at,
    round(date_diff('minute', t.created_at, t.resolved_at) / 60.0, 2)
                                                                 as resolution_hours,
    pr.sla_resolution_hours,
    case
        when t.resolved_at is null or t.status = 'Storniert' then null
        else date_diff('minute', t.created_at, t.resolved_at) / 60.0 <= pr.sla_resolution_hours
    end                                                          as met_resolution_sla,
    t.cost_eur
from tickets t
left join priorities pr using (priority)
left join properties p using (property_id)

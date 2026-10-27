-- Mart: aggregated KPIs per district and month - ready for a Power BI chart.

select
    district,
    created_month,
    count(*)                                                         as tickets,
    count(*) filter (where is_open)                                  as open_tickets,
    count(met_resolution_sla)                                        as measured_tickets,
    count(*) filter (where met_resolution_sla)                       as met_sla_tickets,
    round(count(*) filter (where met_resolution_sla)
          / nullif(count(met_resolution_sla), 0), 3)                 as resolution_sla_rate,
    sum(cost_eur)                                                    as total_cost_eur
from {{ ref('fact_maintenance_ticket') }}
group by district, created_month

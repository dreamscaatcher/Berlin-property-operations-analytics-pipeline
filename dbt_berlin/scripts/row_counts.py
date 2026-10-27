"""Row counts raw vs staging vs marts, plus what staging removed, plus a mart sample."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import duckdb
con = duckdb.connect(str(ROOT / "berlin.duckdb"), read_only=True)
def show(title, sql):
    print(f"\n-- {title}\n{sql.strip()}\n")
    print(con.sql(sql))

show("1. Row counts per layer", """
select 'raw'     as layer, 'raw.tickets'                         as table_name, count(*) as rows from raw.tickets
union all select 'staging', 'staging.stg_tickets',                 count(*) from staging.stg_tickets
union all select 'mart',    'marts.fact_maintenance_ticket',       count(*) from marts.fact_maintenance_ticket
union all select 'raw',     'raw.properties',                      count(*) from raw.properties
union all select 'staging', 'staging.stg_properties',              count(*) from staging.stg_properties
union all select 'mart',    'marts.dim_property',                  count(*) from marts.dim_property
union all select 'raw',     'raw.units',                           count(*) from raw.units
union all select 'staging', 'staging.stg_units',                   count(*) from staging.stg_units
union all select 'raw',     'raw.priorities',                      count(*) from raw.priorities
union all select 'staging', 'staging.stg_priorities',              count(*) from staging.stg_priorities
union all select 'mart',    'marts.mart_tickets_by_district_month', count(*) from marts.mart_tickets_by_district_month
""")
show("2. What staging cleaned up in tickets", """
select
    count(*) filter (where ticket_id like 'TEST%')                         as test_rows_in_raw,
    count(*) - count(distinct ticket_id) - count(*) filter (where ticket_id like 'TEST%') + 3 as duplicate_rows_in_raw,
    count(*) filter (where property_id <> upper(property_id))              as lowercase_ids_in_raw,
    count(*) filter (where created_at like '__.__.____%')                  as german_dates_in_raw,
    (select count(*) from staging.stg_tickets where property_id <> upper(property_id)) as lowercase_ids_in_staging
from raw.tickets
""")
show("3. Messy vs clean: same ticket in raw and in staging", """
select 'raw' as layer, ticket_id, property_id, priority, created_at::varchar as created_at from raw.tickets where ticket_id = (select ticket_id from raw.tickets limit 1 offset 69)
union all
select 'staging', ticket_id, property_id, priority, created_at::varchar from staging.stg_tickets where ticket_id = (select ticket_id from raw.tickets limit 1 offset 69)
""")
show("4. Sample of the aggregated mart (Mitte, 2026)", """
select * from marts.mart_tickets_by_district_month
where district = 'Mitte' and created_month >= '2026-01-01'
order by created_month limit 9
""")
show("5. The 190 tickets that fail the test (first 5)", """
select ticket_id, created_at, resolved_at, resolution_hours from marts.fact_maintenance_ticket
where resolved_at < created_at order by ticket_id limit 5
""")
show("6. Resolution SLA rate by priority (business rule in the mart)", """
select priority, priority_label, count(met_resolution_sla) as measured,
       round(avg(met_resolution_sla::int), 3) as sla_rate
from marts.fact_maintenance_ticket group by all order by priority
""")

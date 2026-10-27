"""
load_raw.py - builds the RAW layer in berlin.duckdb (schema `raw`).

In a real company a loading tool (Fivetran, Airbyte, a nightly export...) would
copy data from the source systems into raw tables. dbt does NOT load data; it
only transforms data that is already in the database. This script plays the
role of that loading tool.

TEACHING NOTE - DELIBERATE MESSINESS
The synthetic Berlin CSVs are already fairly clean, so this script makes the
raw tickets table messy ON PURPOSE, so the staging layer has real work to do:
  1. every 10th ticket: property_id written in lowercase      ('p562' instead of 'P562')
  2. every 7th ticket : created_at stored as German text       ('16.06.2026 15:10')
                        all other tickets: ISO text            ('2026-06-16 15:10:00')
  3. the first 25 tickets are exported twice                   (duplicate rows)
  4. 3 test tickets ('TEST-001'..'TEST-003', property 'P999')   (junk rows)
  5. priorities come as 'P1 Notfall' etc. (code + German label in one field)
Messiness 1-4 is invented for teaching only. Messiness 5 is how the CSV really is.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
import duckdb

# Input: the clean CSVs exported by the main pipeline (../powerbi/csv).
# Fallback: dbt_berlin/data/ if you copied the 4 CSVs there yourself.
_main = ROOT.parent / "powerbi" / "csv"
CSV = (_main if (_main / "fact_maintenance_ticket.csv").exists() else ROOT / "data").as_posix() + "/"
con = duckdb.connect(str(ROOT / "berlin.duckdb"))
con.sql("create schema if not exists raw")

# Properties, units, priorities: copied 1:1 from the CSV (everything kept as text, like a raw export)
for table, file in [("properties", "dim_property"), ("units", "dim_unit"), ("priorities", "dim_priority")]:
    con.sql(f"create or replace table raw.{table} as select * from read_csv('{CSV}{file}.csv', all_varchar=true, header=true)")

# Tickets: only the columns the source system would deliver (no pre-computed SLA flags)
con.sql(f"""
create or replace table raw.tickets as
with src as (
    select row_number() over (order by ticket_id) as rn, *
    from read_csv('{CSV}fact_maintenance_ticket.csv', all_varchar=true, header=true)
),
messy as (
    select
        rn,
        ticket_id,
        case when rn % 10 = 0 then lower(property_id) else property_id end as property_id,
        unit_id,
        category,
        priority,
        channel,
        contractor_id,
        case when rn % 7 = 0 then strftime(created_at::timestamp, '%d.%m.%Y %H:%M')
             else created_at end                                         as created_at,
        resolved_at,
        status,
        cost_eur
    from src
)
select * exclude (rn) from messy
union all
select * exclude (rn) from messy where rn <= 25            -- duplicate export
union all
select * from (values
    ('TEST-001','P999',null,'Sonstiges','P4 Niedrig','Mieterportal',null,'2026-09-01 10:00:00',null,'Neu','0'),
    ('TEST-002','P999',null,'Sonstiges','P4 Niedrig','Mieterportal',null,'2026-09-01 10:05:00',null,'Neu','0'),
    ('TEST-003','P999',null,'Sonstiges','P4 Niedrig','Mieterportal',null,'2026-09-01 10:10:00',null,'Neu','0')
) as t(ticket_id,property_id,unit_id,category,priority,channel,contractor_id,created_at,resolved_at,status,cost_eur)
""")

for t in ["properties", "units", "priorities", "tickets"]:
    n = con.execute(f"select count(*) from raw.{t}").fetchone()[0]
    print(f"raw.{t:<11} {n:>8,} rows")
con.close()

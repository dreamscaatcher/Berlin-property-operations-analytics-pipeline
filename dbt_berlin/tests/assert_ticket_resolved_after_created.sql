-- Singular test (written by hand). dbt treats every row this query returns as a FAILURE.
-- Rule: a ticket cannot be resolved before it was created.
-- EXPECTED TO FAIL: the source system really contains tickets with impossible timestamps
-- (resolved_at earlier than created_at). This is NOT messiness added by load_raw.py.

select
    ticket_id,
    created_at,
    resolved_at
from {{ ref('fact_maintenance_ticket') }}
where resolved_at < created_at

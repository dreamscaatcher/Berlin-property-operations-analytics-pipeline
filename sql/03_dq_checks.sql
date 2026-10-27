-- =====================================================================
-- 03_dq_checks.sql : data-quality checks on the RAW layer
-- Each check returns the number of failing rows. Results land in dq.results
-- and the failing keys in dq.failed_keys (for the QA report).
-- =====================================================================
CREATE OR REPLACE TABLE dq.failed_keys AS
-- DQ01 duplicate ticket_id (expect unique)
SELECT 'DQ01' AS check_id, ticket_id AS key FROM raw.fact_maintenance_ticket GROUP BY ticket_id HAVING COUNT(*) > 1
UNION ALL
-- DQ02 resolved before created
SELECT DISTINCT 'DQ02', ticket_id FROM raw.fact_maintenance_ticket WHERE resolved_at < created_at
UNION ALL
-- DQ03 unit area missing or <= 0
SELECT 'DQ03', unit_id FROM raw.dim_unit WHERE area_m2 IS NULL OR area_m2 <= 0
UNION ALL
-- DQ04 rent-roll lines whose unit_id is not in unit master (orphan FK)
SELECT DISTINCT 'DQ04', r.unit_id FROM raw.fact_rent_roll r LEFT JOIN raw.dim_unit u USING (unit_id) WHERE u.unit_id IS NULL
UNION ALL
-- DQ05 same bank reference booked more than once (double bank-statement import)
SELECT 'DQ05', bank_ref FROM raw.fact_payment GROUP BY bank_ref HAVING COUNT(*) > 1
UNION ALL
-- DQ06 service-charge statement issued before the billing period ended
SELECT 'DQ06', statement_id FROM raw.fact_service_charge_statement WHERE issued_date <= period_end
UNION ALL
-- DQ07 statement header total <> sum of cost lines (tolerance 1 EUR)
SELECT 'DQ07', s.statement_id FROM raw.fact_service_charge_statement s
JOIN (SELECT statement_id, SUM(actual_cost) c FROM raw.fact_service_charge_cost GROUP BY 1) l USING (statement_id)
WHERE ABS(s.actual_costs_total - l.c) > 1
UNION ALL
-- DQ08 payments referencing unknown rent-roll lines
SELECT 'DQ08', p.payment_id FROM raw.fact_payment p LEFT JOIN raw.fact_rent_roll r USING (rent_roll_id) WHERE r.rent_roll_id IS NULL
UNION ALL
-- DQ09 total_due <> kaltmiete + NK prepayment
SELECT 'DQ09', CAST(rent_roll_id AS VARCHAR) FROM raw.fact_rent_roll WHERE ABS(total_due - kaltmiete_due - nk_prepayment_due) > 0.01
UNION ALL
-- DQ10 tickets with status 'Erledigt' but no resolved_at, or resolved_at in the future
SELECT 'DQ10', ticket_id FROM raw.fact_maintenance_ticket
WHERE (status = 'Erledigt' AND resolved_at IS NULL) OR resolved_at > TIMESTAMP '2026-09-30 23:59:59'
UNION ALL
-- DQ11 overlapping tenancies on the same unit
SELECT DISTINCT 'DQ11', a.unit_id FROM raw.dim_tenant a JOIN raw.dim_tenant b
  ON a.unit_id = b.unit_id AND a.tenant_id < b.tenant_id
 AND a.lease_start < COALESCE(b.lease_end, DATE '2099-12-31') AND b.lease_start < COALESCE(a.lease_end, DATE '2099-12-31')
UNION ALL
-- DQ12 tickets for unknown property / unit
SELECT 'DQ12', t.ticket_id FROM raw.fact_maintenance_ticket t
LEFT JOIN raw.dim_property p USING (property_id) LEFT JOIN raw.dim_unit u ON t.unit_id = u.unit_id
WHERE p.property_id IS NULL OR (t.unit_id IS NOT NULL AND u.unit_id IS NULL);

CREATE OR REPLACE TABLE dq.check_catalog (check_id VARCHAR, check_name VARCHAR, table_name VARCHAR, severity VARCHAR, rows_affected_sql VARCHAR, handling VARCHAR);
INSERT INTO dq.check_catalog VALUES
('DQ01','Duplicate ticket_id','fact_maintenance_ticket','High','extra rows','De-duplicated in core (keep first row per ticket_id); otherwise ticket counts and costs are overstated'),
('DQ02','resolved_at before created_at','fact_maintenance_ticket','High','tickets','Ticket kept for counts, but excluded from duration/SLA metrics (flag ts_invalid); raise with portal owner'),
('DQ03','Unit area missing or zero','dim_unit','Medium','units','area set NULL in core; unit excluded from EUR/m2 metrics; master-data fix request'),
('DQ04','Rent-roll unit_id not in unit master','fact_rent_roll','High','unit ids','Lines quarantined (dq.quarantine_rent_roll), excluded from KPIs; typical of a not-yet-mapped migrated portfolio'),
('DQ05','Bank reference booked twice','fact_payment','High','bank refs','Duplicate payment rows removed in core (keep lowest payment_id); otherwise arrears understated'),
('DQ06','Statement issued before period end','fact_service_charge_statement','Medium','statements','issued_date treated as unknown (NULL) in core and excluded from timeliness KPI'),
('DQ07','Statement total <> sum of cost lines','fact_service_charge_statement','Medium','statements','Reconciliation check'),
('DQ08','Payment for unknown rent line','fact_payment','High','payments','Reconciliation check'),
('DQ09','total_due <> Kaltmiete + NK','fact_rent_roll','High','lines','Reconciliation check'),
('DQ10','Status/resolved_at inconsistent or in future','fact_maintenance_ticket','Medium','tickets','Consistency check'),
('DQ11','Overlapping tenancies on a unit','dim_tenant','High','units','Consistency check'),
('DQ12','Ticket for unknown property/unit','fact_maintenance_ticket','High','tickets','Referential-integrity check');

CREATE OR REPLACE TABLE dq.results AS
WITH k AS (SELECT check_id, COUNT(*) AS failed_keys FROM dq.failed_keys GROUP BY 1),
extra AS (  -- for duplicate checks, the number of surplus rows is more meaningful than the number of keys
  SELECT 'DQ01' AS check_id, (SELECT COUNT(*) - COUNT(DISTINCT ticket_id) FROM raw.fact_maintenance_ticket) AS n
  UNION ALL SELECT 'DQ04', (SELECT COUNT(*) FROM raw.fact_rent_roll WHERE unit_id NOT IN (SELECT unit_id FROM raw.dim_unit))
  UNION ALL SELECT 'DQ05', (SELECT COUNT(*) - COUNT(DISTINCT bank_ref) FROM raw.fact_payment))
SELECT c.check_id, c.check_name, c.table_name, c.severity,
       COALESCE(k.failed_keys, 0) AS failed_keys,
       COALESCE(e.n, k.failed_keys, 0) AS failed_rows,
       CASE WHEN COALESCE(k.failed_keys, 0) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
       c.handling
FROM dq.check_catalog c LEFT JOIN k USING (check_id) LEFT JOIN extra e USING (check_id)
ORDER BY c.check_id;

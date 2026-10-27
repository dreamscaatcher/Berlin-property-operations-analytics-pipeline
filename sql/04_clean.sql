-- =====================================================================
-- 04_clean.sql : CORE layer = cleaned star schema used by all KPIs
-- (and exported to powerbi/csv). Snapshot date of the sample: 2026-09-30.
-- =====================================================================
CREATE OR REPLACE TABLE core.dim_property AS SELECT * FROM raw.dim_property;
CREATE OR REPLACE TABLE core.dim_date     AS SELECT * FROM raw.dim_date;
CREATE OR REPLACE TABLE core.dim_contractor AS SELECT * FROM raw.dim_contractor;
CREATE OR REPLACE TABLE core.dim_priority AS SELECT * FROM raw.dim_priority;

CREATE OR REPLACE TABLE core.dim_unit AS
SELECT unit_id, property_id, unit_no, unit_type, floor, rooms,
       CASE WHEN area_m2 > 0 THEN area_m2 END AS area_m2,           -- DQ03
       (area_m2 IS NULL OR area_m2 <= 0)        AS dq_area_missing,
       has_balcony
FROM raw.dim_unit;

CREATE OR REPLACE TABLE core.dim_tenant AS SELECT * FROM raw.dim_tenant;

-- DQ04: quarantine orphan rent-roll lines
CREATE OR REPLACE TABLE dq.quarantine_rent_roll AS
SELECT r.* FROM raw.fact_rent_roll r WHERE r.unit_id NOT IN (SELECT unit_id FROM raw.dim_unit);
CREATE OR REPLACE TABLE core.fact_rent_roll AS
SELECT r.*, u.property_id
FROM raw.fact_rent_roll r JOIN raw.dim_unit u USING (unit_id);

-- DQ05: remove duplicated bank-statement imports
CREATE OR REPLACE TABLE core.fact_payment AS
SELECT * EXCLUDE (rn) FROM (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY bank_ref ORDER BY payment_id) AS rn FROM raw.fact_payment p)
WHERE rn = 1 AND rent_roll_id IN (SELECT rent_roll_id FROM core.fact_rent_roll);

-- DQ01 + DQ02: de-duplicate tickets, derive durations and SLA flags
CREATE OR REPLACE TABLE core.fact_maintenance_ticket AS
WITH d AS (
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY ticket_id ORDER BY created_at) AS rn FROM raw.fact_maintenance_ticket t)
SELECT d.* EXCLUDE (rn),
       CAST(created_at AS DATE)                                             AS created_date,
       CAST(date_trunc('month', created_at) AS DATE)                        AS created_month,
       (resolved_at IS NOT NULL AND resolved_at < created_at)                AS dq_ts_invalid,
       CASE WHEN assigned_at >= created_at THEN (epoch(assigned_at) - epoch(created_at)) / 3600.0 END AS response_hours,
       CASE WHEN resolved_at >= created_at THEN (epoch(resolved_at) - epoch(created_at)) / 3600.0 END AS resolution_hours,
       p.sla_response_hours, p.sla_resolution_hours,
       CASE WHEN assigned_at >= created_at THEN (epoch(assigned_at) - epoch(created_at)) / 3600.0 <= p.sla_response_hours END AS met_response_sla,
       CASE WHEN resolved_at >= created_at THEN (epoch(resolved_at) - epoch(created_at)) / 3600.0 <= p.sla_resolution_hours END AS met_resolution_sla,
       status IN ('Neu', 'In Bearbeitung', 'Wartet auf Material/Freigabe')  AS is_open,
       CASE WHEN status IN ('Neu', 'In Bearbeitung', 'Wartet auf Material/Freigabe')
            THEN date_diff('day', CAST(created_at AS DATE), DATE '2026-09-30') END AS age_days_at_snapshot,
       CASE WHEN status IN ('Neu', 'In Bearbeitung', 'Wartet auf Material/Freigabe')
            THEN (epoch(TIMESTAMP '2026-09-30 23:59:59') - epoch(created_at)) / 3600.0 > p.sla_resolution_hours END AS is_overdue_at_snapshot
FROM d JOIN raw.dim_priority p USING (priority)
WHERE rn = 1;

CREATE OR REPLACE TABLE core.fact_vacancy_reletting AS
SELECT v.*,
       COALESCE(v.days_vacant, date_diff('day', v.move_out_date, DATE '2026-09-30')) AS days_vacant_to_date,
       v.relet_date IS NULL AS still_vacant,
       CASE WHEN v.new_rent_m2 IS NOT NULL THEN v.new_rent_m2 / v.old_rent_m2 - 1 END AS rent_uplift_pct
FROM raw.fact_vacancy_reletting v;

-- DQ06: issued_date inside the billing period is impossible -> unknown
CREATE OR REPLACE TABLE core.fact_service_charge_statement AS
WITH s AS (
  SELECT s.* EXCLUDE (issued_date),
         CASE WHEN s.issued_date > s.period_end THEN s.issued_date END AS issued_date,
         (s.issued_date <= s.period_end) AS dq_issued_date_invalid,
         p.property_type_code IN ('ALT', 'NEU', 'WEG') AS residential_556_bgb,
         CASE WHEN u.area_m2 > 0 THEN u.area_m2 END AS area_m2
  FROM raw.fact_service_charge_statement s JOIN raw.dim_property p USING (property_id)
  LEFT JOIN raw.dim_unit u USING (unit_id))
SELECT s.*,
       CASE WHEN dq_issued_date_invalid THEN 'Unbekannt (DQ)'
            WHEN issued_date IS NULL AND DATE '2026-09-30' > legal_deadline THEN 'Überfällig'
            WHEN issued_date IS NULL THEN 'Offen (Frist läuft)'
            WHEN issued_date <= legal_deadline THEN 'Fristgerecht'
            ELSE 'Verspätet' END AS timeliness,
       date_diff('day', period_end, issued_date) AS days_to_issue,
       -- §556 Abs. 3 S. 3 BGB: late statement -> back-payment claim excluded (residential leases)
       CASE WHEN issued_date > legal_deadline AND balance_eur > 0 AND residential_556_bgb THEN balance_eur ELSE 0 END AS forfeited_backpayment_eur
FROM s;

CREATE OR REPLACE TABLE core.fact_service_charge_cost AS SELECT * FROM raw.fact_service_charge_cost;
CREATE OR REPLACE TABLE core.fact_energy_monthly AS SELECT * FROM raw.fact_energy_monthly;

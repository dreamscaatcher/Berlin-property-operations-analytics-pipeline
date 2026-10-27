-- =====================================================================
-- 05_marts.sql : analytical marts (monthly grain, per property) that feed
-- the browser dashboard and can be imported into Power BI as helper tables.
-- =====================================================================

-- Month spine for the reporting window
CREATE OR REPLACE TABLE mart.month_spine AS
SELECT DISTINCT month_start, last_day(month_start) AS month_end
FROM core.dim_date WHERE month_start BETWEEN DATE '2024-01-01' AND DATE '2026-09-01';

-- ---------------------------------------------------------------------
-- Rent, collection and arrears (Mietrückstände) per property x month-end.
-- open_arrears_eom = sum over all rent lines due on/before month-end of
--   (total_due - payments booked on/before month-end), floored at 0.
-- Ageing = days between due_date and the month-end.
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.rent_arrears_monthly AS
WITH grid AS (
  SELECT r.rent_roll_id, r.property_id, r.period_month, r.due_date, r.total_due, m.month_start AS as_of_month, m.month_end AS as_of
  FROM core.fact_rent_roll r JOIN mart.month_spine m ON r.due_date <= m.month_end),
paid AS (
  SELECT g.rent_roll_id, g.as_of, COALESCE(SUM(p.amount), 0) AS paid
  FROM grid g LEFT JOIN core.fact_payment p ON p.rent_roll_id = g.rent_roll_id AND p.payment_date <= g.as_of
  GROUP BY 1, 2),
items AS (
  SELECT g.property_id, g.as_of_month, GREATEST(g.total_due - p.paid, 0) AS open_amt,
         date_diff('day', g.due_date, g.as_of) AS age_days
  FROM grid g JOIN paid p USING (rent_roll_id, as_of)
  -- assumption: items older than 365 days are handed to collection / written off and leave the open-items list
  WHERE date_diff('day', g.due_date, g.as_of) <= 365),
arrears AS (
  SELECT property_id, as_of_month AS month_start,
         SUM(open_amt) AS open_arrears_eom,
         SUM(CASE WHEN age_days <= 30 THEN open_amt ELSE 0 END)              AS arrears_0_30,
         SUM(CASE WHEN age_days BETWEEN 31 AND 60 THEN open_amt ELSE 0 END)  AS arrears_31_60,
         SUM(CASE WHEN age_days BETWEEN 61 AND 90 THEN open_amt ELSE 0 END)  AS arrears_61_90,
         SUM(CASE WHEN age_days > 90 THEN open_amt ELSE 0 END)               AS arrears_90_plus
  FROM items GROUP BY 1, 2),
soll AS (
  SELECT r.property_id, r.period_month AS month_start,
         SUM(r.kaltmiete_due) AS kaltmiete_due, SUM(r.nk_prepayment_due) AS nk_prepayment_due, SUM(r.total_due) AS total_due,
         COUNT(*) AS rent_lines
  FROM core.fact_rent_roll r WHERE r.period_month >= DATE '2024-01-01' GROUP BY 1, 2),
coll AS (
  SELECT r.property_id, r.period_month AS month_start,
         SUM(CASE WHEN p.payment_date <= r.due_date THEN p.amount ELSE 0 END)                 AS paid_by_due_date,
         SUM(CASE WHEN p.payment_date <= last_day(r.period_month) THEN p.amount ELSE 0 END)   AS paid_in_month,
         SUM(p.amount)                                                                        AS paid_to_snapshot
  FROM core.fact_rent_roll r JOIN core.fact_payment p USING (rent_roll_id)
  WHERE r.period_month >= DATE '2024-01-01' GROUP BY 1, 2)
SELECT s.property_id, s.month_start, s.rent_lines, s.kaltmiete_due, s.nk_prepayment_due, s.total_due,
       COALESCE(c.paid_by_due_date, 0) AS paid_by_due_date, COALESCE(c.paid_in_month, 0) AS paid_in_month,
       COALESCE(c.paid_to_snapshot, 0) AS paid_to_snapshot,
       a.open_arrears_eom, a.arrears_0_30, a.arrears_31_60, a.arrears_61_90, a.arrears_90_plus
FROM soll s LEFT JOIN coll c USING (property_id, month_start) LEFT JOIN arrears a USING (property_id, month_start);

-- ---------------------------------------------------------------------
-- Occupancy / vacancy (Leerstand) per property x month in unit-days.
-- Vacant interval = [move_out_date + 1, relet_date - 1] (open-ended -> snapshot).
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.occupancy_monthly AS
WITH units AS (SELECT property_id, COUNT(*) AS units FROM core.dim_unit GROUP BY 1),
vac AS (
  SELECT v.property_id, m.month_start,
         SUM(GREATEST(0, date_diff('day',
               GREATEST(v.move_out_date + 1, m.month_start),
               LEAST(COALESCE(v.relet_date - 1, DATE '2026-09-30'), m.month_end)) + 1)) AS vacant_unit_days
  FROM core.fact_vacancy_reletting v JOIN mart.month_spine m
    ON v.move_out_date + 1 <= m.month_end AND COALESCE(v.relet_date - 1, DATE '2026-09-30') >= m.month_start
  GROUP BY 1, 2)
SELECT u.property_id, m.month_start, u.units,
       u.units * (date_diff('day', m.month_start, m.month_end) + 1) AS unit_days,
       COALESCE(v.vacant_unit_days, 0) AS vacant_unit_days
FROM units u CROSS JOIN mart.month_spine m LEFT JOIN vac v USING (property_id, month_start);

-- ---------------------------------------------------------------------
-- Maintenance backlog at snapshot (open tickets by age)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.maintenance_backlog_snapshot AS
SELECT t.ticket_id, t.property_id, t.category, t.priority, t.status, t.contractor_id, t.created_at,
       date_diff('day', CAST(t.created_at AS DATE), DATE '2026-09-30') AS age_days,
       (epoch(TIMESTAMP '2026-09-30 23:59:59') - epoch(t.created_at)) / 3600.0 > t.sla_resolution_hours AS is_overdue,
       CASE WHEN date_diff('day', CAST(t.created_at AS DATE), DATE '2026-09-30') <= 7 THEN '0-7 Tage'
            WHEN date_diff('day', CAST(t.created_at AS DATE), DATE '2026-09-30') <= 30 THEN '8-30 Tage'
            WHEN date_diff('day', CAST(t.created_at AS DATE), DATE '2026-09-30') <= 90 THEN '31-90 Tage'
            ELSE '90+ Tage' END AS age_bucket
FROM core.fact_maintenance_ticket t WHERE t.is_open;

-- ---------------------------------------------------------------------
-- Portfolio KPI summary at snapshot (last 12 months = Oct 2025 - Sep 2026)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW mart.portfolio_kpi AS
WITH r AS (SELECT * FROM mart.rent_arrears_monthly),
o AS (SELECT * FROM mart.occupancy_monthly),
t12 AS (SELECT * FROM core.fact_maintenance_ticket WHERE created_month >= DATE '2025-10-01')
SELECT
  (SELECT COUNT(*) FROM core.dim_property)                                                      AS properties,
  (SELECT COUNT(*) FROM core.dim_unit)                                                          AS units,
  (SELECT ROUND(SUM(area_m2)) FROM core.dim_unit)                                               AS area_m2,
  (SELECT SUM(total_due) FROM r WHERE month_start = DATE '2026-09-01')                          AS soll_sep_2026_eur,
  (SELECT SUM(open_arrears_eom) FROM r WHERE month_start = DATE '2026-09-01')                   AS open_arrears_eur,
  (SELECT SUM(open_arrears_eom) / SUM(total_due) FROM r WHERE month_start = DATE '2026-09-01')  AS arrears_rate_of_monthly_soll,
  (SELECT SUM(paid_in_month) / SUM(total_due) FROM r WHERE month_start >= DATE '2025-10-01')    AS collection_rate_in_month_12m,
  (SELECT SUM(vacant_unit_days) / SUM(unit_days) FROM o WHERE month_start = DATE '2026-09-01')  AS vacancy_rate_sep_2026,
  (SELECT AVG(days_vacant) FROM core.fact_vacancy_reletting WHERE relet_date >= DATE '2025-10-01') AS avg_days_to_relet_12m,
  (SELECT MEDIAN(rent_uplift_pct) FROM core.fact_vacancy_reletting WHERE relet_date >= DATE '2025-10-01') AS median_relet_uplift_12m,
  (SELECT COUNT(*) FROM t12)                                                                    AS tickets_12m,
  (SELECT AVG(CAST(met_resolution_sla AS INT)) FROM t12 WHERE met_resolution_sla IS NOT NULL)  AS resolution_sla_rate_12m,
  (SELECT COUNT(*) FROM mart.maintenance_backlog_snapshot)                                     AS open_tickets,
  (SELECT COUNT(*) FROM mart.maintenance_backlog_snapshot WHERE is_overdue)                    AS open_tickets_overdue,
  (SELECT SUM(cost_eur) FROM t12) / (SELECT COUNT(*) FROM core.dim_unit)                        AS maintenance_cost_per_unit_12m,
  (SELECT AVG(CASE WHEN timeliness = 'Fristgerecht' THEN 1 ELSE 0 END) FROM core.fact_service_charge_statement
     WHERE period_year = 2024 AND timeliness IN ('Fristgerecht', 'Verspätet'))                   AS sc_2024_on_time_rate,
  (SELECT SUM(forfeited_backpayment_eur) FROM core.fact_service_charge_statement)              AS sc_forfeited_backpayments_eur;

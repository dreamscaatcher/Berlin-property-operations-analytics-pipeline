-- =====================================================================
-- 06_business_questions.sql : the questions this project answers.
-- Each query is self-contained and runs against the CORE / MART layer.
-- Snapshot date of the sample: 2026-09-30.  "-- Q" markers are parsed by
-- scripts/export.py to write sql/results/*.md.
-- =====================================================================

-- Q01 Portfolio KPI summary at snapshot
SELECT * FROM mart.portfolio_kpi;

-- Q02 Arrears rate (open arrears at month-end / monthly Soll) by property type, quarterly
SELECT p.property_type, CAST(date_trunc('quarter', r.month_start) AS DATE) AS quarter,
       ROUND(SUM(r.open_arrears_eom) FILTER (WHERE month(r.month_start) % 3 = 0)
             / SUM(r.total_due) FILTER (WHERE month(r.month_start) % 3 = 0), 3) AS arrears_rate_q_end,
       ROUND(SUM(r.paid_in_month) / SUM(r.total_due), 3) AS collection_rate_in_month
FROM mart.rent_arrears_monthly r JOIN core.dim_property p USING (property_id)
GROUP BY ALL ORDER BY 1, 2;

-- Q03 Arrears ageing at snapshot by district (EUR)
SELECT p.city, p.district,
       ROUND(SUM(arrears_0_30)) AS "0-30", ROUND(SUM(arrears_31_60)) AS "31-60",
       ROUND(SUM(arrears_61_90)) AS "61-90", ROUND(SUM(arrears_90_plus)) AS "90+",
       ROUND(SUM(open_arrears_eom)) AS total_open, ROUND(SUM(open_arrears_eom) / SUM(total_due), 3) AS arrears_rate
FROM mart.rent_arrears_monthly r JOIN core.dim_property p USING (property_id)
WHERE r.month_start = DATE '2026-09-01'
GROUP BY ALL ORDER BY total_open DESC;

-- Q04 Top 10 properties by open arrears at snapshot
SELECT p.property_id, p.property_name, p.district, p.property_type,
       ROUND(r.open_arrears_eom) AS open_arrears, ROUND(r.open_arrears_eom / r.total_due, 3) AS arrears_rate,
       ROUND(r.arrears_90_plus) AS over_90_days
FROM mart.rent_arrears_monthly r JOIN core.dim_property p USING (property_id)
WHERE r.month_start = DATE '2026-09-01' ORDER BY open_arrears DESC LIMIT 10;

-- Q05 Maintenance SLA compliance by priority (all resolved tickets with valid timestamps)
SELECT priority, COUNT(*) AS tickets,
       ROUND(MEDIAN(response_hours), 1) AS median_response_h, ROUND(AVG(CAST(met_response_sla AS INT)), 3) AS response_sla_rate,
       ROUND(MEDIAN(resolution_hours), 1) AS median_resolution_h, ROUND(AVG(CAST(met_resolution_sla AS INT)), 3) AS resolution_sla_rate
FROM core.fact_maintenance_ticket WHERE status = 'Erledigt' AND NOT dq_ts_invalid
GROUP BY 1 ORDER BY 1;

-- Q06 Contractor scorecard, last 12 months (which contractor is slipping?)
SELECT c.contractor_id, c.contractor_name, COUNT(*) AS tickets,
       ROUND(MEDIAN(t.resolution_hours), 1) AS median_resolution_h,
       ROUND(AVG(CAST(t.met_resolution_sla AS INT)), 3) AS resolution_sla_rate,
       ROUND(AVG(t.cost_eur), 0) AS avg_cost_eur
FROM core.fact_maintenance_ticket t JOIN core.dim_contractor c USING (contractor_id)
WHERE t.created_month >= DATE '2025-10-01' AND t.status = 'Erledigt' AND NOT t.dq_ts_invalid
GROUP BY ALL ORDER BY resolution_sla_rate;

-- Q07 Contractor C03 trend by quarter vs other HLS contractors
SELECT CAST(date_trunc('quarter', created_at) AS DATE) AS quarter,
       ROUND(AVG(CAST(met_resolution_sla AS INT)) FILTER (WHERE contractor_id = 'C03'), 3) AS c03_sla_rate,
       ROUND(AVG(CAST(met_resolution_sla AS INT)) FILTER (WHERE contractor_id IN ('C01','C02','C04')), 3) AS other_hls_sla_rate
FROM core.fact_maintenance_ticket WHERE status = 'Erledigt' AND NOT dq_ts_invalid
GROUP BY 1 ORDER BY 1;

-- Q08 Heating tickets seasonality (tickets per 100 units per month)
SELECT month(created_at) AS month, ROUND(COUNT(*) FILTER (WHERE category = 'Heizung') * 100.0
       / (SELECT COUNT(*) FROM core.dim_unit) / COUNT(DISTINCT created_month), 2) AS heating_tickets_per_100_units
FROM core.fact_maintenance_ticket GROUP BY 1 ORDER BY 1;

-- Q09 Open backlog at snapshot by priority and age bucket
SELECT priority, age_bucket, COUNT(*) AS open_tickets, COUNT(*) FILTER (WHERE is_overdue) AS overdue
FROM mart.maintenance_backlog_snapshot GROUP BY ALL ORDER BY 1, 2;

-- Q10 Maintenance cost per unit per year by property type (2026 = Jan-Sep only)
SELECT p.property_type, year(t.created_at) AS year,
       ROUND(SUM(t.cost_eur) / MAX(u.units), 0) AS cost_per_unit_eur, COUNT(*) AS tickets
FROM core.fact_maintenance_ticket t JOIN core.dim_property p USING (property_id)
JOIN (SELECT p2.property_type, COUNT(*) AS units FROM core.dim_unit u2 JOIN core.dim_property p2 USING (property_id) GROUP BY 1) u USING (property_type)
GROUP BY ALL ORDER BY 1, 2;

-- Q11 Vacancy rate (unit-days) and re-letting KPIs by property type
WITH occ AS (SELECT p.property_type, SUM(vacant_unit_days) / SUM(unit_days) AS vacancy_rate
             FROM mart.occupancy_monthly o JOIN core.dim_property p USING (property_id)
             WHERE o.month_start >= DATE '2025-10-01' GROUP BY 1),
rl AS (SELECT p.property_type, COUNT(*) AS relets, AVG(days_vacant) AS avg_days_to_relet, MEDIAN(days_vacant) AS median_days,
              MEDIAN(rent_uplift_pct) AS median_uplift, AVG(CAST(renovation_before_relet AS INT)) AS share_renovated
       FROM core.fact_vacancy_reletting v JOIN core.dim_property p USING (property_id)
       WHERE v.relet_date IS NOT NULL GROUP BY 1)
SELECT property_type, ROUND(vacancy_rate, 4) AS vacancy_rate_12m, relets, ROUND(avg_days_to_relet, 1) AS avg_days_to_relet,
       median_days, ROUND(median_uplift, 3) AS median_rent_uplift, ROUND(share_renovated, 2) AS share_renovated
FROM occ JOIN rl USING (property_type) ORDER BY 1;

-- Q12 Service-charge statement timeliness by billing year (§556 Abs. 3 BGB deadline)
SELECT period_year, timeliness, COUNT(*) AS statements, ROUND(AVG(days_to_issue)) AS avg_days_to_issue,
       ROUND(SUM(forfeited_backpayment_eur)) AS forfeited_backpayments_eur
FROM core.fact_service_charge_statement GROUP BY ALL ORDER BY 1, 2;

-- Q13 Properties that issued statements late (with forfeited back-payments)
SELECT s.period_year, p.property_id, p.property_name, p.property_type, COUNT(*) AS late_statements,
       ROUND(SUM(s.forfeited_backpayment_eur)) AS forfeited_eur, MIN(s.issued_date) AS first_issued
FROM core.fact_service_charge_statement s JOIN core.dim_property p USING (property_id)
WHERE s.timeliness = 'Verspätet' GROUP BY ALL HAVING COUNT(*) > 5 ORDER BY forfeited_eur DESC;

-- Q14 Back-payment / refund distribution (statements issued)
SELECT period_year,
       CASE WHEN balance_eur < -300 THEN '1: Guthaben > 300'
            WHEN balance_eur < -100 THEN '2: Guthaben 100-300'
            WHEN balance_eur < 0 THEN '3: Guthaben 0-100'
            WHEN balance_eur < 100 THEN '4: Nachzahlung 0-100'
            WHEN balance_eur < 300 THEN '5: Nachzahlung 100-300'
            ELSE '6: Nachzahlung > 300' END AS balance_band,
       COUNT(*) AS statements
FROM core.fact_service_charge_statement WHERE issued_date IS NOT NULL GROUP BY ALL ORDER BY 1, 2;

-- Q15 Actual service-charge cost per m2 and month by cost type and year (residential)
SELECT l.cost_type, s.period_year,
       ROUND(SUM(l.actual_cost) / SUM(u.area_m2 * s.months_billed), 3) AS eur_per_m2_month
FROM core.fact_service_charge_cost l JOIN core.fact_service_charge_statement s USING (statement_id)
JOIN core.dim_unit u USING (unit_id)
WHERE s.residential_556_bgb AND u.area_m2 IS NOT NULL
GROUP BY ALL ORDER BY 1, 2;

-- Q16 Heating energy intensity (kWh/m2, last 12 months) by property type
SELECT p.property_type, ROUND(SUM(e.heating_kwh) / SUM(a.area_m2) * 1.0, 1) AS heating_kwh_per_m2_12m
FROM core.fact_energy_monthly e JOIN core.dim_property p USING (property_id)
JOIN (SELECT property_id, SUM(area_m2) / 12.0 AS area_m2 FROM core.dim_unit GROUP BY 1) a USING (property_id)
WHERE e.period_month >= DATE '2025-10-01'
GROUP BY 1 ORDER BY 2 DESC;

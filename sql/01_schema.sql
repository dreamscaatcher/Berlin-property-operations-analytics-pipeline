-- =====================================================================
-- Berlin Property Operations Analytics  (SYNTHETIC DATA)
-- 01_schema.sql : DDL for the RAW layer (DuckDB)
-- Raw tables mirror the source extracts 1:1 and deliberately carry NO
-- primary/foreign-key constraints, so that bad source rows can be loaded,
-- detected (03_dq_checks.sql) and handled in the CORE layer (04_clean.sql).
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS dq;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE OR REPLACE TABLE raw.dim_property (
    property_id        VARCHAR,   -- P001..
    property_name      VARCHAR,   -- fictitious name
    city               VARCHAR,
    district           VARCHAR,   -- Berlin Bezirk or city
    property_type      VARCHAR,   -- Altbau residential | Neubau residential | WEG condominium | Commercial/retail | Office
    property_type_code VARCHAR,   -- ALT | NEU | WEG | RET | OFF
    year_built         INTEGER,
    has_lift           BOOLEAN,
    has_garden         BOOLEAN,
    heating_source     VARCHAR,   -- Fernwärme | Erdgas | Wärmepumpe
    management_since   DATE,
    is_synthetic       BOOLEAN
);
CREATE OR REPLACE TABLE raw.dim_unit (
    unit_id      VARCHAR, property_id VARCHAR, unit_no VARCHAR,
    unit_type    VARCHAR,          -- Wohnung | Laden/Gewerbe | Büro
    floor        INTEGER, rooms INTEGER,
    area_m2      DOUBLE,           -- Wohn-/Nutzfläche
    has_balcony  BOOLEAN
);
CREATE OR REPLACE TABLE raw.dim_tenant (
    tenant_id VARCHAR, tenant_label VARCHAR,   -- pseudonymous, no personal data
    unit_id VARCHAR, tenant_type VARCHAR,      -- Privat | Gewerbe
    lease_start DATE, lease_end DATE, payment_method VARCHAR
);
CREATE OR REPLACE TABLE raw.dim_date (
    date DATE, year INTEGER, quarter INTEGER, month INTEGER, month_start DATE, year_month VARCHAR,
    month_name_de VARCHAR, month_name_en VARCHAR, iso_week INTEGER, weekday INTEGER,
    is_weekend BOOLEAN, is_heating_season BOOLEAN, is_month_end BOOLEAN
);
CREATE OR REPLACE TABLE raw.dim_contractor (contractor_id VARCHAR, contractor_name VARCHAR, trade VARCHAR, is_synthetic BOOLEAN);
CREATE OR REPLACE TABLE raw.dim_priority (priority VARCHAR, sla_response_hours INTEGER, sla_resolution_hours INTEGER);

-- Sollstellung: one line per unit, tenant and month
CREATE OR REPLACE TABLE raw.fact_rent_roll (
    rent_roll_id BIGINT, period_month DATE, due_date DATE, unit_id VARCHAR, tenant_id VARCHAR,
    kaltmiete_due DECIMAL(12,2),        -- net cold rent
    nk_prepayment_due DECIMAL(12,2),    -- Nebenkostenvorauszahlung
    total_due DECIMAL(12,2)             -- Warmmiete due
);
CREATE OR REPLACE TABLE raw.fact_payment (
    payment_id VARCHAR, rent_roll_id BIGINT, payment_date DATE, amount DECIMAL(12,2),
    payment_method VARCHAR, bank_ref VARCHAR
);
CREATE OR REPLACE TABLE raw.fact_maintenance_ticket (
    ticket_id VARCHAR, property_id VARCHAR, unit_id VARCHAR, is_common_area BOOLEAN,
    category VARCHAR, priority VARCHAR, channel VARCHAR, contractor_id VARCHAR,
    created_at TIMESTAMP, assigned_at TIMESTAMP, resolved_at TIMESTAMP,
    status VARCHAR, cost_eur DECIMAL(12,2)
);
CREATE OR REPLACE TABLE raw.fact_vacancy_reletting (
    vacancy_id VARCHAR, unit_id VARCHAR, property_id VARCHAR, old_tenant_id VARCHAR, new_tenant_id VARCHAR,
    move_out_date DATE, relet_date DATE, days_vacant INTEGER,
    old_rent_m2 DECIMAL(8,2), new_rent_m2 DECIMAL(8,2),
    renovation_before_relet BOOLEAN, marketing_channel VARCHAR, applications_received INTEGER
);
-- Nebenkostenabrechnung header (one per unit, tenant and billing year)
CREATE OR REPLACE TABLE raw.fact_service_charge_statement (
    statement_id VARCHAR, unit_id VARCHAR, tenant_id VARCHAR, property_id VARCHAR,
    period_year INTEGER, period_start DATE, period_end DATE, months_billed INTEGER,
    prepayments_total DECIMAL(12,2), actual_costs_total DECIMAL(12,2),
    balance_eur DECIMAL(12,2),          -- >0 Nachzahlung (tenant owes), <0 Guthaben (refund)
    legal_deadline DATE,                -- period_end + 12 months (§556 Abs. 3 BGB)
    issued_date DATE, status VARCHAR
);
CREATE OR REPLACE TABLE raw.fact_service_charge_cost (
    statement_id VARCHAR, cost_type VARCHAR, allocation_key VARCHAR, actual_cost DECIMAL(12,2)
);
CREATE OR REPLACE TABLE raw.fact_energy_monthly (
    property_id VARCHAR, period_month DATE, heating_kwh BIGINT, common_electricity_kwh BIGINT
);

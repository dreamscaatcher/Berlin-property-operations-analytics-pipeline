# Berlin Property Operations Analytics: data pipeline (SYNTHETIC data)

> **All data in this project is synthetic.** A seeded Python script (`seed = 20261017`) makes it up.
> None of it is real data from Optima, Emeria or any other company. There are no real tenants,
> properties or contractors.

## 1. What this is and why

This project is a practice portfolio for a large Berlin property manager: 680 properties, 33,000 units
and 40,856 tenancies, with a snapshot date of **30 Sep 2026**. It covers the work a property-operations
analyst does every month: rent roll and arrears (*Sollstellung / Mietrückstände*), maintenance tickets
and SLAs, vacancy and re-letting, and service-charge statements (*Nebenkostenabrechnung*, §556 BGB).
The raw data has **deliberately planted errors** such as duplicates, impossible timestamps and missing
master data. That gives the pipeline real work to do, which is the point: **find and fix data problems
before any KPI is calculated**. Otherwise the Power BI report would show wrong numbers. The
Power BI report (`property.pbix`, stored next to this folder in the GitHub repo) reads only the cleaned
and aggregated layers.

## 2. The layers

```
 generate_data_33k.py            sql/01_schema.sql + 02_load.sql
 (fixed seed)                          │
 data/raw/*.csv  ───────────────►  RAW  (schema raw)    13 tables, loaded 1:1, no keys / no constraints
                                       │
                                       ▼  sql/03_dq_checks.sql
                                   DQ   (schema dq)     12 checks -> dq.results (PASS/FAIL), dq.failed_keys
                                       │
                                       ▼  sql/04_clean.sql
                                   CORE (schema core)   cleaned star schema = "staging + cleaned dims & facts"
                                       │                6 dims + 7 facts; bad rows removed, quarantined or flagged
                                       ▼  sql/05_marts.sql
                                   MART (schema mart)   pre-aggregated, monthly grain per property
                                       │                rent_arrears_monthly, occupancy_monthly, backlog, KPI view
                                       ▼  scripts/export.py + scripts/build_xlsx.py
                     powerbi/csv/*.csv  +  powerbi/Berlin_Property_Ops_33k.xlsx  ──►  Power BI Desktop (property.pbix)
```

| Layer | What it does | Plain-words analogy |
|---|---|---|
| **raw** | Exact copy of the source extracts. All columns, all rows, **including the bad ones**. No primary keys, so nothing is rejected on load. | The unopened delivery box |
| **dq** | Runs 12 rule checks on raw and records how many rows break each rule. It also keeps a **quarantine** table for rows that cannot be used. | The inspection report |
| **core** | Cleaned tables in a star schema. Duplicates are removed, orphans are excluded, impossible values become NULL, `dq_*` flag columns are added, and derived columns (SLA hours, timeliness, ...) are calculated. In dbt language this is *staging + cleaned dims/facts*. | Sorted, labelled stock on the shelf |
| **mart** | Business-ready aggregates at month x property grain. The arrears logic is the hard part, so it lives here once and not in DAX. | The ready-to-serve dish |
| **Power BI** | Imports core dims and facts plus the marts. Relationships, DAX measures and report pages are built in Power BI Desktop. | The menu |

Run order: `generate_data_33k.py` -> `build_db.py` (runs sql 01-05) -> `export.py` (sql 06 business
questions, `qa/dq_report.md`, `powerbi/csv`) -> `build_xlsx.py` (the workbook Power BI imports).

## 3. The 12 data-quality checks (`sql/03_dq_checks.sql`, table `dq.check_catalog`)

Result of the build from this folder (also in `qa/dq_report.md`): **6 FAIL, 6 PASS**. The 6 failures are
planted on purpose. `qa/dq_report.md` reconciles them against the generator's injection log
(`data/raw/_dq_injection_log.json`): every planted error was found, and nothing extra was flagged.

| ID | Check (rule) | Table | Severity | Result (keys / rows) | How it is handled (`sql/04_clean.sql`) |
|---|---|---|---|---|---|
| DQ01 | Duplicate `ticket_id` | fact_maintenance_ticket | High | **FAIL** 408 / 408 | De-duplicated in core (keep first row per ticket_id); otherwise ticket counts and costs are overstated |
| DQ02 | `resolved_at` before `created_at` | fact_maintenance_ticket | High | **FAIL** 190 / 190 | Ticket kept for counts, but excluded from duration/SLA metrics (flag `dq_ts_invalid`) |
| DQ03 | Unit area missing or zero | dim_unit | Medium | **FAIL** 95 / 95 | `area_m2` set NULL in core (flag `dq_area_missing`); unit excluded from EUR/m² metrics |
| DQ04 | Rent-roll `unit_id` not in unit master | fact_rent_roll | High | **FAIL** 27 / 324 | Lines quarantined in `dq.quarantine_rent_roll`, excluded from KPIs (typical of a not-yet-mapped migrated portfolio) |
| DQ05 | Bank reference booked twice | fact_payment | High | **FAIL** 163 / 163 | Duplicate payment rows removed in core (keep lowest payment_id); otherwise arrears are understated |
| DQ06 | Statement issued before billing period ended | fact_service_charge_statement | Medium | **FAIL** 68 / 68 | `issued_date` set to NULL (unknown) in core; timeliness = "Unbekannt (DQ)" (flag `dq_issued_date_invalid`) |
| DQ07 | Statement header total <> sum of cost lines (±1 EUR) | fact_service_charge_statement | Medium | PASS 0 | Reconciliation check |
| DQ08 | Payment for unknown rent line | fact_payment | High | PASS 0 | Reconciliation check |
| DQ09 | `total_due` <> Kaltmiete + NK prepayment | fact_rent_roll | High | PASS 0 | Reconciliation check |
| DQ10 | Status "Erledigt" without `resolved_at`, or `resolved_at` after snapshot | fact_maintenance_ticket | Medium | PASS 0 | Consistency check |
| DQ11 | Overlapping tenancies on the same unit | dim_tenant | High | PASS 0 | Consistency check |
| DQ12 | Ticket for unknown property / unit | fact_maintenance_ticket | High | PASS 0 | Referential-integrity check |

*keys* = distinct failing IDs. *rows* = affected rows. For DQ04, 27 unknown unit IDs carry 324 rent lines.

## 4. One worked example per layer (real SQL, real counts from this build)

### RAW: load everything, reject nothing (`sql/01_schema.sql`, `sql/02_load.sql`)
```sql
CREATE OR REPLACE TABLE raw.fact_payment (payment_id VARCHAR, rent_roll_id BIGINT, payment_date DATE,
    amount DECIMAL(12,2), payment_method VARCHAR, bank_ref VARCHAR);   -- no PRIMARY KEY on purpose
COPY raw.fact_payment FROM 'data/raw/fact_payment.csv' (HEADER);
```
If `payment_id` or `bank_ref` were a primary key, the load would crash on the first duplicate and you
would never learn how many there are. Raw therefore accepts all **1,435,925** payment rows and
**1,428,704** rent-roll lines.

### DQ: detect and quarantine (DQ04 orphan rent lines)
```sql
-- 03_dq_checks.sql: rent-roll lines whose unit_id is not in the unit master
SELECT DISTINCT 'DQ04', r.unit_id FROM raw.fact_rent_roll r
LEFT JOIN raw.dim_unit u USING (unit_id) WHERE u.unit_id IS NULL;
-- 04_clean.sql: park them, keep only lines with a known unit
CREATE OR REPLACE TABLE dq.quarantine_rent_roll AS
SELECT r.* FROM raw.fact_rent_roll r WHERE r.unit_id NOT IN (SELECT unit_id FROM raw.dim_unit);
CREATE OR REPLACE TABLE core.fact_rent_roll AS
SELECT r.*, u.property_id FROM raw.fact_rent_roll r JOIN raw.dim_unit u USING (unit_id);
```
Result: 27 unknown units (`UMIG001` ... `UMIG027`, 12 monthly lines each, Oct 2025 – Sep 2026) give
**324 lines with EUR 283,092.00 of Soll quarantined**. Rent roll goes from **1,428,704 (raw) to
1,428,380 (core)**. The lines are not deleted. They wait in quarantine until master data maps the units.

### CORE: de-duplicate with `ROW_NUMBER()` (DQ05 double bank import)
```sql
CREATE OR REPLACE TABLE core.fact_payment AS
SELECT * EXCLUDE (rn) FROM (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY bank_ref ORDER BY payment_id) AS rn FROM raw.fact_payment p)
WHERE rn = 1 AND rent_roll_id IN (SELECT rent_roll_id FROM core.fact_rent_roll);
```
Example: bank reference `BR2026030020615` appears twice in raw (`PM0020615` and `PM1435910`, both
EUR 1,080.50 on 2026-03-02 for rent line 20531). `ROW_NUMBER()` numbers the copies 1 and 2 per
`bank_ref`, and only `rn = 1` (`PM0020615`) is kept. Payments go from **1,435,925 (raw) to 1,435,762
(core)**, which removes 163 duplicates worth **EUR 335,113.14**. Without this step that money would count as
paid twice and arrears would look smaller than they are. The same pattern (`PARTITION BY ticket_id`)
removes DQ01's 408 duplicate tickets: **150,149 to 149,741** tickets, EUR 196,649.68 of double-counted cost.

### MART: monthly arrears per property (`sql/05_marts.sql`, `mart.rent_arrears_monthly`)
For every month-end from Jan 2024 to Sep 2026, the mart takes every rent line already due. It subtracts
the payments booked by that month-end, floors the result at 0, puts it into ageing buckets, and ignores
items older than 365 days (assumed handed to collection):
```sql
grid  AS (SELECT r.rent_roll_id, r.property_id, r.due_date, r.total_due, m.month_start AS as_of_month, m.month_end AS as_of
          FROM core.fact_rent_roll r JOIN mart.month_spine m ON r.due_date <= m.month_end),
paid  AS (SELECT g.rent_roll_id, g.as_of, COALESCE(SUM(p.amount), 0) AS paid
          FROM grid g LEFT JOIN core.fact_payment p ON p.rent_roll_id = g.rent_roll_id AND p.payment_date <= g.as_of
          GROUP BY 1, 2),
items AS (SELECT g.property_id, g.as_of_month, GREATEST(g.total_due - p.paid, 0) AS open_amt,
                 date_diff('day', g.due_date, g.as_of) AS age_days
          FROM grid g JOIN paid p USING (rent_roll_id, as_of) WHERE date_diff('day', g.due_date, g.as_of) <= 365)
```
It condenses 1,428,380 rent lines and 1,435,762 payments into **22,440 rows** (680 properties x 33 months).
Sep 2026 across the portfolio:

| Soll (total_due) | paid in month | open arrears EOM | 0–30 days | 31–60 | 61–90 | 90+ |
|---|---|---|---|---|---|---|
| EUR 58,769,774.77 | EUR 56,263,287.76 | **EUR 10,701,059.16 (18.2% of Soll)** | 2,506,487.01 | 1,316,227.05 | 1,107,170.82 | 5,771,174.28 |

One row, for example: property `P001`, Sep 2026 has 94 rent lines, Soll EUR 106,410.87, paid in month
EUR 99,906.79 and open arrears EUR 12,278.02. Arrears are a *stock* (all unpaid items up to the month-end),
while Soll is the *flow* of one month. That is why the rate is "open arrears / monthly Soll".

## 5. How the Power BI tables map to the layers

`scripts/build_xlsx.py` writes `powerbi/Berlin_Property_Ops_33k.xlsx`. It has one Excel Table per sheet,
and this is the file `property.pbix` imports. (`powerbi/csv/` has the same core and mart tables as plain CSVs.)

| Power BI table | Layer / source | Role in the star schema |
|---|---|---|
| dim_property, dim_unit, dim_tenant, dim_date, dim_contractor, dim_priority | core | Dimensions (who / what / where / when) |
| fact_rent_roll (re-unioned in the model from sheets `fact_rent_roll_2024` 389,206 + `fact_rent_roll_2025_2026` 681,969 = 1,071,175 lines from Jan 2024; payments folded onto each line as `paid_by_due_date`, `paid_by_month_end`, `paid_to_snapshot`) | core.fact_rent_roll + core.fact_payment | Fact |
| fact_payment_monthly (91,382 rows: property x month x method) | core.fact_payment aggregated | Fact |
| fact_maintenance_ticket (149,741), fact_vacancy_reletting (8,239), fact_service_charge_statement (103,327), fact_service_charge_cost (946,258), fact_energy_monthly (22,440) | core | Facts |
| mart_rent_arrears_monthly (22,440), mart_occupancy_monthly (22,440) | mart | Pre-aggregated facts for arrears and vacancy |
| dq_results (12), dq_row_counts (5) | dq (via qa/dq_report.md) | Data Quality page. Not related to other tables |
| _Measures | helper | Holds the DAX measures |

The rent roll is split into two sheets because Excel stops at 1,048,576 rows per sheet. In Power BI Desktop
the relationships, DAX measures (`powerbi_kit/measures_reference.dax` is the reference kit, but the
measures saved in `property.pbix` are the source of truth), validation against the SQL numbers, and the
five report pages were built by hand. Example measure: `Arrears Rate % = DIVIDE([Open Arrears EOM], [Soll Last Month])`,
both for the last `month_start` in the mart. It returns 18.2%, which matches the SQL above.

Headline numbers to check the report against (from `scripts/row_counts.py`):
33,000 units · Soll Sep 2026 EUR 58,769,775 · open arrears EUR 10,701,059 (18.2%) · open tickets 2,951 ·
service-charge statements 103,327 · DQ 6 FAIL / 6 PASS.

## 6. How to run it on Windows

Prerequisite: Python 3.14 (64-bit) with the `py` launcher, which is the standard python.org / Microsoft Store install.
About 1 GB of free disk is needed for generated files. A full run takes a few minutes.

```powershell
cd C:\path\to\berlin-property-ops-pipeline
powershell -ExecutionPolicy Bypass -File .\run_all.ps1
```
The script creates `.venv`, installs `requirements.txt` (numpy 2.5.4, pandas 3.0.6, duckdb 1.5.6, openpyxl 3.1.5),
and runs the 4 steps. At the end it prints the row counts per layer and the headline numbers.
**Python 3.14 note:** all four pinned packages publish ready-made Windows wheels for Python 3.14
(`cp314-win_amd64`), so nothing needs compiling. If `pip install` still fails on your machine (for example a
32-bit or ARM Python, or a newer Python without wheels yet), install Python 3.12 and run
```powershell
Remove-Item -Recurse -Force .venv
powershell -ExecutionPolicy Bypass -File .\run_all.ps1 -PyVersion 3.12
```
Linux / macOS / Git Bash: `./run_all.sh`.

Generated files are listed in `.gitignore` and not committed: `data/raw/` (~260 MB; `fact_payment.csv` alone
is ~95 MB, close to GitHub's 100 MB limit), `db/`, `powerbi/csv/` and the 113 MB xlsx. Re-running the pipeline
recreates them: with the fixed seed and pinned packages you get the same rows and the same numbers. Only the row
*order* inside some exported CSVs can differ, because DuckDB writes in parallel. On Windows the generated raw CSVs also
get Windows line endings, so their file hashes differ from a Linux run even though the content is the same.
This was tested: a clean run of `run_all.ps1` on Windows with Python 3.14.3 took about 9 minutes and printed exactly the headline numbers above.

### Optional: the dbt version (`dbt_berlin/`)
`dbt_berlin/` is a small **teaching** project with dbt-core + dbt-duckdb. It shows the same raw → staging → marts idea the
"dbt way" for the maintenance-ticket slice: 4 staging views, 2 mart models + 1 aggregate, and 21 tests. **It does not
feed Power BI. The report uses the SQL pipeline above.** Its `load_raw.py` reads the cleaned `powerbi/csv`
files and *re-introduces* teaching mess on purpose (lowercase IDs, German date text, 25 duplicate rows,
3 test tickets). Staging then cleans that up: 149,769 raw rows become 149,741 in `stg_tickets`. One custom test
(`assert_ticket_resolved_after_created`) is **expected to fail with 190 rows**, which is DQ02 again. Read
`dbt_berlin/WALKTHROUGH.md`. Run it after the main pipeline:
`powershell -ExecutionPolicy Bypass -File .\dbt_berlin\run_all.ps1`.
The saved `dbt_berlin/outputs/` come from a run on Linux, with local folder paths shortened to `<repo>`.

## 7. How this was made (honest note)

This repo was built **with AI assistance (Grok Bot)**. The AI wrote the data generator, the SQL layers,
the scripts and this README. The author built the Power BI model in Power BI Desktop (data import,
relationships, DAX measures, validation against the SQL results, the report pages), and uses this project to learn the
raw → staging → marts approach. Do not read it as hand-written code. All numbers in this README come
from a fresh run of the pipeline in this folder on 26 Oct 2026.

## Folder contents

```
data_generation/generate_data_33k.py   synthetic data generator (seed 20261017)
sql/01_schema.sql .. 05_marts.sql       raw -> dq -> core -> mart
sql/06_business_questions.sql          16 business questions (results: sql/results/query_results.md)
scripts/build_db.py                    builds db/berlin_property_ops.duckdb (runs sql 01-05)
scripts/export.py                      sql 06 results, qa/dq_report.md, powerbi/csv
scripts/build_xlsx.py, validate_xlsx.py  Power BI workbook + its check
scripts/row_counts.py                  row counts per layer + headline numbers
qa/dq_report.md                        DQ results, before/after counts, injection-log reconciliation
powerbi_kit/                           report theme JSON + reference DAX measures
dbt_berlin/                            optional dbt teaching project
run_all.ps1 / run_all.sh               one-click rebuild
```

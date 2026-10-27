# QA / Data-quality report

*Synthetic sample. Generated 2026-10-26 by `scripts/export.py`; checks defined in `sql/03_dq_checks.sql`, handling in `sql/04_clean.sql`.*

## Check results (raw layer)

| check_id | check_name | table_name | severity | failed_keys | failed_rows | result | handling |
|---|---|---|---|---|---|---|---|
| DQ01 | Duplicate ticket_id | fact_maintenance_ticket | High | 408 | 408 | FAIL | De-duplicated in core (keep first row per ticket_id); otherwise ticket counts and costs are overstated |
| DQ02 | resolved_at before created_at | fact_maintenance_ticket | High | 190 | 190 | FAIL | Ticket kept for counts, but excluded from duration/SLA metrics (flag ts_invalid); raise with portal owner |
| DQ03 | Unit area missing or zero | dim_unit | Medium | 95 | 95 | FAIL | area set NULL in core; unit excluded from EUR/m2 metrics; master-data fix request |
| DQ04 | Rent-roll unit_id not in unit master | fact_rent_roll | High | 27 | 324 | FAIL | Lines quarantined (dq.quarantine_rent_roll), excluded from KPIs; typical of a not-yet-mapped migrated portfolio |
| DQ05 | Bank reference booked twice | fact_payment | High | 163 | 163 | FAIL | Duplicate payment rows removed in core (keep lowest payment_id); otherwise arrears understated |
| DQ06 | Statement issued before period end | fact_service_charge_statement | Medium | 68 | 68 | FAIL | issued_date treated as unknown (NULL) in core and excluded from timeliness KPI |
| DQ07 | Statement total <> sum of cost lines | fact_service_charge_statement | Medium | 0 | 0 | PASS | Reconciliation check |
| DQ08 | Payment for unknown rent line | fact_payment | High | 0 | 0 | PASS | Reconciliation check |
| DQ09 | total_due <> Kaltmiete + NK | fact_rent_roll | High | 0 | 0 | PASS | Reconciliation check |
| DQ10 | Status/resolved_at inconsistent or in future | fact_maintenance_ticket | Medium | 0 | 0 | PASS | Consistency check |
| DQ11 | Overlapping tenancies on a unit | dim_tenant | High | 0 | 0 | PASS | Consistency check |
| DQ12 | Ticket for unknown property/unit | fact_maintenance_ticket | High | 0 | 0 | PASS | Referential-integrity check |

## Rows before / after cleaning

| table | raw_rows | core_rows |
|---|---|---|
| fact_maintenance_ticket | 150149 | 149741 |
| fact_payment | 1435925 | 1435762 |
| fact_rent_roll | 1428704 | 1428380 |
| fact_service_charge_statement | 103327 | 103327 |
| dim_unit | 33000 | 33000 |

## Financial impact had the issues not been caught

* Duplicate bank-statement import: **EUR 335,113.14** of payments counted twice -> arrears understated by that amount.
* Orphan rent-roll lines (migrated units missing from unit master): **EUR 283,092.00** Soll quarantined.
* Duplicate ticket rows: **EUR 196,649.68** maintenance cost double-counted.

## Reconciliation against the injection log (proves the checks catch what was planted)

| check | injected keys | detected keys | all injected found | extra (natural) findings |
|---|---|---|---|---|
| DQ01 | 408 | 408 | yes | 0 |
| DQ02 | 190 | 190 | yes | 0 |
| DQ03 | 95 | 95 | yes | 0 |
| DQ04 | 27 | 27 | yes | 0 |
| DQ05 | 163 | 163 | yes | 0 |
| DQ06 | 68 | 68 | yes | 0 |

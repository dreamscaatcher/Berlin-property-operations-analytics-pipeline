-- 02_load.sql : load raw CSV extracts (run from the project root)
COPY raw.dim_property                  FROM 'data/raw/dim_property.csv'                  (HEADER);
COPY raw.dim_unit                      FROM 'data/raw/dim_unit.csv'                      (HEADER);
COPY raw.dim_tenant                    FROM 'data/raw/dim_tenant.csv'                    (HEADER);
COPY raw.dim_date                      FROM 'data/raw/dim_date.csv'                      (HEADER);
COPY raw.dim_contractor                FROM 'data/raw/dim_contractor.csv'                (HEADER);
COPY raw.dim_priority                  FROM 'data/raw/dim_priority.csv'                  (HEADER);
COPY raw.fact_rent_roll                FROM 'data/raw/fact_rent_roll.csv'                (HEADER);
COPY raw.fact_payment                  FROM 'data/raw/fact_payment.csv'                  (HEADER);
COPY raw.fact_maintenance_ticket       FROM 'data/raw/fact_maintenance_ticket.csv'       (HEADER);
COPY raw.fact_vacancy_reletting        FROM 'data/raw/fact_vacancy_reletting.csv'        (HEADER);
COPY raw.fact_service_charge_statement FROM 'data/raw/fact_service_charge_statement.csv' (HEADER);
COPY raw.fact_service_charge_cost      FROM 'data/raw/fact_service_charge_cost.csv'      (HEADER);
COPY raw.fact_energy_monthly           FROM 'data/raw/fact_energy_monthly.csv'           (HEADER);

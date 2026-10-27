#!/usr/bin/env python3
"""Print row counts per layer (raw / dq / core / mart) and the headline KPIs.
Run after build_db.py:  python scripts/row_counts.py"""
import os, duckdb
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
con = duckdb.connect(os.path.join(ROOT, "db", "berlin_property_ops.duckdb"), read_only=True)
print("\nRow counts per layer")
print(f"{'layer':<6} {'table':<32} {'rows':>12}")
for schema in ["raw", "dq", "core", "mart"]:
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = ? ORDER BY 1", [schema]).fetchall():
        n = con.execute(f'SELECT COUNT(*) FROM {schema}."{t}"').fetchone()[0]
        print(f"{schema:<6} {t:<32} {n:>12,}")
k = con.execute("""SELECT units, soll_sep_2026_eur, open_arrears_eur, arrears_rate_of_monthly_soll, open_tickets
                   FROM mart.portfolio_kpi""").fetchone()
st = con.execute("SELECT COUNT(*) FROM core.fact_service_charge_statement").fetchone()[0]
dq = dict(con.execute("SELECT result, COUNT(*) FROM dq.results GROUP BY 1").fetchall())
print("\nHeadline numbers (snapshot 2026-09-30, SYNTHETIC data)")
print(f"  units                     {k[0]:,}")
print(f"  Soll Sep 2026 (EUR)       {k[1]:,.2f}")
print(f"  open arrears (EUR)        {k[2]:,.2f}  ({k[3]:.1%} of Sep Soll)")
print(f"  open tickets              {k[4]:,}")
print(f"  service-charge statements {st:,}")
print(f"  DQ checks                 {dq.get('FAIL', 0)} FAIL / {dq.get('PASS', 0)} PASS")
con.close()

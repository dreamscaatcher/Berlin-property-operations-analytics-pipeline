#!/usr/bin/env python3
"""Build the DuckDB database from data/raw/*.csv and run all SQL (01-05).
Run from anywhere:  python3 scripts/build_db.py"""
import os, duckdb, glob
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
DB = os.path.join("db", "berlin_property_ops.duckdb")
if os.path.exists(DB):
    os.remove(DB)
os.makedirs("db", exist_ok=True)
con = duckdb.connect(DB)
for f in sorted(glob.glob("sql/0[1-5]_*.sql")):
    print("running", f)
    con.execute(open(f, encoding="utf-8").read())
print(con.sql("SELECT check_id, check_name, failed_keys, failed_rows, result FROM dq.results"))
print(con.sql("SELECT * FROM mart.portfolio_kpi"))
con.close()
print("built", DB)

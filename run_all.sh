#!/usr/bin/env bash
# Rebuild everything from scratch: synthetic data -> DuckDB (raw, dq, core, mart)
# -> QA report + Power BI CSVs -> Power BI workbook (xlsx). Linux / macOS / Git Bash.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -d .venv ] || "$PY" -m venv .venv
if [ -x .venv/bin/python ]; then VPY=.venv/bin/python; else VPY=.venv/Scripts/python.exe; fi
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet -r requirements.txt
"$VPY" data_generation/generate_data_33k.py   # 1. synthetic raw CSVs (fixed seed)
"$VPY" scripts/build_db.py                    # 2. DuckDB: sql/01..05
"$VPY" scripts/export.py                      # 3. sql/06 results, qa/dq_report.md, powerbi/csv
"$VPY" scripts/build_xlsx.py                  # 4. powerbi/Berlin_Property_Ops_33k.xlsx (Power BI source)
"$VPY" scripts/row_counts.py

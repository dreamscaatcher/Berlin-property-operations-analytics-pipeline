#!/usr/bin/env bash
# Optional dbt teaching project. Run the main pipeline first (../run_all.sh),
# because load_raw.py reads ../powerbi/csv. Output is saved to outputs/.
set -u
cd "$(dirname "$0")"
export DBT_PROFILES_DIR="$PWD"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
source .venv/bin/activate
mkdir -p outputs
python scripts/load_raw.py                 | tee outputs/00_load_raw.txt
dbt --no-use-colors debug           > outputs/01_dbt_debug.txt 2>&1
dbt --no-use-colors run             > outputs/02_dbt_run.txt 2>&1
dbt --no-use-colors test            > outputs/03_dbt_test.txt 2>&1
dbt --no-use-colors build           > outputs/04_dbt_build.txt 2>&1
dbt --no-use-colors docs generate   > outputs/05_dbt_docs_generate.txt 2>&1
python scripts/row_counts.py        > outputs/06_row_counts_and_samples.txt 2>&1
python scripts/lineage.py           > outputs/07_lineage_edges.txt
for f in outputs/02_dbt_run.txt outputs/03_dbt_test.txt outputs/04_dbt_build.txt; do echo "$f: $(tail -n 1 "$f")"; done

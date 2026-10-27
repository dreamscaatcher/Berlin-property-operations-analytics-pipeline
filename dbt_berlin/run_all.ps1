# Optional dbt teaching project (Windows PowerShell).
# Run the main pipeline first (..\run_all.ps1): load_raw.py reads ..\powerbi\csv.
# Usage:  powershell -ExecutionPolicy Bypass -File .\run_all.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:DBT_PROFILES_DIR = $PSScriptRoot
$py = if ($env:PIPELINE_PY) { $env:PIPELINE_PY } else { "py" }
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    & $py -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}
& .\.venv\Scripts\Activate.ps1
New-Item -ItemType Directory -Force outputs | Out-Null
python scripts\load_raw.py
dbt debug
dbt build
python scripts\row_counts.py

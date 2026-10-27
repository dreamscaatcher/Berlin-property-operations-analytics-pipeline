# Rebuild everything from scratch on Windows (PowerShell):
#   synthetic data -> DuckDB (raw, dq, core, mart) -> QA report + Power BI CSVs -> Power BI workbook (xlsx)
# Usage (from this folder):
#   powershell -ExecutionPolicy Bypass -File .\run_all.ps1              # uses the default Python (py launcher)
#   powershell -ExecutionPolicy Bypass -File .\run_all.ps1 -PyVersion 3.12   # fallback if a package fails on 3.14
param([string]$PyVersion = "")
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"   # DuckDB prints box-drawing characters

function Step($label, [scriptblock]$cmd) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    $t = Get-Date
    & $cmd
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $label (exit $LASTEXITCODE)" -ForegroundColor Red; exit $LASTEXITCODE }
    Write-Host ("done in {0:N0} s" -f ((Get-Date) - $t).TotalSeconds)
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    if ($PyVersion) { Step "create .venv (Python $PyVersion)" { py -$PyVersion -m venv .venv } }
    else            { Step "create .venv"                     { py -m venv .venv } }
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py --version
Step "pip install -r requirements.txt" { & $py -m pip install --quiet --upgrade pip; & $py -m pip install --quiet -r requirements.txt }
Step "1/4 generate synthetic raw CSVs"   { & $py data_generation\generate_data_33k.py }
Step "2/4 build DuckDB (sql 01-05)"      { & $py scripts\build_db.py }
Step "3/4 QA report + Power BI CSVs"     { & $py scripts\export.py }
Step "4/4 Power BI workbook (xlsx)"      { & $py scripts\build_xlsx.py }
Step "row counts per layer"              { & $py scripts\row_counts.py }

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher (py) was not found. Install Python 3.11 or newer from python.org."
}

if (-not (Test-Path .venv)) {
    & py -3 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e . -r requirements-build.txt
& .\.venv\Scripts\python.exe scripts\build.py

Write-Host "Built dist\KeplerSet.exe and dist\KeplerSetCLI.exe"

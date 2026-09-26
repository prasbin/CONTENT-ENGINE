# Runs the CONTENT ENGINE API with auto-reload (development).
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Join-Path $PSScriptRoot "..")
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

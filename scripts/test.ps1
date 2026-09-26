# Runs the CONTENT ENGINE test suite + lint (development).
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Join-Path $PSScriptRoot "..")
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m ruff format --check .
exit $LASTEXITCODE

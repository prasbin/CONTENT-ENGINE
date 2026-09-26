#!/usr/bin/env sh
# Runs the CONTENT ENGINE API with auto-reload (development).
set -e
cd "$(dirname "$0")/.."
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

#!/usr/bin/env sh
# Runs the CONTENT ENGINE test suite + lint (development).
set -e
cd "$(dirname "$0")/.."
python -m pytest -q
python -m ruff check .
python -m ruff format --check .

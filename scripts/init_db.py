"""Initialize the database (create tables) without starting the server.

Usage (from the repository root):

    python scripts/init_db.py

Exit codes: 0 = success, 1 = configuration/database error.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.core.config import ConfigurationError, Settings
    from app.db.session import create_engine_from_url, init_db
    from sqlalchemy import inspect

    try:
        settings = Settings.load()
    except ConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        engine = create_engine_from_url(settings.ce_database_url)
        init_db(engine)
        tables = sorted(inspect(engine).get_table_names())
        target = engine.url.database or str(engine.url)
        engine.dispose()
    except Exception as exc:  # pragma: no cover - depends on local FS/DB state
        print(f"ERROR: could not initialize database: {exc}", file=sys.stderr)
        return 1

    print(f"Database initialized: {target}")
    print(f"Tables: {', '.join(tables) if tables else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

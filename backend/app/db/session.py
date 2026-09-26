"""Engine/session factories.

Kept portable across SQLite (development) and PostgreSQL (future server
deployment): nothing SQLite-specific leaks outside this module.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.paths import project_path

_SQLITE_PREFIX = "sqlite:///"


def normalize_database_url(database_url: str) -> str:
    """Anchor relative SQLite file paths at the repository root.

    Relative paths such as ``sqlite:///./data/x.db`` would otherwise
    depend on the process working directory (root vs ``backend/`` vs a
    service manager's directory). Absolute paths, ``:memory:``, and
    non-SQLite URLs pass through unchanged.
    """
    if not database_url.startswith(_SQLITE_PREFIX):
        return database_url
    raw_path = database_url[len(_SQLITE_PREFIX) :]
    if raw_path in ("", ":memory:") or raw_path.startswith("/"):
        return database_url
    if Path(raw_path).is_absolute():
        return database_url
    return _SQLITE_PREFIX + project_path(raw_path).as_posix()


def _prepare_sqlite_file(database_url: str) -> None:
    """Ensure the parent directory of a SQLite file exists."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return
    database = url.database
    if database in (None, "", ":memory:"):
        return
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_engine_from_url(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine for the given SQLAlchemy database URL."""
    if not database_url:
        raise ValueError("database URL must not be empty")
    database_url = normalize_database_url(database_url)
    options: dict[str, object] = {"echo": echo, "future": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        _prepare_sqlite_file(database_url)
    return create_engine(database_url, **options)  # type: ignore[arg-type]


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db(engine: Engine) -> None:
    """Create all tables (Phase 1 foundation; Alembic migrations come later)."""
    from app.db.base import Base
    from app.models import Job  # noqa: F401  (import registers the model)

    Base.metadata.create_all(engine)


def check_database(engine: Engine | None) -> bool:
    """Return True when the database answers a trivial query."""
    if engine is None:
        return False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - defensive
        return False


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional session wrapper: commit on success, rollback on error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

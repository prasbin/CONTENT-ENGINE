"""SQLAlchemy declarative base shared by all models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for CONTENT ENGINE ORM models."""

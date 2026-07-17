"""SQLAlchemy engine, session factory, and declarative base."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

_connect_args = {"check_same_thread": False} if _settings.is_sqlite else {}

engine: Engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    future=True,
)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    """Enable foreign keys + WAL on SQLite for correctness and concurrency."""
    if _settings.is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables. Import models here to ensure registration."""
    from app import models  # noqa: F401  (side-effect: register mappers)

    Base.metadata.create_all(bind=engine)

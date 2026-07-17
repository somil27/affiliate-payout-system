"""Pytest fixtures — isolated in-memory SQLite per test."""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import session as db_session
from app.database.session import Base
from app.main import create_app


@pytest.fixture()
def engine():
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    # Point the app-wide SessionLocal at our test engine.
    db_session.SessionLocal = TestingSession
    db_session.engine = engine
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine):
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db_session.SessionLocal = TestingSession
    db_session.engine = engine
    app = create_app()
    with TestClient(app) as c:
        yield c

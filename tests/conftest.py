"""Shared test fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import db


@pytest.fixture
def fresh_db(monkeypatch):
    """Give each test a clean, throwaway in-memory database.

    We point db.engine / db.SessionLocal at an in-memory SQLite, create the
    tables, and let the test run. Nothing touches the real database, and the
    DB vanishes when the test ends.
    """
    engine = create_engine(
        "sqlite://",                                  # in-memory
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,                         # one shared in-memory DB for the test
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=engine))
    db.Base.metadata.create_all(engine)
    yield

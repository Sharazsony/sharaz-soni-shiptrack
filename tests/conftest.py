"""Shared pytest fixtures. Tests run only against PostgreSQL — this app uses
native PostgreSQL enum types, which SQLite cannot create.
"""
from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# AUDIT_LOG_PATH and API_KEY must be set before app.config is imported,
# since Settings() is instantiated at import time.
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("POSTGRES_USER", "appuser")
os.environ.setdefault("POSTGRES_PASSWORD", "localdevpassword")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "shiptrack")

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = settings.database_url

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": settings.api_key}


@pytest.fixture(scope="function")
def audit_log_path(tmp_path, monkeypatch) -> str:
    path = str(tmp_path / "audit.log")
    monkeypatch.setattr(settings, "audit_log_path", path)
    return path

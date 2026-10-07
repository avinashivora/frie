"""Shared fixtures for Phase 2 persistence tests: isolated file database per test."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def storage_dir(tmp_path, monkeypatch) -> Path:
    """Redirect file storage to a temporary directory for one test."""

    target = tmp_path / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRIE_STORAGE_DIR", str(target))
    return target


@pytest.fixture()
def db_file(tmp_path):
    """Path of a fresh database file for one test."""

    return tmp_path / "phase2_test.db"


@pytest.fixture()
def test_client(db_file) -> Iterator[tuple[TestClient, Any]]:
    """Test client bound to the isolated database, plus its session factory."""

    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = testing_sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, testing_sessions
    finally:
        app.dependency_overrides.clear()
        testing_sessions.close_all()
        engine.dispose()


@pytest.fixture()
def client_tables(db_file) -> list[str]:
    """Table names present in a freshly initialized database file."""

    engine = create_engine(f"sqlite:///{db_file}", poolclass=NullPool)
    Base.metadata.create_all(bind=engine)
    try:
        return inspect(engine).get_table_names()
    finally:
        engine.dispose()


def register_user(client: TestClient, email: str, password: str) -> dict[str, Any]:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def login_user(client: TestClient, email: str, password: str) -> dict[str, Any]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

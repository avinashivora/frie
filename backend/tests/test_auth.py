"""Registration, login, hashing, session, isolation, and seed tests."""

from __future__ import annotations

from app.db.models import User
from app.db.seed import ensure_demo_user
from tests.conftest import auth_headers, login_user, register_user


def test_database_initializes_with_all_tables(client_tables: list[str]) -> None:
    assert {
        "users",
        "sessions",
        "customer_profiles",
        "documents",
        "financial_features",
        "predictions",
        "explanations",
    }.issubset(set(client_tables))


def test_register_success_returns_token_without_password_material(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "alice@example.com", "Secret123!")

    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.com"
    assert "id" in body["user"]
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    raw = client.post("/auth/register", json={"email": "other@example.com", "password": "Secret123!"})
    assert raw.status_code == 201
    assert "password_hash" not in raw.text
    assert "Secret123!" not in raw.text


def test_register_duplicate_email_is_rejected(test_client) -> None:
    client, _ = test_client
    register_user(client, "bob@example.com", "Secret123!")

    response = client.post("/auth/register", json={"email": "BOB@example.com", "password": "Secret123!"})

    assert response.status_code == 409


def test_register_invalid_email_is_rejected(test_client) -> None:
    client, _ = test_client

    for bad in ("not-an-email", "a@b", "", "x" * 250 + "@example.com"):
        response = client.post("/auth/register", json={"email": bad, "password": "Secret123!"})
        assert response.status_code == 422, bad


def test_register_short_password_is_rejected(test_client) -> None:
    client, _ = test_client

    response = client.post("/auth/register", json={"email": "cara@example.com", "password": "short"})
    assert response.status_code == 422


def test_password_is_hashed_with_salt_not_plaintext(test_client) -> None:
    client, sessions = test_client
    register_user(client, "dave@example.com", "Secret123!")
    register_user(client, "erin@example.com", "Secret123!")

    with sessions() as db:
        rows = db.query(User).all()
        hashes = [row.password_hash for row in rows]

    assert len(hashes) == 2
    for stored in hashes:
        assert stored.startswith("pbkdf2_sha256$")
        assert "Secret123!" not in stored
    assert hashes[0] != hashes[1]


def test_login_success_and_me(test_client) -> None:
    client, _ = test_client
    register_user(client, "fred@example.com", "Secret123!")

    body = login_user(client, "fred@example.com", "Secret123!")
    assert body["token_type"] == "bearer"

    me = client.get("/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "fred@example.com"
    assert "password_hash" not in me.json()


def test_login_wrong_password_is_rejected(test_client) -> None:
    client, _ = test_client
    register_user(client, "gina@example.com", "Secret123!")

    response = client.post("/auth/login", json={"email": "gina@example.com", "password": "WrongPass1!"})
    assert response.status_code == 401


def test_login_unknown_email_is_rejected(test_client) -> None:
    client, _ = test_client

    response = client.post("/auth/login", json={"email": "nobody@example.com", "password": "Secret123!"})
    assert response.status_code == 401


def test_me_without_token_is_rejected(test_client) -> None:
    client, _ = test_client

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_user_isolation_between_accounts(test_client) -> None:
    client, _ = test_client
    register_user(client, "hank@example.com", "Secret123!")
    ivy = register_user(client, "ivy@example.com", "Secret123!")

    me = client.get("/auth/me", headers=auth_headers(ivy["access_token"]))
    assert me.json()["email"] == "ivy@example.com"
    assert me.json()["id"] == ivy["user"]["id"]


def test_demo_seed_is_idempotent(test_client) -> None:
    client, sessions = test_client

    with sessions() as db:
        first, created_first = ensure_demo_user(db, email="individual@frie.demo", password="FRIE123")
        db.commit()
        second, created_second = ensure_demo_user(db, email="individual@frie.demo", password="FRIE123")
        db.commit()
        count = db.query(User).filter(User.email == "individual@frie.demo").count()

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert count == 1
    assert second.password_hash.startswith("pbkdf2_sha256$")
    assert "FRIE123" not in second.password_hash

    login = client.post("/auth/login", json={"email": "individual@frie.demo", "password": "FRIE123"})
    assert login.status_code == 200

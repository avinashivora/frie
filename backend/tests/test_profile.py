"""Customer profile persistence, validation, isolation, and durability tests."""

from __future__ import annotations

from app.db.models import CustomerProfile
from tests.conftest import auth_headers, register_user


def test_profile_requires_authentication(test_client) -> None:
    client, _ = test_client

    assert client.get("/profile").status_code == 401
    assert client.put("/profile", json={"city": "Pune"}).status_code == 401


def test_profile_missing_before_first_save(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "pam@example.com", "Secret123!")

    response = client.get("/profile", headers=auth_headers(body["access_token"]))

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["profile"] is None
    assert envelope["completeness"]["completed"] == 0
    assert envelope["completeness"]["required"] == 18
    assert envelope["readiness"]["profile_ready"] is False
    assert envelope["readiness"]["frie_scoring_ready"] is False


def test_profile_save_and_read_roundtrip(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "quinn@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    saved = client.put(
        "/profile",
        json={"city": "Pune", "monthly_income": 95000, "children_count": 1},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["profile"]["city"] == "Pune"
    assert saved.json()["profile"]["monthly_income"] == 95000
    assert saved.json()["profile"]["user_id"] == body["user"]["id"]

    fetched = client.get("/profile", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["profile"]["city"] == "Pune"


def test_profile_update_merges_fields(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "rob@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    client.put("/profile", json={"city": "Pune", "monthly_income": 95000}, headers=headers)

    updated = client.put("/profile", json={"occupation": "Laborers"}, headers=headers)

    assert updated.status_code == 200
    assert updated.json()["profile"]["occupation"] == "Laborers"
    assert updated.json()["profile"]["city"] == "Pune"


def test_profile_rejects_invalid_values(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "sara@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile", json={"monthly_income": -5}, headers=headers).status_code == 422
    assert client.put("/profile", json={"children_count": -1}, headers=headers).status_code == 422


def test_profile_is_isolated_between_users(test_client) -> None:
    client, _ = test_client
    tom = register_user(client, "tom@example.com", "Secret123!")
    uma = register_user(client, "uma@example.com", "Secret123!")

    client.put("/profile", json={"city": "Pune"}, headers=auth_headers(tom["access_token"]))

    envelope = client.get("/profile", headers=auth_headers(uma["access_token"])).json()
    assert envelope["profile"] is None
    assert envelope["completeness"]["completed"] == 0

    client.put("/profile", json={"city": "Nagpur"}, headers=auth_headers(uma["access_token"]))
    assert client.get("/profile", headers=auth_headers(uma["access_token"])).json()["profile"]["city"] == "Nagpur"
    assert client.get("/profile", headers=auth_headers(tom["access_token"])).json()["profile"]["city"] == "Pune"


def test_profile_persists_in_the_database_file(test_client) -> None:
    client, sessions = test_client
    body = register_user(client, "vic@example.com", "Secret123!")
    client.put("/profile", json={"city": "Mumbai"}, headers=auth_headers(body["access_token"]))

    with sessions() as db:
        row = db.query(CustomerProfile).filter(CustomerProfile.user_id == body["user"]["id"]).first()

    assert row is not None
    assert row.city == "Mumbai"

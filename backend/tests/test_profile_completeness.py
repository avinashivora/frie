"""Profile completeness, readiness, and validation tests for the 18 USER features."""

from __future__ import annotations

from datetime import date, timedelta

import joblib

from app.core.config import get_settings
from app.db.models import Prediction
from app.schemas.profile import CATEGORICAL_LEVELS
from tests.conftest import auth_headers, register_user

COMPLETE_PROFILE = {
    "gender": "F",
    "date_of_birth": "1993-04-12",
    "children_count": 1,
    "family_size": 4,
    "family_status": "Married",
    "education_level": "Higher education",
    "housing_type": "House / apartment",
    "owns_car": "Y",
    "owns_property": "N",
    "income_type": "Working",
    "occupation": "Laborers",
    "organization_type": "Government",
    "contract_type": "Cash loans",
    "city": "Pune",
    "monthly_income": 95000,
    "employment_start": "2018-06-01",
}


def _envelope(client, headers):
    response = client.get("/profile", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_profile_is_not_ready(test_client) -> None:
    client, sessions = test_client
    body = register_user(client, "ca@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    saved = client.put("/profile", json={}, headers=headers)
    assert saved.status_code == 200

    envelope = _envelope(client, headers)
    assert envelope["profile"] is not None
    assert envelope["completeness"]["completed"] == 0
    assert envelope["completeness"]["required"] == 18
    assert envelope["completeness"]["percentage"] == 0
    assert len(envelope["completeness"]["missing"]) == 18
    assert envelope["readiness"]["profile_status"] == "NOT_READY"
    assert envelope["readiness"]["profile_ready"] is False
    assert envelope["readiness"]["frie_scoring_ready"] is False

    with sessions() as db:
        assert db.query(Prediction).count() == 0


def test_partial_profile_counts_mapped_features(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "cb@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    saved = client.put(
        "/profile",
        json={
            "gender": "F",
            "date_of_birth": "1993-04-12",
            "city": "Pune",
            "monthly_income": 95000,
            "occupation": "Laborers",
        },
        headers=headers,
    )

    assert saved.status_code == 200
    completeness = saved.json()["completeness"]
    assert completeness["completed"] == 6
    assert completeness["required"] == 18
    assert len(completeness["missing"]) == 12
    assert saved.json()["readiness"]["profile_status"] == "PARTIALLY_READY"
    assert saved.json()["readiness"]["profile_ready"] is False
    assert saved.json()["readiness"]["frie_scoring_ready"] is False


def test_complete_profile_is_ready_but_not_scoring_ready(test_client) -> None:
    client, sessions = test_client
    body = register_user(client, "cc@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    saved = client.put("/profile", json=COMPLETE_PROFILE, headers=headers)

    assert saved.status_code == 200
    envelope = saved.json()
    assert envelope["completeness"] == {
        "completed": 18,
        "required": 18,
        "percentage": 100.0,
        "missing": [],
    }
    assert envelope["readiness"] == {
        "profile_status": "READY",
        "profile_ready": True,
        "frie_scoring_ready": False,
    }

    with sessions() as db:
        assert db.query(Prediction).count() == 0


def test_profile_levels_match_encoder_categories() -> None:
    pipeline = joblib.load(get_settings().model_path)
    preprocessor = pipeline.named_steps["preprocessing"]
    position = list(preprocessor.transformers[1][2])
    encoder = preprocessor.named_transformers_["categorical"].named_steps["onehot"]
    trained = {name: tuple(map(str, categories)) for name, categories in zip(position, encoder.categories_)}

    assert set(CATEGORICAL_LEVELS.keys()) == {
        "gender",
        "family_status",
        "education_level",
        "housing_type",
        "owns_car",
        "owns_property",
        "income_type",
        "occupation",
        "organization_type",
        "contract_type",
    }
    for name, levels in CATEGORICAL_LEVELS.items():
        assert trained[name] == levels


def test_profile_rejects_malformed_birth_date(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "cd@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile", json={"date_of_birth": "not-a-date"}, headers=headers).status_code == 422


def test_profile_rejects_future_birth_date(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "ce@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = client.put("/profile", json={"date_of_birth": tomorrow}, headers=headers)

    assert response.status_code == 422


def test_profile_rejects_unreasonable_age(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "cf@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    response = client.put("/profile", json={"date_of_birth": "1800-01-01"}, headers=headers)

    assert response.status_code == 422


def test_profile_rejects_future_employment_start(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "cg@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = client.put("/profile", json={"employment_start": tomorrow}, headers=headers)

    assert response.status_code == 422


def test_profile_rejects_non_positive_income(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "ch@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile", json={"monthly_income": 0}, headers=headers).status_code == 422
    assert client.put("/profile", json={"monthly_income": -100}, headers=headers).status_code == 422


def test_profile_rejects_negative_counts(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "ci@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile", json={"children_count": -1}, headers=headers).status_code == 422
    assert client.put("/profile", json={"family_size": 0}, headers=headers).status_code == 422


def test_profile_rejects_unknown_categorical_level(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "cj@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile", json={"occupation": "Astronaut"}, headers=headers).status_code == 422
    assert client.put("/profile", json={"gender": "X"}, headers=headers).status_code == 422


def test_profile_envelope_shape(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "ck@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    envelope = _envelope(client, headers)

    assert set(envelope.keys()) == {"profile", "completeness", "readiness"}
    assert set(envelope["completeness"].keys()) == {"completed", "required", "percentage", "missing"}
    assert set(envelope["readiness"].keys()) == {"profile_status", "profile_ready", "frie_scoring_ready"}

from __future__ import annotations

from tests.conftest import auth_headers, register_user


COMPLETE_PROFILE = {
    "gender": "F", "date_of_birth": "1993-04-12", "children_count": 1,
    "family_size": 4, "family_status": "Married", "education_level": "Higher education",
    "housing_type": "House / apartment", "owns_car": "Y", "owns_property": "N",
    "income_type": "Working", "occupation": "Laborers", "organization_type": "Government",
    "contract_type": "Cash loans", "city": "Pune", "monthly_income": 95000,
    "employment_start": "2018-06-01",
}


def _account(client, email: str):
    account = register_user(client, email, "Secret123!")
    return auth_headers(account["access_token"])


def test_fresh_user_gets_source_guidance_and_no_score(test_client) -> None:
    client, sessions = test_client
    headers = _account(client, "assessment-empty@example.com")

    state = client.get("/analysis/status", headers=headers)
    assert state.status_code == 200
    body = state.json()
    assert body["assessment_state"] == "insufficient"
    assert body["can_assess"] is False
    sources = {item["key"]: item for item in body["sources"]}
    assert sources["profile"]["status"] == "required"
    assert sources["income"]["status"] == "required"
    assert sources["bank"]["status"] == "required"
    assert "98" not in state.text and "features" not in state.text

    response = client.post("/analysis/assess", headers=headers)
    assert response.status_code == 409
    assert "sources" in response.json()["detail"]
    with sessions() as db:
        from app.db.models import Prediction
        assert db.query(Prediction).count() == 0


def test_confirmed_product_absence_satisfies_source_state_but_unknown_does_not(test_client) -> None:
    client, _ = test_client
    headers = _account(client, "assessment-declarations@example.com")
    profile = client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    assert profile.status_code == 200, profile.text
    declarations = {
        "has_loan": "no", "insurance_status": "none",
        "inv_fd": "no", "inv_rd": "no", "inv_sip": "no",
        "inv_mutual_fund": "no", "inv_ppf": "no", "inv_nps": "no",
    }
    saved = client.put("/profile/financial-status", json=declarations, headers=headers)
    assert saved.status_code == 200, saved.text
    body = client.get("/analysis/status", headers=headers).json()
    assert body["assessment_state"] == "estimated"
    assert body["can_assess"] is True
    by_key = {item["key"]: item for item in body["sources"]}
    for key in ("loans", "insurance", "investments"):
        assert by_key[key]["status"] == "complete"

    unknown = {key: "unknown" for key in declarations}
    unknown["insurance_status"] = "none"  # A separate confirmed source permits an estimated assessment.
    saved = client.put("/profile/financial-status", json=unknown, headers=headers)
    assert saved.status_code == 200, saved.text
    after_unknown = client.get("/analysis/status", headers=headers).json()
    assert after_unknown["assessment_state"] == "estimated"
    by_key = {item["key"]: item for item in after_unknown["sources"]}
    assert by_key["loans"]["status"] == "unknown"
    assert by_key["investments"]["status"] == "unknown"


def test_structured_bank_import_is_preferred_without_double_counting() -> None:
    from app.services.feature_engineering import Assembly, _bank_block
    from types import SimpleNamespace
    import json

    transaction = {"date": "2024-01-05", "description": "SALARY-CREDIT", "debit": 0, "credit": 95000, "balance": 215000}
    pdf = (SimpleNamespace(id=1), SimpleNamespace(structured_data=json.dumps({"transactions": [transaction]})))
    csv = (SimpleNamespace(id=2), SimpleNamespace(structured_data=json.dumps({"imported_transactions": [{"date": "2024-01-05", "description": "SALARY-CREDIT", "debit_amount": 0, "credit_amount": 95000, "balance": 215000}]})))
    preferred, only_csv, only_pdf = Assembly(), Assembly(), Assembly()
    _bank_block(preferred, pdf, csv)
    _bank_block(only_csv, None, csv)
    _bank_block(only_pdf, pdf)
    assert preferred.values == only_csv.values == only_pdf.values
    assert preferred.sources["savings_balance"] == 2

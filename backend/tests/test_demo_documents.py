"""End-to-end tests using the committed synthetic demo documents.

Proves the documented demo flow reaches READY 98 with real parsing,
real OCR, and honest provenance -- no hardcoded values anywhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.feature_contract import get_feature_contract
from tests.conftest import auth_headers, register_user
from tests.test_profile_completeness import COMPLETE_PROFILE

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_documents"

BANK_DOC = "02_bank_statement.pdf"
CREDIT_DOC = "03_credit_report.pdf"


def _read(name: str) -> bytes:
    return (DEMO_DIR / name).read_bytes()


def _upload(client, headers, name: str, doc_type: str, mime: str = "application/pdf"):
    response = client.post(
        "/documents/upload",
        files={"file": (name, _read(name), mime)},
        data={"document_type": doc_type},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _extract_accept(client, headers, document_id: int):
    extracted = client.post(f"/documents/{document_id}/extract", headers=headers)
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["extraction_status"] == "EXTRACTED"
    reviewed = client.post(
        f"/documents/{document_id}/review", json={"decision": "accept"}, headers=headers
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "REVIEWED"


def _full_demo_user(client, email: str):
    body = register_user(client, email, "Secret123!")
    headers = auth_headers(body["access_token"])
    response = client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    assert response.status_code == 200, response.text
    response = client.put(
        "/profile/financial-status",
        json={
            "has_loan": "yes",
            "insurance_status": "life",
            "inv_fd": "yes",
            "inv_rd": "yes",
            "inv_sip": "yes",
            "inv_mutual_fund": "yes",
            "inv_ppf": "yes",
            "inv_nps": "yes",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    for name, doc_type in (
        ("01_salary_slip.pdf", "salary_income_proof"),
        ("02_bank_statement.pdf", "bank_statement"),
        ("03_credit_report.pdf", "credit_report"),
        ("07_loan_document.pdf", "loan_document"),
        ("04_insurance_policy.pdf", "insurance_document"),
        ("05_investment_statement.pdf", "investment_statement"),
    ):
        created = _upload(client, headers, name, doc_type)
        _extract_accept(client, headers, created["id"])
    return headers


def test_demo_bank_statement_parses_all_required_categories(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "demo1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _upload(client, headers, BANK_DOC, "bank_statement")
    extracted = client.post(f"/documents/{created['id']}/extract", headers=headers).json()

    transactions = extracted["structured_data"]["transactions"]
    descriptions = " ".join(t["description"] for t in transactions)
    for keyword in ("GROCERY", "SWIGGY", "RENT", "ELECTRICITY", "OLA", "SIP", "SALARY"):
        assert keyword in descriptions
    assert len(transactions) == 12 * 7


def test_demo_bank_grocery_and_transfer_semantics(test_client) -> None:
    client, _ = test_client
    headers = _full_demo_user(client, "demo2@example.com")
    client.post("/features/build", headers=headers)
    rows = {r["feature_name"]: r["value_num"] for r in client.get("/features", headers=headers).json()}

    # UPI grocery + UPI food both land in food_expense; the SIP transfer is excluded.
    assert rows["food_expense"] == 5500.0
    assert rows["rent_expense"] == 18000.0
    assert rows["transport_expense"] == 1200.0
    assert rows["upi_spending"] == 5500.0
    assert rows["synthetic_total_expense"] == 26200.0
    assert rows["monthly_savings"] == 63800.0
    assert rows["savings_balance"] == 885600.0


def test_demo_documents_reach_ready_98(test_client) -> None:
    client, sessions = test_client
    headers = _full_demo_user(client, "demo3@example.com")

    built = client.post("/features/build", headers=headers).json()
    readiness = client.get("/features/readiness", headers=headers).json()

    assert built["stored"] == 98
    assert readiness["status"] == "READY"
    assert readiness["available"] == 98
    assert readiness["missing"] == []
    assert readiness["by_provenance"] == {"USER": 19, "DOCUMENT": 63, "DERIVED": 16}

    contract = get_feature_contract()
    rows = client.get("/features", headers=headers).json()
    assert {r["feature_name"] for r in rows} == set(contract.feature_names)
    assert "frie_score" not in {r["feature_name"] for r in rows}
    assert built["status"] == "READY"


def test_demo_scanned_salary_png_uses_ocr(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "demo4@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _upload(client, headers, "06_scanned_salary_slip.png", "salary_income_proof", mime="image/png")

    extracted = client.post(f"/documents/{created['id']}/extract", headers=headers).json()

    assert extracted["extraction_status"] == "EXTRACTED"
    assert extracted["engine"] == "paddleocr"
    assert extracted["confidence"] is not None
    assert extracted["structured_data"]["gross_salary"] == 95000.0
    assert extracted["structured_data"]["net_salary"] == 78000.0


def test_demo_scanned_salary_pdf_uses_ocr_fallback(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "demo5@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _upload(client, headers, "06_scanned_salary_slip.pdf", "salary_income_proof")

    extracted = client.post(f"/documents/{created['id']}/extract", headers=headers).json()

    assert extracted["extraction_status"] == "EXTRACTED"
    assert extracted["engine"] == "paddleocr"
    assert extracted["structured_data"]["gross_salary"] == 95000.0


def test_new_user_has_empty_state_and_no_score(test_client) -> None:
    client, sessions = test_client
    body = register_user(client, "fresh9@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    profile = client.get("/profile", headers=headers).json()
    docs = client.get("/documents", headers=headers).json()
    readiness = client.get("/features/readiness", headers=headers).json()
    features = client.get("/features", headers=headers).json()

    assert profile["completeness"]["completed"] == 0
    assert docs == []
    assert readiness["status"] == "NOT_READY"
    assert readiness["available"] == 0
    assert features == []
    with sessions() as db:
        from app.db.models import Prediction

        assert db.query(Prediction).count() == 0


def test_second_user_sees_none_of_first_users_state(test_client) -> None:
    client, sessions = test_client
    first_headers = _full_demo_user(client, "demoA@example.com")
    client.post("/features/build", headers=first_headers)
    second = register_user(client, "demoB@example.com", "Secret123!")
    second_headers = auth_headers(second["access_token"])

    assert client.get("/profile", headers=second_headers).json()["completeness"]["completed"] == 0
    assert client.get("/documents", headers=second_headers).json() == []
    second_ready = client.get("/features/readiness", headers=second_headers).json()
    assert second_ready["status"] == "NOT_READY"
    assert client.get("/features", headers=second_headers).json() == []
    with sessions() as db:
        from app.db.models import Document, FinancialFeature, Prediction

        assert db.query(Document).count() == 6
        assert db.query(FinancialFeature).count() == 98
        assert db.query(Prediction).count() == 0

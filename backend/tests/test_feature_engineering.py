"""Feature engineering, readiness, provenance, and isolation tests.

A complete synthetic user (profile, declarations, six reviewed document
types) must assemble the exact 98-feature vector; partial and unknown
states must stay honest and never fabricate.
"""

from __future__ import annotations

import pytest

from app.core.feature_contract import get_feature_contract
from app.db.models import FinancialFeature, Prediction
from tests.conftest import auth_headers, register_user
from tests.test_profile_completeness import COMPLETE_PROFILE


def _pdf_bytes(lines: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    try:
        page = document.new_page(width=1200, height=1400)
        page.insert_text((72, 72), "\n".join(lines), fontsize=9)
        return document.tobytes()
    finally:
        document.close()


def _upload_extract_accept(client, headers, lines, doc_type, name="doc.pdf"):
    created = client.post(
        "/documents/upload",
        files={"file": (name, _pdf_bytes(lines), "application/pdf")},
        data={"document_type": doc_type},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    document = created.json()
    extracted = client.post(f"/documents/{document['id']}/extract", headers=headers)
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["extraction_status"] == "EXTRACTED"
    reviewed = client.post(
        f"/documents/{document['id']}/review", json={"decision": "accept"}, headers=headers
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "REVIEWED"
    return document


def _bank_lines() -> list[str]:
    lines = ["Demo Bank Statement", "Account No: 123456789012"]
    balance = 100000.0
    for month in range(1, 13):
        tag = f"{month:02d}/2024"
        for day, description, debit, credit in (
            ("05", "SALARY-CREDIT", 0.0, 95000.0),
            ("10", "UPI-SWIGGY-FOOD", 2500.0, 0.0),
            ("15", "HOUSE-RENT-NEFT", 18000.0, 0.0),
            ("20", "UPI-UBER-TRANSPORT", 800.0, 0.0),
        ):
            balance += credit - debit
            lines.append(f"{day}/{tag} {description} {debit:,.2f} {credit:,.2f} {balance:,.2f}")
    return lines


def _credit_lines() -> list[str]:
    lines = [
        "Demo Credit Bureau Report",
        "TRADELINE | lender=HDFC Bank | type=Credit Card | limit=500000 | balance=125000 "
        "| debt=125000 | overdue=0 | dpd=0 | status=Active",
        "TRADELINE | lender=SBI | type=Home Loan | limit=2000000 | balance=1500000 "
        "| debt=1500000 | overdue=5000 | dpd=15 | prolong=1 | status=Active",
    ]
    for month in range(1, 13):
        lines.append(
            f"INSTALLMENT | date=05/{month:02d}/2024 | paid_date=05/{month:02d}/2024 "
            f"| due=18000.00 | paid=18000.00"
        )
    lines += [
        "PREVAPP | status=Approved | credit=300000 | annuity=15000 | down=20000 | goods=280000",
        "PREVAPP | status=Refused | credit=100000 | annuity=8000 | down=10000 | goods=90000",
        "CARDMONTH | balance=125000 | limit=500000 | drawings=20000 | payments=18000 "
        "| minimum=5000 | dpd=0 | dpd_default=0",
        "CARDMONTH | balance=130000 | limit=500000 | drawings=25000 | payments=20000 "
        "| minimum=5200 | dpd=5 | dpd_default=0",
        "POSREC | installments=12 | future=6 | dpd=0 | dpd_default=0",
        "POSREC | installments=6 | future=2 | dpd=10 | dpd_default=1",
    ]
    return lines


def _insurance_lines() -> list[str]:
    lines = [
        "Demo Life Insurance Policy",
        "Premium: Rs. 1200.00",
        "Frequency: Monthly",
        "Status: In-force",
    ]
    lines += [f"Premium paid on 05/{month:02d}/2024" for month in range(1, 13)]
    return lines


def _full_user(client, email: str):
    body = register_user(client, email, "Secret123!")
    headers = auth_headers(body["access_token"])
    response = client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    assert response.status_code == 200, response.text
    response = client.put(
        "/profile/financial-status",
        json={
            "has_loan": "yes",
            "insurance_status": "both",
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
    _upload_extract_accept(client, headers, _bank_lines(), "bank_statement", "stmt.pdf")
    _upload_extract_accept(client, headers, _credit_lines(), "credit_report", "credit.pdf")
    _upload_extract_accept(
        client, headers,
        ["Loan Sanction", "Loan Amount: Rs. 990000.00", "EMI: Rs. 28944.00"],
        "loan_document", "loan.pdf",
    )
    _upload_extract_accept(client, headers, _insurance_lines(), "insurance_document", "policy.pdf")
    _upload_extract_accept(
        client, headers,
        ["Holdings", "Fixed Deposit: Rs. 200000.00", "Recurring Deposit: Rs. 50000.00",
         "SIP: Rs. 5000.00", "Mutual Fund: Rs. 150000.00", "PPF: Rs. 200000.00",
         "NPS: Rs. 100000.00"],
        "investment_statement", "invest.pdf",
    )
    _upload_extract_accept(
        client, headers,
        ["Salary Slip", "Employee Name: Demo User", "Gross: Rs. 95000.00", "Net Salary: Rs. 78000.00"],
        "salary_income_proof", "salary.pdf",
    )
    return headers


def test_full_user_reaches_ready_98(test_client) -> None:
    client, _ = test_client
    headers = _full_user(client, "full1@example.com")

    readiness = client.get("/features/readiness", headers=headers).json()

    assert readiness["total_required"] == 98
    assert readiness["available"] == 98
    assert readiness["missing"] == []
    assert readiness["status"] == "READY"
    assert sum(readiness["by_provenance"].values()) == 98
    assert readiness["by_provenance"] == {"USER": 19, "DOCUMENT": 63, "DERIVED": 16}


def test_build_persists_98_idempotently(test_client) -> None:
    client, sessions = test_client
    headers = _full_user(client, "full2@example.com")

    first = client.post("/features/build", headers=headers).json()
    second = client.post("/features/build", headers=headers).json()

    assert first["stored"] == 98
    assert second["stored"] == 98
    assert second["status"] == "READY"
    rows = client.get("/features", headers=headers).json()
    assert len(rows) == 98
    assert len({row["feature_name"] for row in rows}) == 98
    with sessions() as db:
        count = db.query(FinancialFeature).count()
    assert count == 98


def test_built_vector_matches_contract_order_and_predicts(test_client) -> None:
    from app.core.feature_contract import get_feature_contract
    from app.services.feature_service import FeatureService
    from app.services.prediction_service import PredictionService
    from app.core.config import get_settings

    client, _ = test_client
    headers = _full_user(client, "full3@example.com")
    client.post("/features/build", headers=headers)
    rows = {row["feature_name"]: row for row in client.get("/features", headers=headers).json()}

    contract = get_feature_contract()
    assert set(rows.keys()) == set(contract.feature_names)
    assert "frie_score" not in rows
    payload = {
        name: rows[name]["value_num"] if rows[name]["value_num"] is not None else rows[name]["value_text"]
        for name in contract.feature_names
    }
    service = PredictionService(get_settings())
    service.load_model()
    frame = FeatureService(contract).build_model_input(payload, service._pipeline_feature_order)
    assert list(frame.columns) == list(service._pipeline_feature_order)
    assert frame.shape == (1, 98)

    response = client.post("/predict", json={"features": payload})
    assert response.status_code == 200
    assert response.json()["reliability_level"] in {"Poor", "Average", "Good", "Excellent"}


def test_derived_formulas_spot_check(test_client) -> None:
    client, _ = test_client
    headers = _full_user(client, "full4@example.com")
    client.post("/features/build", headers=headers)
    rows = {row["feature_name"]: row["value_num"] for row in client.get("/features", headers=headers).json()}

    assert rows["current_dti"] == pytest.approx(28944.0 / 95000.0, abs=1e-4)
    assert rows["bureau_dti"] == pytest.approx(1625000.0 / 95000.0, abs=1e-4)
    assert rows["previous_approval_ratio"] == pytest.approx(0.5)
    assert rows["bureau_overdue_ratio"] == pytest.approx(5000.0 / 2500000.0, abs=1e-6)
    assert rows["on_time_payment_ratio"] == pytest.approx(1.0)
    assert rows["payment_coverage_ratio"] == pytest.approx(1.0)
    assert rows["synthetic_total_expense"] == pytest.approx(21300.0)
    assert rows["synthetic_total_emi"] == pytest.approx(28944.0)
    assert rows["available_surplus"] == pytest.approx(95000.0 - 21300.0 - 28944.0)
    assert rows["savings_rate"] == pytest.approx(73700.0 / 95000.0, abs=1e-4)
    assert rows["digital_payment_ratio"] == pytest.approx(3300.0 / 21300.0, abs=1e-4)
    assert rows["cash_flow_mean"] == pytest.approx(73700.0)
    assert rows["cash_flow_std"] == pytest.approx(0.0)
    assert rows["cash_flow_min"] == pytest.approx(73700.0)
    assert rows["cash_flow_negative_months"] == 0
    assert rows["bureau_overdue_days"] == 15
    assert rows["total_late_payments"] == 0
    assert rows["max_card_dpd"] == 5
    assert rows["insurance_payment_consistency"] == pytest.approx(1.0)


def test_provenance_spot_check(test_client) -> None:
    client, _ = test_client
    headers = _full_user(client, "full5@example.com")
    client.post("/features/build", headers=headers)
    rows = {row["feature_name"]: row for row in client.get("/features", headers=headers).json()}

    assert rows["monthly_income"]["provenance"] == "DOCUMENT"
    assert rows["food_expense"]["provenance"] == "DOCUMENT"
    assert rows["current_dti"]["provenance"] == "DERIVED"
    assert rows["bureau_debt_amount"]["provenance"] == "DOCUMENT"
    assert rows["fd_amount"]["provenance"] == "DOCUMENT"
    assert rows["health_insurance"]["provenance"] == "USER"


def test_fresh_user_is_not_ready(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "fresh1@example.com", "Secret123!")

    readiness = client.get("/features/readiness", headers=auth_headers(body["access_token"])).json()

    assert readiness["status"] == "NOT_READY"
    assert readiness["available"] == 0
    assert len(readiness["missing"]) == 98
    assert client.get("/features", headers=auth_headers(body["access_token"])).json() == []


def test_unknown_declarations_stay_missing_not_zero(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "unk1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    client.put(
        "/profile/financial-status",
        json={"has_loan": "unknown", "insurance_status": "unknown"},
        headers=headers,
    )

    readiness = client.get("/features/readiness", headers=headers).json()
    values = {row["feature_name"] for row in client.get("/features", headers=headers).json()}

    assert "bureau_debt_amount" not in values
    assert readiness["status"] != "READY"
    assert any("credit history unknown" in entry["reason"] for entry in readiness["missing"])


def test_confirmed_none_semantics(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "none1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    client.put(
        "/profile/financial-status",
        json={
            "has_loan": "no",
            "insurance_status": "none",
            "inv_fd": "no",
            "inv_rd": "no",
            "inv_sip": "no",
            "inv_mutual_fund": "no",
            "inv_ppf": "no",
            "inv_nps": "no",
        },
        headers=headers,
    )

    readiness = client.get("/features/readiness", headers=headers).json()
    names = {entry["feature"] for entry in readiness["missing"]}

    assert readiness["status"] == "PARTIALLY_READY"
    assert "previous_approval_ratio" in names
    assert "bureau_overdue_ratio" in names
    assert "on_time_payment_ratio" in names
    assert "payment_coverage_ratio" in names
    assert "insurance_payment_consistency" in names

    client.post("/features/build", headers=headers)
    stored = {row["feature_name"]: row["value_num"] for row in client.get("/features", headers=headers).json()}
    assert stored["bureau_debt_amount"] == 0.0
    assert stored["fd_amount"] == 0.0
    assert stored["health_insurance"] == 0


def test_unreviewed_extraction_blocks_features(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "unrev@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    client.put("/profile", json=COMPLETE_PROFILE, headers=headers)
    client.post(
        "/documents/upload",
        files={"file": ("stmt.pdf", _pdf_bytes(["x"]), "application/pdf")},
        data={"document_type": "bank_statement"},
        headers=headers,
    )

    readiness = client.get("/features/readiness", headers=headers).json()
    reasons = " ".join(entry["reason"] for entry in readiness["missing"])

    assert "food_expense" in {entry["feature"] for entry in readiness["missing"]}
    assert "unreviewed" in reasons


def test_features_isolated_between_users(test_client) -> None:
    client, _ = test_client
    headers = _full_user(client, "full7@example.com")
    client.post("/features/build", headers=headers)
    other = register_user(client, "other7@example.com", "Secret123!")

    assert client.get("/features", headers=auth_headers(other["access_token"])).json() == []
    assert client.post("/features/build", headers=auth_headers(other["access_token"])).json()["available"] < 98

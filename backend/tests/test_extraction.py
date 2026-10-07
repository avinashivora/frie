"""Document extraction tests with synthetic in-memory fixtures only.

Text PDFs are generated with PyMuPDF; no real financial documents are used.
Image OCR has no engine in this environment, so image tests assert the
honest failure path (no values invented).
"""

from __future__ import annotations

import io

import pytest

from app.db.models import Document, Extraction
from tests.conftest import auth_headers, register_user


def _pdf_bytes(lines: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "\n".join(lines), fontsize=11)
        return document.tobytes()
    finally:
        document.close()


def _salary_png_bytes() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    lines = [
        "ACME Private Limited",
        "Employee Name: Priya Test",
        "Gross: Rs. 95000.00",
        "Net Salary: Rs. 78250.00",
    ]
    image = Image.new("RGB", (900, 320), color="white")
    draw = ImageDraw.Draw(image)
    top = 20
    for line in lines:
        draw.text((20, top), line, fill="black", font=font)
        top += 55
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _scanned_pdf_bytes() -> bytes:
    import fitz

    document = fitz.open()
    try:
        page = document.new_page(width=900, height=320)
        page.insert_image(fitz.Rect(0, 0, 900, 320), stream=_salary_png_bytes())
        return document.tobytes()
    finally:
        document.close()


SALARY_LINES = [
    "ACME Private Limited",
    "Employee Name: Priya Test",
    "Employer: ACME Private Limited",
    "Salary Period: June 2025",
    "Basic: Rs. 60000.00",
    "Gross: Rs. 95000.00",
    "Net Salary: Rs. 78250.00",
    "Pay Date: 30/06/2025",
]

BANK_LINES = [
    "Demo Bank Statement",
    "Account No: 123456789012",
    "Statement Period: 01/06/2025 To 30/06/2025",
    "05/06/2025 UPI-SWIGGY 1,250.00 0.00 45,320.50",
    "12/06/2025 SALARY-CREDIT 0.00 95,000.00 139,070.50",
    "20/06/2025 RENT-NEFT 18,000.00 0.00 121,070.50",
]

CREDIT_LINES = [
    "HDFC Bank Credit Report",
    "Lender: HDFC Bank",
    "Account Type: Credit Card",
    "Sanctioned: Rs. 500000.00",
    "Outstanding: Rs. 125000.00",
    "Credit Limit: Rs. 500000.00",
    "Overdue: Rs. 0.00",
    "45 days past due",
    "Status: Active",
    "Application Approved Rs. 300000.00",
]

LOAN_LINES = [
    "Home Loan Sanction Letter",
    "Loan Amount: Rs. 2500000.00",
    "EMI: Rs. 28944.00",
    "Cash loan facility",
    "Dated: 15/01/2024",
]

INSURANCE_LINES = [
    "Life Insurance Policy",
    "Health cover details",
    "Premium: Rs. 12000.00",
    "Frequency: Annual",
    "Status: In-force",
    "Premium paid on 05/03/2025 and 05/03/2024",
]

INVESTMENT_LINES = [
    "Portfolio Statement",
    "Fixed Deposit: Rs. 200000.00",
    "SIP: Rs. 5000.00",
    "Mutual Fund: Rs. 150000.00",
    "PPF: Rs. 50000.00",
    "NPS: Rs. 30000.00",
    "Recurring Deposit: Rs. 10000.00",
]


@pytest.fixture()
def user_with_pdf(test_client, storage_dir):
    client, _ = test_client
    body = register_user(client, "ex1@example.com", "Secret123!")

    def _upload(lines, doc_type="bank_statement", name="doc.pdf"):
        response = client.post(
            "/documents/upload",
            files={"file": (name, _pdf_bytes(lines), "application/pdf")},
            data={"document_type": doc_type},
            headers=auth_headers(body["access_token"]),
        )
        assert response.status_code == 201, response.text
        return response.json()

    return client, auth_headers(body["access_token"]), _upload


def test_salary_extraction_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(SALARY_LINES, doc_type="salary_income_proof", name="salary.pdf")

    response = client.post(f"/documents/{created['id']}/extract", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "EXTRACTED"
    assert body["review_status"] == "REVIEW_REQUIRED"
    assert body["engine"] == "pymupdf-text"
    fields = body["structured_data"]
    assert "Priya Test" in fields["employee_name"]
    assert fields["basic_salary"] == 60000.0
    assert fields["gross_salary"] == 95000.0
    assert fields["net_salary"] == 78250.0
    assert fields["salary_period"] == "June 2025"


def test_bank_transaction_extraction(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(BANK_LINES, doc_type="bank_statement", name="stmt.pdf")

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert fields["account_number"] == "123456789012"
    assert len(fields["transactions"]) == 3
    first = fields["transactions"][0]
    assert first["date"] == "05/06/2025"
    assert first["debit"] == 1250.0
    assert first["credit"] == 0.0
    assert first["balance"] == 45320.5


def test_credit_extraction_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(CREDIT_LINES, doc_type="credit_report", name="credit.pdf")

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert "HDFC Bank" in fields["lender"]
    assert fields["account_type"] == "credit card"
    assert fields["sanctioned_amount"] == 500000.0
    assert fields["outstanding_amount"] == 125000.0
    assert fields["overdue_days"] == 45
    assert fields["account_status"] == "active"
    assert len(fields["application_records"]) >= 1


def test_loan_extraction_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(LOAN_LINES, doc_type="loan_document", name="loan.pdf")

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert fields["loan_amount"] == 2500000.0
    assert fields["emi"] == 28944.0
    assert "cash loan" in fields["contract_info"]


def test_insurance_extraction_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(INSURANCE_LINES, doc_type="insurance_document", name="policy.pdf")

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert fields["policy_type"] in ("health", "life")
    assert fields["premium"] == 12000.0
    assert fields["premium_frequency"] == "annual"
    assert len(fields["payment_dates"]) == 2


def test_investment_extraction_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(INVESTMENT_LINES, doc_type="investment_statement", name="invest.pdf")

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert fields["fd"] == 200000.0
    assert fields["sip"] == 5000.0
    assert fields["mutual_fund"] == 150000.0
    assert fields["ppf"] == 50000.0
    assert fields["nps"] == 30000.0
    assert fields["rd"] == 10000.0


def test_missing_fields_are_omitted_not_fabricated(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    created = upload(
        ["ACME Private Limited", "Employee Name: Priya Test", "Basic: Rs. 60000.00"],
        doc_type="salary_income_proof",
        name="partial.pdf",
    )

    fields = client.post(f"/documents/{created['id']}/extract", headers=headers).json()["structured_data"]

    assert fields["basic_salary"] == 60000.0
    assert "net_salary" not in fields
    assert "gross_salary" not in fields


def test_image_ocr_extracts_salary_fields(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "ex2@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = client.post(
        "/documents/upload",
        files={"file": ("scan.png", _salary_png_bytes(), "image/png")},
        data={"document_type": "salary_income_proof"},
        headers=headers,
    ).json()

    response = client.post(f"/documents/{created['id']}/extract", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "EXTRACTED"
    assert body["review_status"] == "REVIEW_REQUIRED"
    assert body["engine"] == "paddleocr"
    assert body["confidence"] is not None
    assert body["structured_data"]["gross_salary"] == 95000.0
    assert body["structured_data"]["net_salary"] == 78250.0


def test_scanned_pdf_falls_back_to_ocr(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "ex2b@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = client.post(
        "/documents/upload",
        files={"file": ("scan.pdf", _scanned_pdf_bytes(), "application/pdf")},
        data={"document_type": "salary_income_proof"},
        headers=headers,
    ).json()

    response = client.post(f"/documents/{created['id']}/extract", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "EXTRACTED"
    assert body["engine"] == "paddleocr"
    assert body["structured_data"]["gross_salary"] == 95000.0


def test_blank_image_fails_honestly(test_client, storage_dir) -> None:
    from PIL import Image

    client, _ = test_client
    body = register_user(client, "ex2c@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    buffer = io.BytesIO()
    Image.new("RGB", (400, 200), color="white").save(buffer, format="PNG")
    created = client.post(
        "/documents/upload",
        files={"file": ("blank.png", buffer.getvalue(), "image/png")},
        data={"document_type": "bank_statement"},
        headers=headers,
    ).json()

    response = client.post(f"/documents/{created['id']}/extract", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "FAILED"
    assert body["review_status"] == "REVIEW_REQUIRED"
    assert body["structured_data"] == {}


def test_corrupt_pdf_fails_without_values(user_with_pdf) -> None:
    client, headers, upload = user_with_pdf
    response = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", b"%PDF-1.4\n%not-a-real-document", "application/pdf")},
        data={"document_type": "bank_statement"},
        headers=headers,
    )
    assert response.status_code == 201
    created = response.json()

    body = client.post(f"/documents/{created['id']}/extract", headers=headers).json()

    assert body["extraction_status"] == "FAILED"
    assert body["structured_data"] == {}


def test_reprocessing_replaces_without_duplicates(test_client, storage_dir) -> None:
    client, sessions = test_client
    body = register_user(client, "ex3@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = client.post(
        "/documents/upload",
        files={"file": ("salary.pdf", _pdf_bytes(SALARY_LINES), "application/pdf")},
        data={"document_type": "salary_income_proof"},
        headers=headers,
    ).json()

    first = client.post(f"/documents/{created['id']}/extract", headers=headers).json()
    second = client.post(f"/documents/{created['id']}/extract", headers=headers).json()

    assert first["id"] == second["id"]
    assert first["structured_data"] == second["structured_data"]
    with sessions() as db:
        from app.db.models import Extraction

        count = db.query(Extraction).filter(Extraction.document_id == created["id"]).count()
    assert count == 1


def test_extraction_persists_linked_to_document(test_client, storage_dir) -> None:
    client, sessions = test_client
    body = register_user(client, "ex4@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = client.post(
        "/documents/upload",
        files={"file": ("stmt.pdf", _pdf_bytes(BANK_LINES), "application/pdf")},
        data={"document_type": "bank_statement"},
        headers=headers,
    ).json()
    client.post(f"/documents/{created['id']}/extract", headers=headers)

    with sessions() as db:
        from app.db.models import Document, Extraction

        document = db.query(Document).filter(Document.id == created["id"]).first()
        extraction = db.query(Extraction).filter(Extraction.document_id == created["id"]).first()

    assert document.processing_status == "EXTRACTED"
    assert document.extraction_status == "EXTRACTED"
    assert document.review_status == "REVIEW_REQUIRED"
    assert extraction is not None
    assert "transactions" in (extraction.structured_data or "")


def test_extraction_ownership_isolation(test_client, storage_dir) -> None:
    client, _ = test_client
    ada = register_user(client, "ada9@example.com", "Secret123!")
    bob = register_user(client, "bob9@example.com", "Secret123!")
    created = client.post(
        "/documents/upload",
        files={"file": ("stmt.pdf", _pdf_bytes(BANK_LINES), "application/pdf")},
        data={"document_type": "bank_statement"},
        headers=auth_headers(ada["access_token"]),
    ).json()

    assert client.get(f"/documents/{created['id']}/extraction", headers=auth_headers(bob["access_token"])).status_code == 404
    assert client.post(f"/documents/{created['id']}/extract", headers=auth_headers(bob["access_token"])).status_code == 404
    assert client.get(f"/documents/{created['id']}/extraction", headers=auth_headers(ada["access_token"])).status_code == 404

    client.post(f"/documents/{created['id']}/extract", headers=auth_headers(ada["access_token"]))
    own = client.get(f"/documents/{created['id']}/extraction", headers=auth_headers(ada["access_token"]))
    assert own.status_code == 200
    assert own.json()["document_id"] == created["id"]


def test_extraction_response_contains_no_scores(test_client, storage_dir) -> None:
    client, sessions = test_client
    body = register_user(client, "ex5@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = client.post(
        "/documents/upload",
        files={"file": ("salary.pdf", _pdf_bytes(SALARY_LINES), "application/pdf")},
        data={"document_type": "salary_income_proof"},
        headers=headers,
    ).json()

    response = client.post(f"/documents/{created['id']}/extract", headers=headers)

    assert response.status_code == 200
    assert set(response.json().keys()) == {
        "id",
        "document_id",
        "raw_text",
        "structured_data",
        "extraction_status",
        "review_status",
        "engine",
        "confidence",
        "error_message",
        "created_at",
        "updated_at",
    }

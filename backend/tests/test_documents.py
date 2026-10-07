"""Document metadata persistence and ownership tests. No OCR in Phase 2."""

from __future__ import annotations

from tests.conftest import auth_headers, register_user
from app.db.models import Document, Extraction


def test_documents_require_authentication(test_client) -> None:
    client, _ = test_client

    assert client.get("/documents").status_code == 401
    assert (
        client.post(
            "/documents/metadata",
            json={"document_type": "bank_statement", "original_filename": "stmt.pdf"},
        ).status_code
        == 401
    )


def test_document_metadata_create_defaults(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "wade@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    response = client.post(
        "/documents/metadata",
        json={"document_type": "bank_statement", "original_filename": "stmt.pdf"},
        headers=headers,
    )

    assert response.status_code == 201
    created = response.json()
    assert created["document_type"] == "bank_statement"
    assert created["original_filename"] == "stmt.pdf"
    assert created["processing_status"] == "UPLOADED"
    assert created["extraction_status"] == "PENDING"
    assert created["review_status"] == "PENDING"
    assert created["user_id"] == body["user"]["id"]


def test_document_metadata_rejects_unknown_type(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "xena@example.com", "Secret123!")

    response = client.post(
        "/documents/metadata",
        json={"document_type": "passport", "original_filename": "pp.pdf"},
        headers=auth_headers(body["access_token"]),
    )

    assert response.status_code == 422


def test_document_list_is_isolated_between_users(test_client) -> None:
    client, _ = test_client
    yara = register_user(client, "yara@example.com", "Secret123!")
    zane = register_user(client, "zane@example.com", "Secret123!")

    for name in ("a.pdf", "b.pdf"):
        client.post(
            "/documents/metadata",
            json={"document_type": "bank_statement", "original_filename": name},
            headers=auth_headers(yara["access_token"]),
        )
    client.post(
        "/documents/metadata",
        json={"document_type": "salary_income_proof", "original_filename": "c.pdf"},
        headers=auth_headers(zane["access_token"]),
    )

    yara_docs = client.get("/documents", headers=auth_headers(yara["access_token"])).json()
    zane_docs = client.get("/documents", headers=auth_headers(zane["access_token"])).json()

    assert sorted(item["original_filename"] for item in yara_docs) == ["a.pdf", "b.pdf"]
    assert [item["original_filename"] for item in zane_docs] == ["c.pdf"]


def test_document_detail_is_isolated_between_users(test_client) -> None:
    client, _ = test_client
    yara = register_user(client, "yara2@example.com", "Secret123!")
    zane = register_user(client, "zane2@example.com", "Secret123!")

    created = client.post(
        "/documents/metadata",
        json={"document_type": "credit_report", "original_filename": "report.pdf"},
        headers=auth_headers(yara["access_token"]),
    ).json()

    own = client.get(f"/documents/{created['id']}", headers=auth_headers(yara["access_token"]))
    assert own.status_code == 200
    assert own.json()["original_filename"] == "report.pdf"

    foreign = client.get(f"/documents/{created['id']}", headers=auth_headers(zane["access_token"]))
    assert foreign.status_code == 404

    missing = client.get("/documents/999999", headers=auth_headers(yara["access_token"]))
    assert missing.status_code == 404


def test_document_delete_is_owner_only_and_removes_record(test_client) -> None:
    client, sessions = test_client
    owner = register_user(client, "delete-owner@example.com", "Secret123!")
    other = register_user(client, "delete-other@example.com", "Secret123!")
    headers = auth_headers(owner["access_token"])
    created = client.post("/documents/metadata", json={"document_type":"bank_statement", "original_filename":"bank.pdf"}, headers=headers).json()

    assert client.delete(f"/documents/{created['id']}", headers=auth_headers(other["access_token"])).status_code == 404
    assert client.delete(f"/documents/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/documents/{created['id']}", headers=headers).status_code == 404
    with sessions() as db:
        assert db.query(Document).filter(Document.id == created["id"]).first() is None
        assert db.query(Extraction).filter(Extraction.document_id == created["id"]).first() is None


def test_manual_extraction_edit_requires_review_and_preserves_original(test_client) -> None:
    client, sessions = test_client
    account = register_user(client, "field-edit@example.com", "Secret123!")
    headers = auth_headers(account["access_token"])
    created = client.post("/documents/metadata", json={"document_type":"salary_income_proof", "original_filename":"salary.pdf"}, headers=headers).json()
    with sessions() as db:
        doc = db.query(Document).filter(Document.id == created["id"]).one()
        db.add(Extraction(document_id=doc.id, structured_data='{"gross_salary":95000.0,"net_salary":78000.0}', extraction_status="EXTRACTED", review_status="REVIEWED", engine="test"))
        db.commit()

    response = client.patch(f"/documents/{created['id']}/extraction", json={"gross_salary": 91000}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["structured_data"]["gross_salary"] == 91000
    assert body["structured_data"]["__original_values__"]["gross_salary"] == 95000
    assert body["structured_data"]["__field_provenance__"]["gross_salary"] == "USER_EDITED"
    assert body["review_status"] == "REVIEW_REQUIRED"
    assert client.patch(f"/documents/{created['id']}/extraction", json={"unreviewed_model_feature": 10}, headers=headers).status_code == 422


def test_bank_transaction_edit_updates_provenance_and_requires_review(test_client) -> None:
    client, sessions = test_client
    account = register_user(client, "bank-edit@example.com", "Secret123!")
    headers = auth_headers(account["access_token"])
    created = client.post(
        "/documents/metadata",
        json={"document_type": "bank_statement", "original_filename": "bank.csv"},
        headers=headers,
    ).json()
    with sessions() as db:
        doc = db.query(Document).filter(Document.id == created["id"]).one()
        doc.document_type = "bank_import"
        db.add(Extraction(
            document_id=doc.id,
            structured_data='{"imported_transactions":[{"date":"2024-01-05","description":"SALARY","transaction_type":"credit","credit_amount":95000,"debit_amount":0,"category":"salary_income"}]}',
            extraction_status="EXTRACTED", review_status="REVIEWED", engine="bank_import",
        ))
        db.commit()

    response = client.patch(
        f"/documents/{created['id']}/transactions",
        json={"operation": "edit", "index": 0, "transaction": {"credit_amount": 91000, "category": "salary_income"}},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "REVIEW_REQUIRED"
    with sessions() as db:
        extraction = db.query(Extraction).filter(Extraction.document_id == created["id"]).one()
        import json
        fields = json.loads(extraction.structured_data)
        assert fields["imported_transactions"][0]["credit_amount"] == 91000
        assert fields["__field_provenance__"]["imported_transactions"] == "USER_EDITED"

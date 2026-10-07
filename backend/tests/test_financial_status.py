"""Availability declarations, review actions, and NONE-vs-UNKNOWN semantics."""

from __future__ import annotations

from tests.conftest import auth_headers, register_user


def _pdf(client, headers, lines, doc_type="bank_statement", name="doc.pdf"):
    import fitz

    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "\n".join(lines), fontsize=11)
        payload = document.tobytes()
    finally:
        document.close()
    response = client.post(
        "/documents/upload",
        files={"file": (name, payload, "application/pdf")},
        data={"document_type": doc_type},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_financial_status_roundtrip(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "fs1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.get("/profile/financial-status", headers=headers).status_code == 404
    saved = client.put(
        "/profile/financial-status",
        json={"has_loan": "no", "insurance_status": "none", "inv_fd": "unknown"},
        headers=headers,
    )
    assert saved.status_code == 200
    fetched = client.get("/profile/financial-status", headers=headers).json()
    assert fetched["has_loan"] == "no"
    assert fetched["insurance_status"] == "none"
    assert fetched["inv_fd"] == "unknown"
    assert fetched["inv_sip"] is None


def test_financial_status_rejects_unknown_values(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "fs2@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    assert client.put("/profile/financial-status", json={"has_loan": "maybe"}, headers=headers).status_code == 422
    assert client.put("/profile/financial-status", json={"insurance_status": "full"}, headers=headers).status_code == 422


def test_financial_status_requires_authentication(test_client) -> None:
    client, _ = test_client

    assert client.get("/profile/financial-status").status_code == 401
    assert client.put("/profile/financial-status", json={"has_loan": "no"}).status_code == 401


def test_financial_status_isolated_between_users(test_client) -> None:
    client, _ = test_client
    ada = register_user(client, "fsada@example.com", "Secret123!")
    bob = register_user(client, "fsbob@example.com", "Secret123!")

    client.put("/profile/financial-status", json={"has_loan": "yes"}, headers=auth_headers(ada["access_token"]))

    assert client.get("/profile/financial-status", headers=auth_headers(bob["access_token"])).status_code == 404


def test_review_accept_requires_extracted_output(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "rv1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _pdf(client, headers, ["Hello"], doc_type="bank_statement")
    extracted = client.post(f"/documents/{created['id']}/extract", headers=headers)
    assert extracted.json()["extraction_status"] == "EXTRACTED"

    response = client.post(f"/documents/{created['id']}/review", json={"decision": "accept"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["review_status"] == "REVIEWED"


def test_review_accept_rejected_for_failed_extraction(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "rv2@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    import fitz

    document = fitz.open()
    try:
        document.new_page()
        payload = document.tobytes()
    finally:
        document.close()
    created = client.post(
        "/documents/upload",
        files={"file": ("blank.pdf", payload, "application/pdf")},
        data={"document_type": "bank_statement"},
        headers=headers,
    ).json()
    extracted = client.post(f"/documents/{created['id']}/extract", headers=headers).json()
    assert extracted["extraction_status"] == "FAILED"

    response = client.post(f"/documents/{created['id']}/review", json={"decision": "accept"}, headers=headers)

    assert response.status_code == 422


def test_review_flag_and_unknown_decision(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "rv3@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _pdf(client, headers, ["Hello"], doc_type="bank_statement")
    client.post(f"/documents/{created['id']}/extract", headers=headers)

    flagged = client.post(f"/documents/{created['id']}/review", json={"decision": "flag"}, headers=headers)
    assert flagged.status_code == 200
    assert flagged.json()["review_status"] == "REVIEW_REQUIRED"

    bad = client.post(f"/documents/{created['id']}/review", json={"decision": "maybe"}, headers=headers)
    assert bad.status_code == 422


def test_reviewed_document_serializes_in_list(test_client) -> None:
    client, _ = test_client
    body = register_user(client, "rv4@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _pdf(client, headers, ["Hello"], doc_type="bank_statement")
    client.post(f"/documents/{created['id']}/extract", headers=headers)
    client.post(f"/documents/{created['id']}/review", json={"decision": "accept"}, headers=headers)

    listed = client.get("/documents", headers=headers)

    assert listed.status_code == 200
    assert listed.json()[0]["review_status"] == "REVIEWED"


def test_review_other_users_document_is_hidden(test_client) -> None:
    client, _ = test_client
    ada = register_user(client, "rvada@example.com", "Secret123!")
    bob = register_user(client, "rvbob@example.com", "Secret123!")
    created = _pdf(client, auth_headers(ada["access_token"]), ["Hello"])

    assert (
        client.post(
            f"/documents/{created['id']}/review", json={"decision": "accept"}, headers=auth_headers(bob["access_token"])
        ).status_code
        == 404
    )

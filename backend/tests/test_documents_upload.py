"""Document upload, storage, retrieval, and cleanup tests with synthetic files only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import document_service
from tests.conftest import auth_headers, register_user

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture()
def storage_dir(tmp_path, monkeypatch) -> Path:
    """Redirect file storage to a temporary directory for one test."""

    target = tmp_path / "uploads"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRIE_STORAGE_DIR", str(target))
    return target


def _upload(client, headers, filename="stmt.pdf", content=PDF_BYTES, mime="application/pdf", doc_type="bank_statement"):
    return client.post(
        "/documents/upload",
        files={"file": (filename, content, mime)},
        data={"document_type": doc_type},
        headers=headers,
    )


def test_valid_pdf_upload_stores_file_and_metadata(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up1@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    response = _upload(client, headers)

    assert response.status_code == 201
    created = response.json()
    assert created["document_type"] == "bank_statement"
    assert created["original_filename"] == "stmt.pdf"
    assert created["processing_status"] == "UPLOADED"
    assert created["extraction_status"] == "PENDING"
    assert created["review_status"] == "PENDING"
    assert created["user_id"] == body["user"]["id"]

    reference = created["storage_reference"]
    assert reference != "stmt.pdf"
    assert ".." not in reference and "/" not in reference and "\\" not in reference
    assert reference.endswith(".pdf")
    stored = storage_dir / reference
    assert stored.is_file()
    assert stored.read_bytes() == PDF_BYTES


def test_valid_png_and_jpeg_uploads(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up2@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    png = _upload(client, headers, filename="scan.png", content=PNG_BYTES, mime="image/png")
    jpg = _upload(client, headers, filename="scan.JPG", content=JPEG_BYTES, mime="image/jpeg")

    assert png.status_code == 201
    assert jpg.status_code == 201
    assert png.json()["storage_reference"].endswith(".png")
    assert jpg.json()["storage_reference"].endswith(".jpg")


def test_unsupported_extension_is_rejected(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up3@example.com", "Secret123!")

    response = _upload(
        client, auth_headers(body["access_token"]),
        filename="run.exe", content=b"MZ" + b"\x00" * 32, mime="application/octet-stream",
    )

    assert response.status_code == 415
    assert list(storage_dir.iterdir()) == []


def test_mismatched_content_is_rejected(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up4@example.com", "Secret123!")

    response = _upload(
        client, auth_headers(body["access_token"]),
        filename="fake.pdf", content=b"hello, not a pdf", mime="application/pdf",
    )

    assert response.status_code == 415
    assert list(storage_dir.iterdir()) == []


def test_empty_file_is_rejected(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up5@example.com", "Secret123!")

    response = _upload(client, auth_headers(body["access_token"]), content=b"")

    assert response.status_code == 422
    assert list(storage_dir.iterdir()) == []


def test_oversized_file_is_rejected(test_client, storage_dir, monkeypatch) -> None:
    client, _ = test_client
    monkeypatch.setenv("FRIE_MAX_UPLOAD_MB", "1")
    body = register_user(client, "up6@example.com", "Secret123!")

    response = _upload(
        client, auth_headers(body["access_token"]), content=b"a" * (1024 * 1024 + 10)
    )

    assert response.status_code == 413
    assert list(storage_dir.iterdir()) == []


def test_upload_requires_type_and_file(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up7@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    no_type = client.post(
        "/documents/upload",
        files={"file": ("stmt.pdf", PDF_BYTES, "application/pdf")},
        headers=headers,
    )
    no_file = client.post(
        "/documents/upload", data={"document_type": "bank_statement"}, headers=headers
    )

    assert no_type.status_code == 422
    assert no_file.status_code == 422
    assert list(storage_dir.iterdir()) == []


def test_upload_unknown_document_type_is_rejected(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up8@example.com", "Secret123!")

    response = _upload(client, auth_headers(body["access_token"]), doc_type="passport")

    assert response.status_code == 422
    assert list(storage_dir.iterdir()) == []


def test_upload_requires_authentication(test_client, storage_dir) -> None:
    client, _ = test_client

    response = _upload(client, {})

    assert response.status_code == 401
    assert list(storage_dir.iterdir()) == []


def test_upload_is_isolated_between_users(test_client, storage_dir) -> None:
    client, _ = test_client
    ada = register_user(client, "ada@example.com", "Secret123!")
    bob = register_user(client, "bob2@example.com", "Secret123!")

    _upload(client, auth_headers(ada["access_token"]))

    assert len(client.get("/documents", headers=auth_headers(ada["access_token"])).json()) == 1
    assert client.get("/documents", headers=auth_headers(bob["access_token"])).json() == []


def test_file_download_returns_bytes_with_safe_headers(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up9@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])
    created = _upload(client, headers).json()

    response = client.get(f"/documents/{created['id']}/file", headers=headers)

    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "backend" not in response.headers["content-disposition"]
    assert f"document-{created['id']}.pdf" in response.headers["content-disposition"]


def test_file_download_is_isolated_between_users(test_client, storage_dir) -> None:
    client, _ = test_client
    ada = register_user(client, "ada2@example.com", "Secret123!")
    bob = register_user(client, "bob3@example.com", "Secret123!")
    created = _upload(client, auth_headers(ada["access_token"])).json()

    assert (
        client.get(f"/documents/{created['id']}/file", headers=auth_headers(bob["access_token"])).status_code
        == 404
    )
    assert client.get("/documents/999999/file", headers=auth_headers(ada["access_token"])).status_code == 404


def test_failed_db_insert_removes_orphan_file(test_client, storage_dir, monkeypatch) -> None:
    client, _ = test_client
    body = register_user(client, "up10@example.com", "Secret123!")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(document_service, "create_document_metadata", _boom)
    response = _upload(client, auth_headers(body["access_token"]))

    assert response.status_code == 500
    assert list(storage_dir.iterdir()) == []


def test_all_supported_types_accept_uploads(test_client, storage_dir) -> None:
    client, _ = test_client
    body = register_user(client, "up11@example.com", "Secret123!")
    headers = auth_headers(body["access_token"])

    for doc_type in (
        "salary_income_proof",
        "bank_statement",
        "credit_report",
        "loan_document",
        "insurance_document",
        "investment_statement",
    ):
        response = _upload(client, headers, doc_type=doc_type)
        assert response.status_code == 201, doc_type

    listed = client.get("/documents", headers=headers).json()
    assert sorted(item["document_type"] for item in listed) == sorted(
        [
            "salary_income_proof",
            "bank_statement",
            "credit_report",
            "loan_document",
            "insurance_document",
            "investment_statement",
        ]
    )


def test_default_storage_is_dedicated_and_git_ignored() -> None:
    from app.core.config import get_settings

    root = get_settings().storage_dir
    assert root.name == "documents"
    assert root.parent.name == "storage"
    assert "app" not in root.parts
    gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text()
    assert "storage/" in gitignore

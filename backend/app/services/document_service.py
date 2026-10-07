"""Document metadata persistence. Metadata only; no OCR or extraction here."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DOCUMENT_TYPES, Document, User


class UnknownDocumentTypeError(ValueError):
    """Raised when the document type is outside the supported set."""


def require_known_type(document_type: str) -> str:
    """Validate a document type, shared by metadata and upload routes."""

    if document_type not in DOCUMENT_TYPES:
        raise UnknownDocumentTypeError(f"Unsupported document type: {document_type}.")
    return document_type


def create_document_metadata(
    db: Session,
    *,
    user: User,
    document_type: str,
    original_filename: str,
    storage_reference: str | None = None,
    source_type: str = "manual_upload",
) -> Document:
    """Record an uploaded document's metadata with initial plain statuses."""

    require_known_type(document_type)
    document = Document(
        user_id=user.id,
        document_type=document_type,
        original_filename=original_filename,
        storage_reference=storage_reference,
        source_type=source_type,
        processing_status="UPLOADED",
        extraction_status="PENDING",
        review_status="PENDING",
    )
    db.add(document)
    db.flush()
    return document


def list_documents(db: Session, *, user: User) -> list[Document]:
    """Return only the authenticated user's documents, newest first."""

    return (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.id.desc())
        .all()
    )


def get_document(db: Session, *, user: User, document_id: int) -> Document | None:
    """Return one of the authenticated user's documents, else None."""

    return (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.id == document_id)
        .first()
    )


class ReviewNotAllowedError(ValueError):
    """Raised when a review decision cannot be applied."""


def review_document(db: Session, *, user: User, document_id: int, decision: str):
    """Apply a human review decision. Accept requires extracted output."""

    from app.db.models import Extraction

    document = get_document(db, user=user, document_id=document_id)
    if document is None:
        return None
    extraction = (
        db.query(Extraction).filter(Extraction.document_id == document.id).first()
    )
    if extraction is None:
        raise ReviewNotAllowedError("There is no extraction to review yet.")
    if decision == "accept":
        if extraction.extraction_status != "EXTRACTED":
            raise ReviewNotAllowedError(
                "Only successfully extracted output can be accepted."
            )
        extraction.review_status = "REVIEWED"
        document.review_status = "REVIEWED"
    elif decision == "flag":
        extraction.review_status = "REVIEW_REQUIRED"
        document.review_status = "REVIEW_REQUIRED"
    else:
        raise ReviewNotAllowedError("Unknown review decision.")
    db.flush()
    return extraction

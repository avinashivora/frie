"""Document metadata schemas. No file content or extraction results travel here in Phase 2."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal[
    "salary_income_proof",
    "bank_statement",
    "credit_report",
    "loan_document",
    "insurance_document",
    "investment_statement",
]

ProcessingStatus = Literal["UPLOADED", "PROCESSING", "EXTRACTED", "FAILED"]
ExtractionStatus = Literal["PENDING", "EXTRACTED", "FAILED"]
ReviewStatus = Literal["PENDING", "REVIEW_REQUIRED", "REVIEWED", "APPROVED", "FAILED"]


class DocumentCreate(BaseModel):
    """Metadata for an uploaded document. The file itself arrives in Phase 4."""

    document_type: DocumentType
    original_filename: str = Field(min_length=1, max_length=255)
    storage_reference: Optional[str] = Field(default=None, max_length=1024)
    source_type: str = Field(default="manual_upload", min_length=1, max_length=64)


class DocumentRead(BaseModel):
    """Stored document metadata with processing statuses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    document_type: str
    original_filename: str
    storage_reference: Optional[str]
    uploaded_at: datetime
    processing_status: ProcessingStatus
    extraction_status: ExtractionStatus
    source_type: str
    review_status: ReviewStatus
    created_at: datetime
    updated_at: datetime

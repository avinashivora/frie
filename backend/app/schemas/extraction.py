"""Extraction read schema. Raw information only; never model features or scores."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict

ExtractionStatus = Literal["PENDING", "PROCESSING", "EXTRACTED", "FAILED"]
ReviewStatus = Literal["PENDING", "REVIEW_REQUIRED", "REVIEWED", "APPROVED", "FAILED"]


class ExtractionRead(BaseModel):
    """One document's raw extraction output for review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    raw_text: str
    structured_data: Dict[str, Any]
    extraction_status: ExtractionStatus
    review_status: ReviewStatus
    engine: str
    confidence: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

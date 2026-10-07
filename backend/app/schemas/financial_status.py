"""Availability declaration schemas. Declarations describe knowledge state, never values."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

YesNoUnknown = Literal["yes", "no", "unknown"]
InsuranceStatus = Literal["health", "life", "both", "none", "unknown"]
ReviewDecision = Literal["accept", "flag"]


class FinancialStatusUpdate(BaseModel):
    """Partial availability declaration. Absent fields are left unchanged."""

    has_loan: Optional[YesNoUnknown] = None
    insurance_status: Optional[InsuranceStatus] = None
    inv_fd: Optional[YesNoUnknown] = None
    inv_rd: Optional[YesNoUnknown] = None
    inv_sip: Optional[YesNoUnknown] = None
    inv_mutual_fund: Optional[YesNoUnknown] = None
    inv_ppf: Optional[YesNoUnknown] = None
    inv_nps: Optional[YesNoUnknown] = None


class FinancialStatusRead(FinancialStatusUpdate):
    """Stored availability declaration with identity and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class ReviewRequest(BaseModel):
    """Human review decision on an extraction. Accept requires extracted output."""

    decision: ReviewDecision

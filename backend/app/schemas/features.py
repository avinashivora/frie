"""Feature inspection schemas. Read-only views over stored engineering output."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict


class FeatureRead(BaseModel):
    """One stored feature value with provenance."""

    model_config = ConfigDict(from_attributes=True)

    feature_name: str
    feature_type: str
    value_num: Optional[float]
    value_text: Optional[str]
    provenance: str
    status: str
    confidence: Optional[float]
    source_document_id: Optional[int]


class MissingFeature(BaseModel):
    """One unavailable feature with its reason and data block."""

    feature: str
    reason: str
    block: str


class ReadinessRead(BaseModel):
    """Deterministic readiness from a fresh assembly (nothing persisted)."""

    total_required: int
    available: int
    missing: list[MissingFeature]
    status: Literal["READY", "PARTIALLY_READY", "NOT_READY"]
    by_provenance: dict[str, int]
    by_status: dict[str, int]
    group_completeness: dict[str, dict[str, Any]]


class BuildSummary(BaseModel):
    """Result of an idempotent feature build."""

    total_required: int
    available: int
    stored: int
    missing: list[MissingFeature]
    status: str
    by_provenance: dict[str, int]

    model_config = ConfigDict(extra="ignore")


class GroupCompleteness(BaseModel):
    available: int
    total: int
    percentage: float


class CompletenessRead(BaseModel):
    """Real-world completeness report with feature group breakdown."""

    total_required: int
    available: int
    status: str
    by_provenance: dict[str, int]
    by_status: dict[str, int]
    group_completeness: dict[str, GroupCompleteness]

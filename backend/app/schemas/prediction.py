"""Strict API schemas for source-normalized FRIE customer feature data and scores."""

from __future__ import annotations

from math import isfinite
from typing import Annotated, Any, Literal, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictStr,
    create_model,
)

from app.core.feature_contract import get_feature_contract

FEATURE_CONTRACT = get_feature_contract()


def _strict_finite_number(value: Any) -> float:
    """Accept numeric JSON values only; strings, nulls, booleans, and infinities are rejected."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a numeric JSON value")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError("must be finite")
    return numeric_value


def _optional_finite_number(value: Any) -> Optional[float]:
    """Accept numeric JSON values or null; strings, booleans, and infinities are rejected."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a numeric JSON value or null")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError("must be finite")
    return numeric_value


StrictFiniteNumber = Annotated[float, BeforeValidator(_strict_finite_number)]
OptionalFiniteNumber = Annotated[
    Optional[float], BeforeValidator(_optional_finite_number)
]

_feature_fields = {
    **{
        name: (StrictFiniteNumber, Field(...))
        for name in FEATURE_CONTRACT.numeric_features
    },
    **{
        name: (StrictStr, Field(..., min_length=1))
        for name in FEATURE_CONTRACT.categorical_features
    },
}

_partial_feature_fields = {
    **{
        name: (OptionalFiniteNumber, Field(default=None))
        for name in FEATURE_CONTRACT.numeric_features
    },
    **{
        name: (Optional[StrictStr], Field(default=None))
        for name in FEATURE_CONTRACT.categorical_features
    },
}

CustomerFeatureData = create_model(
    "CustomerFeatureData",
    __config__=ConfigDict(extra="forbid"),
    **_feature_fields,
)

PartialCustomerFeatureData = create_model(
    "PartialCustomerFeatureData",
    __config__=ConfigDict(extra="forbid"),
    **_partial_feature_fields,
)


class PredictionRequest(BaseModel):
    """A complete, source-normalized customer feature record for prototype scoring."""

    model_config = ConfigDict(extra="forbid")
    features: CustomerFeatureData = Field(  # type: ignore
        description=(
            "All 98 source-normalized customer features required by the saved FRIE pipeline. "
            "No missing values, defaults, or inferred financial facts are accepted by this API."
        )
    )


class DimensionResponse(BaseModel):
    score: float
    max_score: float = 100.0
    coverage: float
    status: Literal[
        "AVAILABLE",
        "LIMITED",
        "NOT_ESTABLISHED",
        "UNAVAILABLE",
    ]
    confidence: float
    indicators: dict[str, Any] = {}
    effective_weights: dict[str, float] = {}


class ProfileResponse(BaseModel):
    profile: Literal["neutral", "loan", "insurance"]
    score: float
    max_score: float = 100.0
    coverage: float
    confidence: float
    configured_weights: dict[str, float]
    effective_weights: dict[str, float]


class PredictionResponse(BaseModel):
    algorithm_version: str

    frie_score: float
    max_score: float = 600.0

    dimensions: dict[str, DimensionResponse]

    profile: ProfileResponse | None = None


class PartialPredictionRequest(BaseModel):
    """Incomplete customer feature record for prototype scoring with partial data."""

    model_config = ConfigDict(extra="forbid")
    features: PartialCustomerFeatureData = Field(  # type: ignore
        description=(
            "Available customer feature data for the internal available-data endpoint. "
            "Missing values are handled by the existing V2 pipeline preprocessors."
        )
    )


class PartialPredictionResponse(BaseModel):
    """The score output from the FRIE prototype pipeline with partial data."""

    frie_score: float = Field(description="Prototype FRIE score, rounded for display.")
    reliability_level: Literal["Poor", "Average", "Good", "Excellent"] = Field(
        description="Prototype calibration category; not a regulatory or universal threshold."
    )
    data_coverage: float = Field(
        description="Fraction of 98 features that were provided."
    )
    available_features: int = Field(description="Number of features provided.")
    total_features: int = Field(description="Total required features (98).")
    missing_groups: list[str] = Field(
        description="Document groups with missing features."
    )
    model_used: str = Field(
        description="Model used: 'full', 'full_imputed', 'missing_aware', or 'none'."
    )
    warning: Optional[str] = Field(
        default=None, description="Warning about data quality or imputation."
    )

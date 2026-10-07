"""Customer profile schemas. Raw user inputs only; no feature computation.

Categorical levels below mirror the fitted V2 encoder categories exactly
(verified by test_profile_levels_match_encoder_categories). Unknown levels
are rejected with 422 rather than silently mapped or ignored.
"""

from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

CATEGORICAL_LEVELS: dict[str, tuple[str, ...]] = {
    "gender": ("F", "M"),
    "family_status": (
        "Civil marriage",
        "Married",
        "Separated",
        "Single / not married",
        "Widow",
    ),
    "education_level": (
        "Higher education",
        "Incomplete higher",
        "Lower secondary",
        "Secondary / secondary special",
    ),
    "housing_type": (
        "Co-op apartment",
        "House / apartment",
        "Municipal apartment",
        "Office apartment",
        "Rented apartment",
        "With parents",
    ),
    "owns_car": ("N", "Y"),
    "owns_property": ("N", "Y"),
    "income_type": ("Commercial associate", "Pensioner", "State servant", "Working"),
    "occupation": (
        "Accountants",
        "Cleaning staff",
        "Cooking staff",
        "Core staff",
        "Drivers",
        "HR staff",
        "High skill tech staff",
        "IT staff",
        "Laborers",
        "Low-skill Laborers",
        "Managers",
        "Medicine staff",
        "Private service staff",
        "Realty agents",
        "Sales staff",
        "Secretaries",
        "Security staff",
        "Waiters/barmen staff",
    ),
    "organization_type": (
        "Advertising",
        "Agriculture",
        "Bank",
        "Business Entity Type 1",
        "Business Entity Type 2",
        "Business Entity Type 3",
        "Cleaning",
        "Construction",
        "Electricity",
        "Emergency",
        "Government",
        "Hotel",
        "Housing",
        "Industry: type 1",
        "Industry: type 10",
        "Industry: type 11",
        "Industry: type 12",
        "Industry: type 2",
        "Industry: type 3",
        "Industry: type 5",
        "Industry: type 7",
        "Industry: type 9",
        "Insurance",
        "Kindergarten",
        "Legal Services",
        "Medicine",
        "Military",
        "Mobile",
        "Other",
        "Police",
        "Postal",
        "Realtor",
        "Restaurant",
        "School",
        "Security",
        "Security Ministries",
        "Self-employed",
        "Services",
        "Telecom",
        "Trade: type 1",
        "Trade: type 2",
        "Trade: type 3",
        "Trade: type 7",
        "Transport: type 1",
        "Transport: type 2",
        "Transport: type 3",
        "Transport: type 4",
        "University",
        "XNA",
    ),
    "contract_type": ("Cash loans", "Revolving loans"),
}

MAX_HUMAN_AGE_YEARS = 120


def _check_level(field_name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if value not in CATEGORICAL_LEVELS[field_name]:
        raise ValueError(f"must be one of the supported {field_name} values")
    return value


class ProfileUpdate(BaseModel):
    """Partial profile write. Every field is optional; absent fields are left unchanged."""

    gender: Optional[str] = Field(default=None, min_length=1, max_length=32)
    date_of_birth: Optional[date] = None
    children_count: Optional[int] = Field(default=None, ge=0, le=30)
    family_size: Optional[int] = Field(default=None, ge=1, le=30)
    family_status: Optional[str] = Field(default=None, min_length=1, max_length=64)
    education_level: Optional[str] = Field(default=None, min_length=1, max_length=64)
    housing_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    owns_car: Optional[str] = Field(default=None, min_length=1, max_length=8)
    owns_property: Optional[str] = Field(default=None, min_length=1, max_length=8)
    income_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    occupation: Optional[str] = Field(default=None, min_length=1, max_length=64)
    organization_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    contract_type: Optional[str] = Field(default=None, min_length=1, max_length=32)
    city: Optional[str] = Field(default=None, min_length=1, max_length=128)
    monthly_income: Optional[float] = Field(default=None, gt=0)
    employment_start: Optional[date] = None

    @field_validator(
        "gender",
        "family_status",
        "education_level",
        "housing_type",
        "owns_car",
        "owns_property",
        "income_type",
        "occupation",
        "organization_type",
        "contract_type",
    )
    @classmethod
    def check_known_level(cls, value: str | None, info) -> str | None:
        return _check_level(info.field_name, value)

    @field_validator("monthly_income")
    @classmethod
    def check_finite_income(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("must be a finite number")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def check_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        today = date.today()
        if value > today:
            raise ValueError("must not be in the future")
        age_days = (today - value).days
        if age_days > MAX_HUMAN_AGE_YEARS * 365.25:
            raise ValueError("implies an unreasonable age")
        return value

    @field_validator("employment_start")
    @classmethod
    def check_employment_start(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("must not be in the future")
        return value


class ProfileRead(ProfileUpdate):
    """Stored profile with identity and timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class MissingFeature(BaseModel):
    """One user feature still needed for a complete profile."""

    feature: str
    label: str


class CompletenessRead(BaseModel):
    """Deterministic profile completeness against the 18 user features."""

    completed: int
    required: int
    percentage: float
    missing: list[MissingFeature]


class ReadinessRead(BaseModel):
    """Profile readiness vs scoring readiness. Scoring stays false in Phase 3."""

    profile_status: str
    profile_ready: bool
    frie_scoring_ready: bool


class ProfileEnvelope(BaseModel):
    """Profile plus its completeness and readiness metadata."""

    profile: ProfileRead | None
    completeness: CompletenessRead
    readiness: ReadinessRead

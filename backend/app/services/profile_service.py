"""Customer profile persistence. Stores raw user inputs only; no feature engineering."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CustomerProfile, User
from app.schemas.profile import MAX_HUMAN_AGE_YEARS

PROFILE_FIELDS = (
    "gender",
    "date_of_birth",
    "children_count",
    "family_size",
    "family_status",
    "education_level",
    "housing_type",
    "owns_car",
    "owns_property",
    "income_type",
    "occupation",
    "organization_type",
    "contract_type",
    "city",
    "monthly_income",
    "employment_start",
)


def get_profile(db: Session, *, user: User) -> CustomerProfile | None:
    """Return the authenticated user's profile, or None when never saved."""

    return db.query(CustomerProfile).filter(CustomerProfile.user_id == user.id).first()


def upsert_profile(db: Session, *, user: User, values: dict[str, Any]) -> CustomerProfile:
    """Create or update the authenticated user's profile from raw inputs."""

    profile = get_profile(db, user=user)
    if profile is None:
        profile = CustomerProfile(user_id=user.id)
        db.add(profile)
    for name in PROFILE_FIELDS:
        if name in values:
            setattr(profile, name, values[name])
    db.flush()
    return profile


# Each entry maps one Phase 1.5 USER feature to the raw profile field that
# satisfies it, with the label shown in completeness reporting.
COMPLETENESS_REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("gender", "Gender", "gender"),
    ("age_years", "Age (from date of birth)", "date_of_birth"),
    ("children_count", "Children", "children_count"),
    ("family_size", "Family size", "family_size"),
    ("family_status", "Family status", "family_status"),
    ("education_level", "Education", "education_level"),
    ("housing_type", "Housing", "housing_type"),
    ("owns_car", "Car ownership", "owns_car"),
    ("owns_property", "Property ownership", "owns_property"),
    ("income_type", "Income type", "income_type"),
    ("occupation", "Occupation", "occupation"),
    ("organization_type", "Organization type", "organization_type"),
    ("contract_type", "Contract type", "contract_type"),
    ("city_tier", "City tier (from city)", "city"),
    ("occupation_band", "Occupation band (from occupation)", "occupation"),
    ("indian_household_size", "Household size (from family size)", "family_size"),
    ("monthly_income", "Monthly income", "monthly_income"),
    ("employment_years", "Employment years (from start date)", "employment_start"),
)

REQUIRED_COMPLETENESS_COUNT = len(COMPLETENESS_REQUIREMENTS)


def _raw_value(profile: CustomerProfile | None, field_name: str) -> Any:
    if profile is None:
        return None
    return getattr(profile, field_name, None)


def _satisfied(profile: CustomerProfile | None, feature: str, field_name: str) -> bool:
    value = _raw_value(profile, field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        if feature == "monthly_income":
            return isfinite(float(value)) and float(value) > 0
        return isfinite(float(value))
    if isinstance(value, date):
        today = date.today()
        if value > today:
            return False
        if feature == "age_years":
            return (today - value).days <= MAX_HUMAN_AGE_YEARS * 365.25
        return True
    return False


def compute_completeness(profile: CustomerProfile | None) -> dict[str, Any]:
    """Deterministic completeness over the 18 Phase 1.5 USER features."""

    missing = [
        {"feature": feature, "label": label}
        for feature, label, field_name in COMPLETENESS_REQUIREMENTS
        if not _satisfied(profile, feature, field_name)
    ]
    completed = REQUIRED_COMPLETENESS_COUNT - len(missing)
    return {
        "completed": completed,
        "required": REQUIRED_COMPLETENESS_COUNT,
        "percentage": round(100.0 * completed / REQUIRED_COMPLETENESS_COUNT, 1),
        "missing": missing,
    }


def profile_readiness(profile: CustomerProfile | None) -> dict[str, Any]:
    """Profile readiness only. FRIE scoring readiness stays False in Phase 3.

    A complete profile never implies scoring readiness because the 64
    document features and 16 derived features are still unavailable.
    """

    completed = compute_completeness(profile)["completed"]
    if completed <= 0:
        status = "NOT_READY"
    elif completed >= REQUIRED_COMPLETENESS_COUNT:
        status = "READY"
    else:
        status = "PARTIALLY_READY"
    return {
        "profile_status": status,
        "profile_ready": completed >= REQUIRED_COMPLETENESS_COUNT,
        "frie_scoring_ready": False,
    }

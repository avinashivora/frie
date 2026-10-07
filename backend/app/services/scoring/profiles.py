"""
FRIE purpose-specific profile aggregation.

The six canonical dimension scores are calculated once.  A profile changes
their relative importance; it does not recalculate the underlying dimensions.

Profiles:
    neutral   - general financial reliability / base profile
    loan      - debt/repayment-oriented assessment
    insurance - financial/payment reliability for insurance commitments

Profile scores are normalized to /100.  The canonical neutral FRIE Base Score
remains the six-dimension /600 score produced by frie_score.py.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from .frie_score import (
    ALGORITHM_VERSION,
    DIMENSION_ORDER,
    DimensionResult,
    DimensionStatus,
    calculate_dimensions,
)


PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "neutral": {
        "credit_behaviour": 0.20,
        "affordability": 0.20,
        "cashflow_stability": 0.20,
        "financial_resilience": 0.15,
        "commitment_adherence": 0.15,
        "spending_behaviour": 0.10,
    },
    "loan": {
        "credit_behaviour": 0.30,
        "affordability": 0.25,
        "cashflow_stability": 0.15,
        "financial_resilience": 0.10,
        "commitment_adherence": 0.15,
        "spending_behaviour": 0.05,
    },
    "insurance": {
        "credit_behaviour": 0.15,
        "affordability": 0.15,
        "cashflow_stability": 0.20,
        "financial_resilience": 0.20,
        "commitment_adherence": 0.25,
        "spending_behaviour": 0.05,
    },
}


def _validate_weights(weights: Mapping[str, float]) -> None:
    missing = set(DIMENSION_ORDER) - set(weights)
    extra = set(weights) - set(DIMENSION_ORDER)

    if missing:
        raise ValueError(f"Profile weights missing dimensions: {sorted(missing)}")
    if extra:
        raise ValueError(f"Unknown profile dimensions: {sorted(extra)}")

    total = sum(float(weights[name]) for name in DIMENSION_ORDER)
    if not isfinite(total) or total <= 0:
        raise ValueError("Profile weights must have a positive finite total.")

    if any(float(weights[name]) < 0 for name in DIMENSION_ORDER):
        raise ValueError("Profile weights cannot be negative.")


def get_profile_weights(profile: str) -> dict[str, float]:
    key = profile.strip().lower()
    if key not in PROFILE_WEIGHTS:
        raise ValueError(
            f"Unknown FRIE profile '{profile}'. "
            f"Expected one of: {', '.join(PROFILE_WEIGHTS)}."
        )
    return dict(PROFILE_WEIGHTS[key])


def _usable(result: DimensionResult) -> bool:
    return result.score is not None and result.status not in {
        DimensionStatus.UNAVAILABLE.value,
        DimensionStatus.NOT_ESTABLISHED.value,
    }


def calculate_profile_score(
    dimensions: Mapping[str, DimensionResult],
    profile: str = "neutral",
) -> dict[str, Any]:
    """
    Calculate a purpose-specific /100 profile score.

    Missing dimensions are excluded and their weights are redistributed across
    dimensions that are actually usable.  The original configured weights are
    returned separately from the effective weights so the frontend can explain
    what happened.
    """

    weights = get_profile_weights(profile)
    _validate_weights(weights)

    usable = {
        name: dimensions[name]
        for name in DIMENSION_ORDER
        if name in dimensions and _usable(dimensions[name])
    }

    usable_weight = sum(weights[name] for name in usable)

    if not usable or usable_weight <= 0:
        return {
            "profile": profile.lower(),
            "score": None,
            "maximum": 100.0,
            "configured_weights": weights,
            "effective_weights": {},
            "coverage": 0.0,
            "confidence": "Low",
            "available_dimensions": 0,
        }

    effective_weights = {name: weights[name] / usable_weight for name in usable}

    score = sum(float(usable[name].score) * effective_weights[name] for name in usable)

    coverage = sum(
        dimensions[name].coverage * weights[name] for name in DIMENSION_ORDER
    )

    available_count = len(usable)

    if available_count == len(DIMENSION_ORDER) and coverage >= 0.90:
        confidence = "High"
    elif available_count >= 4 and coverage >= 0.65:
        confidence = "Moderate"
    else:
        confidence = "Low"

    return {
        "profile": profile.lower(),
        "score": round(max(0.0, min(100.0, score)), 4),
        "maximum": 100.0,
        "configured_weights": weights,
        "effective_weights": {
            name: round(value, 6) for name, value in effective_weights.items()
        },
        "coverage": round(max(0.0, min(1.0, coverage)), 4),
        "confidence": confidence,
        "available_dimensions": available_count,
    }


def calculate_profile(
    features: Mapping[str, Any],
    profile: str = "neutral",
) -> dict[str, Any]:
    """Run the six dimensions once and produce one purpose-specific profile."""

    dimensions = calculate_dimensions(features)
    result = calculate_profile_score(dimensions, profile=profile)

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "profile": result,
        "dimensions": {
            name: {
                "score": dimensions[name].score,
                "coverage": dimensions[name].coverage,
                "status": dimensions[name].status,
                "confidence": dimensions[name].confidence,
                "indicators": dimensions[name].indicators,
                "effective_weights": dimensions[name].effective_weights,
            }
            for name in DIMENSION_ORDER
        },
    }


def calculate_all_profiles(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Calculate neutral, loan, and insurance profiles from the same six
    dimension results.  The dimensions are evaluated only once.
    """

    dimensions = calculate_dimensions(features)

    profiles = {
        name: calculate_profile_score(dimensions, profile=name)
        for name in PROFILE_WEIGHTS
    }

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "dimensions": {
            name: {
                "score": dimensions[name].score,
                "coverage": dimensions[name].coverage,
                "status": dimensions[name].status,
                "confidence": dimensions[name].confidence,
                "indicators": dimensions[name].indicators,
                "effective_weights": dimensions[name].effective_weights,
            }
            for name in DIMENSION_ORDER
        },
        "profiles": profiles,
    }


def calculate_loan_profile(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    return calculate_profile(features, profile="loan")


def calculate_insurance_profile(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    return calculate_profile(features, profile="insurance")


def calculate_neutral_profile(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    return calculate_profile(features, profile="neutral")


__all__ = [
    "PROFILE_WEIGHTS",
    "calculate_all_profiles",
    "calculate_insurance_profile",
    "calculate_loan_profile",
    "calculate_neutral_profile",
    "calculate_profile",
    "calculate_profile_score",
    "get_profile_weights",
]

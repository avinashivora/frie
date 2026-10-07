"""
FRIE six-dimension scoring orchestrator.

This module is deliberately independent of FastAPI, the database, React,
XGBoost, and SHAP.  The six dimension modules remain the source of truth for
their individual scoring logic; this module only combines their results.

Canonical FRIE dimensions:
    - Credit Behaviour
    - Affordability
    - Cash-Flow Stability
    - Financial Resilience
    - Commitment Adherence
    - Spending Behaviour

The canonical neutral FRIE Base Score is the sum of the six /100 dimension
scores and therefore has a maximum of 600.

Missing/unavailable dimensions are NOT treated as zero.  Profile-level
aggregation redistributes weights across dimensions that can actually be
evaluated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from math import isfinite
from typing import Any, Mapping

from . import affordability
from . import cashflow_stability
from . import commitment_adherence
from . import credit_behavior
from . import financial_resiliance
from . import spending_behavior


ALGORITHM_VERSION = "FRIE-6D-v1.0"
BASE_SCORE_MAX = 600.0

DIMENSION_ORDER: tuple[str, ...] = (
    "credit_behaviour",
    "affordability",
    "cashflow_stability",
    "financial_resilience",
    "commitment_adherence",
    "spending_behaviour",
)


class DimensionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    LIMITED = "LIMITED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class DimensionResult:
    """Normalized result returned by every dimension."""

    score: float | None
    coverage: float
    status: str
    confidence: str
    indicators: dict[str, Any]
    effective_weights: dict[str, float]
    validation: dict[str, Any]


# The existing dimension files were developed independently.  These candidate
# names allow the orchestrator to tolerate the naming convention used in each
# module without changing their internal scoring implementation.
_FUNCTION_CANDIDATES: dict[str, tuple[str, ...]] = {
    "credit_behaviour": (
        "score_credit_behaviour",
        "score_credit_behavior",
    ),
    "affordability": ("score_affordability",),
    "cashflow_stability": (
        "score_cashflow_stability",
        "score_cash_flow_stability",
    ),
    "financial_resilience": (
        "score_financial_resilience",
        "score_financial_resiliance",
    ),
    "commitment_adherence": ("score_commitment_adherence",),
    "spending_behaviour": (
        "score_spending_behaviour",
        "score_spending_behavior",
    ),
}

_MODULES = {
    "credit_behaviour": credit_behavior,
    "affordability": affordability,
    "cashflow_stability": cashflow_stability,
    "financial_resilience": financial_resiliance,
    "commitment_adherence": commitment_adherence,
    "spending_behaviour": spending_behavior,
}


def _first_callable(module: Any, candidates: tuple[str, ...]):
    for name in candidates:
        function = getattr(module, name, None)
        if callable(function):
            return function
    raise AttributeError(
        f"None of the expected scoring functions {candidates!r} "
        f"were found in {module.__name__}."
    )


def _finite_score(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return max(0.0, min(100.0, number))


def _normalise_status(value: Any, score: float | None, coverage: float) -> str:
    if value is not None:
        raw = getattr(value, "value", value)
        raw = str(raw).upper()
        if raw in {status.value for status in DimensionStatus}:
            return raw

    if score is None:
        return DimensionStatus.UNAVAILABLE.value

    if coverage < 1.0:
        return DimensionStatus.LIMITED.value

    return DimensionStatus.AVAILABLE.value


def _normalise_result(raw: Any) -> DimensionResult:
    """
    Convert a dimension module's result into one stable representation.

    The dimension files may return a dataclass, mapping, or an object with
    attributes.  This keeps the six-dimension orchestrator decoupled from
    their implementation details.
    """

    if isinstance(raw, Mapping):
        get = raw.get
    else:
        get = lambda key, default=None: getattr(raw, key, default)

    score = _finite_score(get("score", get("value", get("component_score"))))

    coverage_raw = get("coverage", get("data_coverage", 0.0))
    try:
        coverage = float(coverage_raw)
    except (TypeError, ValueError):
        coverage = 0.0
    if not isfinite(coverage):
        coverage = 0.0
    coverage = max(0.0, min(1.0, coverage))

    status = _normalise_status(get("status"), score, coverage)

    confidence = get("confidence", "Low")
    confidence = getattr(confidence, "value", confidence)
    confidence = str(confidence)

    indicators = get("indicators", get("indicator_scores", {}))
    if not isinstance(indicators, Mapping):
        indicators = {}

    effective_weights = get("effective_weights", get("weights", {}))
    if not isinstance(effective_weights, Mapping):
        effective_weights = {}

    validation = get("validation", {})
    if not isinstance(validation, Mapping):
        validation = {}

    return DimensionResult(
        score=score,
        coverage=coverage,
        status=status,
        confidence=confidence,
        indicators=dict(indicators),
        effective_weights={
            str(k): float(v)
            for k, v in effective_weights.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        },
        validation=dict(validation),
    )


def _score_dimension(name: str, features: Mapping[str, Any]) -> DimensionResult:
    module = _MODULES[name]
    function = _first_callable(module, _FUNCTION_CANDIDATES[name])
    raw = function(features)
    return _normalise_result(raw)


def calculate_dimensions(features: Mapping[str, Any]) -> dict[str, DimensionResult]:
    """Run all six canonical dimension algorithms."""

    return {name: _score_dimension(name, features) for name in DIMENSION_ORDER}


def calculate_base_score(
    dimensions: Mapping[str, DimensionResult],
) -> dict[str, Any]:
    """
    Calculate the canonical /600 FRIE Base Score.

    A dimension that is genuinely unavailable/not established is not assigned
    zero.  Its contribution is absent from the denominator and the result
    carries coverage/confidence information separately.
    """

    available = [
        dimensions[name].score
        for name in DIMENSION_ORDER
        if dimensions[name].score is not None
    ]

    score = float(sum(available)) if available else None

    dimension_coverage = {name: dimensions[name].coverage for name in DIMENSION_ORDER}

    overall_coverage = (
        sum(dimension_coverage.values()) / len(DIMENSION_ORDER)
        if DIMENSION_ORDER
        else 0.0
    )

    established = sum(
        dimensions[name].status
        in {
            DimensionStatus.AVAILABLE.value,
            DimensionStatus.LIMITED.value,
        }
        for name in DIMENSION_ORDER
    )

    # This is a coverage descriptor, not a probability of repayment/default.
    if score is None:
        confidence = "Low"
    elif established == len(DIMENSION_ORDER) and overall_coverage >= 0.90:
        confidence = "High"
    elif established >= 4 and overall_coverage >= 0.65:
        confidence = "Moderate"
    else:
        confidence = "Low"

    return {
        "value": score,
        "maximum": BASE_SCORE_MAX,
        "available_dimensions": established,
        "dimension_count": len(DIMENSION_ORDER),
        "coverage": round(overall_coverage, 4),
        "confidence": confidence,
    }


def calculate_frie_score(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Complete neutral FRIE assessment.

    This is the main function the backend service should call.
    """

    dimensions = calculate_dimensions(features)
    base_score = calculate_base_score(dimensions)

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "frie_score": base_score,
        "dimensions": {name: asdict(dimensions[name]) for name in DIMENSION_ORDER},
    }


# Compatibility aliases for backend integration.
score_frie = calculate_frie_score
assess = calculate_frie_score


__all__ = [
    "ALGORITHM_VERSION",
    "BASE_SCORE_MAX",
    "DIMENSION_ORDER",
    "DimensionResult",
    "DimensionStatus",
    "assess",
    "calculate_base_score",
    "calculate_dimensions",
    "calculate_frie_score",
    "score_frie",
]

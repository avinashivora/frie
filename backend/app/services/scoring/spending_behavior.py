"""
Spending Behaviour Scoring
==========================

FRIE Component: Spending Behaviour

Purpose
-------
Measures whether an individual's spending pattern is financially
sustainable, with emphasis on total spending burden, discretionary
spending, and the balance between essential and discretionary
expenses.

Output
------
Spending Behaviour score: 0–100

Indicators
----------
    1. Overall Spending Burden          40%
    2. Discretionary Spending Discipline 30%
    3. Essential/Discretionary Balance  20%
    4. Spending Pattern Coverage        10%

Important design decisions
--------------------------
- High spending is not automatically "bad"; it is evaluated
  relative to income where possible.
- Discretionary spending is treated differently from essential
  spending.
- UPI usage and digital-payment usage are NOT treated as
  inherently positive or negative behaviours.
- Missing expense categories do not become zero spending.
- Missing data reduces coverage/confidence rather than creating
  an artificial penalty.
- Affordability and spending behaviour remain separate:
      Affordability -> ability to meet obligations
      Spending      -> composition and burden of spending
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional
import math


# ============================================================
# Configuration
# ============================================================

INDICATOR_WEIGHTS = {
    "overall_spending_burden": 0.40,
    "discretionary_spending_discipline": 0.30,
    "essential_discretionary_balance": 0.20,
    "spending_pattern_coverage": 0.10,
}


SPENDING_FEATURES = {
    # Aggregate spending
    "synthetic_total_expense",
    "synthetic_spending_ratio",
    # Income denominator
    "monthly_income",
    # Expense categories
    "food_expense",
    "rent_expense",
    "education_expense",
    "healthcare_expense",
    "transport_expense",
    "utility_expense",
    "discretionary_expense",
    # Payment-channel/context variables
    "upi_spending",
    "upi_transaction_count",
    "digital_payment_ratio",
}


ESSENTIAL_EXPENSE_FEATURES = (
    "food_expense",
    "rent_expense",
    "education_expense",
    "healthcare_expense",
    "transport_expense",
    "utility_expense",
)


DISCRETIONARY_FEATURES = ("discretionary_expense",)


# ============================================================
# Enums / Result Objects
# ============================================================


class FeatureState(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"


class IndicatorStatus(str, Enum):
    AVAILABLE = "available"
    LIMITED = "limited"
    NOT_ESTABLISHED = "not_established"
    UNAVAILABLE = "unavailable"


@dataclass
class IndicatorResult:
    name: str
    score: Optional[float]
    coverage: float
    status: IndicatorStatus
    reason: str = ""
    features_used: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "coverage": round(self.coverage, 4),
            "status": self.status.value,
            "reason": self.reason,
            "features_used": self.features_used or [],
        }


# ============================================================
# General Helpers
# ============================================================


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        return False


def _is_numeric(value: Any) -> bool:
    if _is_missing(value):
        return False

    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_number(value: Any) -> Optional[float]:
    if not _is_numeric(value):
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    return value


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:

    return max(low, min(high, value))


def _round_score(
    value: Optional[float],
) -> Optional[float]:

    if value is None:
        return None

    return round(_clamp(value), 2)


# ============================================================
# Validation
# ============================================================


def validate_spending_features(
    data: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Validate only features relevant to Spending Behaviour.

    No source values are modified.
    """

    result = {}

    numeric_features = {
        "synthetic_total_expense",
        "synthetic_spending_ratio",
        "monthly_income",
        "food_expense",
        "rent_expense",
        "education_expense",
        "healthcare_expense",
        "transport_expense",
        "utility_expense",
        "discretionary_expense",
        "upi_spending",
        "upi_transaction_count",
        "digital_payment_ratio",
    }

    for feature in SPENDING_FEATURES:
        value = data.get(feature)

        if _is_missing(value):
            result[feature] = {
                "state": FeatureState.MISSING.value,
                "value": None,
                "reason": "Feature is missing.",
            }

            continue

        if feature in numeric_features:
            numeric_value = _finite_number(value)

            if numeric_value is None:
                result[feature] = {
                    "state": FeatureState.INVALID.value,
                    "value": value,
                    "reason": "Expected a finite numeric value.",
                }

                continue

            # Monetary quantities and counts cannot be negative.
            if feature != "synthetic_spending_ratio":
                if numeric_value < 0:
                    result[feature] = {
                        "state": FeatureState.INVALID.value,
                        "value": numeric_value,
                        "reason": "Value cannot be negative.",
                    }

                    continue

            # Spending ratio and digital payment ratio are bounded.
            if feature in {
                "synthetic_spending_ratio",
                "digital_payment_ratio",
            }:
                if not 0 <= numeric_value <= 1:
                    result[feature] = {
                        "state": FeatureState.INVALID.value,
                        "value": numeric_value,
                        "reason": "Ratio must be between 0 and 1.",
                    }

                    continue

            result[feature] = {
                "state": FeatureState.VALID.value,
                "value": numeric_value,
                "reason": "",
            }

        else:
            result[feature] = {
                "state": FeatureState.VALID.value,
                "value": value,
                "reason": "",
            }

    return result


# ============================================================
# Score Helpers
# ============================================================


def _lower_is_better_score(
    value: float,
    thresholds: List[tuple[float, float]],
) -> float:
    """
    Score where lower values are better.

    thresholds:
        [(upper_bound, score), ...]

    Example:
        <= 0.30 -> 100
        <= 0.40 -> 90
        <= 0.50 -> 75
        ...
    """

    for upper_bound, score in thresholds:
        if value <= upper_bound:
            return _clamp(score)

    return 0.0


def _higher_is_better_score(
    value: float,
    thresholds: List[tuple[float, float]],
) -> float:
    """
    Score where higher values are better.

    thresholds:
        [(lower_bound, score), ...]
    """

    score = thresholds[0][1]

    for lower_bound, threshold_score in thresholds:
        if value >= lower_bound:
            score = threshold_score
        else:
            break

    return _clamp(score)


# ============================================================
# Indicator 1
# Overall Spending Burden
# ============================================================


def score_overall_spending_burden(
    data: Mapping[str, Any],
) -> IndicatorResult:

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    monthly_income = _finite_number(data.get("monthly_income"))

    spending_ratio = _finite_number(data.get("synthetic_spending_ratio"))

    # --------------------------------------------------------
    # Preferred calculation
    # --------------------------------------------------------

    if total_expense is not None and monthly_income is not None and monthly_income > 0:
        expense_ratio = total_expense / monthly_income

        score = _lower_is_better_score(
            expense_ratio,
            [
                (0.30, 100),
                (0.40, 90),
                (0.50, 75),
                (0.60, 55),
                (0.70, 35),
                (0.80, 15),
            ],
        )

        return IndicatorResult(
            name="overall_spending_burden",
            score=_round_score(score),
            coverage=1.0,
            status=IndicatorStatus.AVAILABLE,
            reason=("Total monthly spending is evaluated relative to monthly income."),
            features_used=[
                "synthetic_total_expense",
                "monthly_income",
            ],
        )

    # --------------------------------------------------------
    # Fallback to supplied spending ratio
    # --------------------------------------------------------

    if spending_ratio is not None:
        score = _lower_is_better_score(
            spending_ratio,
            [
                (0.30, 100),
                (0.40, 90),
                (0.50, 75),
                (0.60, 55),
                (0.70, 35),
                (0.80, 15),
            ],
        )

        return IndicatorResult(
            name="overall_spending_burden",
            score=_round_score(score),
            coverage=0.75,
            status=IndicatorStatus.LIMITED,
            reason=(
                "Synthetic spending ratio is available, but "
                "income-normalized spending could not be independently "
                "reconstructed."
            ),
            features_used=[
                "synthetic_spending_ratio",
            ],
        )

    return IndicatorResult(
        name="overall_spending_burden",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.NOT_ESTABLISHED,
        reason="Insufficient information to evaluate spending burden.",
        features_used=[],
    )


# ============================================================
# Indicator 2
# Discretionary Spending Discipline
# ============================================================


def score_discretionary_spending_discipline(
    data: Mapping[str, Any],
) -> IndicatorResult:

    discretionary = _finite_number(data.get("discretionary_expense"))

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    if discretionary is None:
        return IndicatorResult(
            name="discretionary_spending_discipline",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Discretionary spending information is unavailable.",
            features_used=[],
        )

    # --------------------------------------------------------
    # Preferred: discretionary expense / total expense
    # --------------------------------------------------------

    if total_expense is not None and total_expense > 0:
        discretionary_ratio = discretionary / total_expense

        score = _lower_is_better_score(
            discretionary_ratio,
            [
                (0.10, 100),
                (0.15, 95),
                (0.20, 85),
                (0.25, 75),
                (0.30, 60),
                (0.40, 40),
                (0.50, 20),
            ],
        )

        return IndicatorResult(
            name="discretionary_spending_discipline",
            score=_round_score(score),
            coverage=1.0,
            status=IndicatorStatus.AVAILABLE,
            reason=(
                "Discretionary spending is evaluated as a share of total spending."
            ),
            features_used=[
                "discretionary_expense",
                "synthetic_total_expense",
            ],
        )

    return IndicatorResult(
        name="discretionary_spending_discipline",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.LIMITED,
        reason=(
            "Discretionary spending is known, but total spending "
            "is unavailable for normalization."
        ),
        features_used=[
            "discretionary_expense",
        ],
    )


# ============================================================
# Indicator 3
# Essential / Discretionary Balance
# ============================================================


def score_essential_discretionary_balance(
    data: Mapping[str, Any],
) -> IndicatorResult:

    essential_values = []
    essential_features = []

    for feature in ESSENTIAL_EXPENSE_FEATURES:
        value = _finite_number(data.get(feature))

        if value is not None:
            essential_values.append(value)
            essential_features.append(feature)

    discretionary = _finite_number(data.get("discretionary_expense"))

    if not essential_values and discretionary is None:
        return IndicatorResult(
            name="essential_discretionary_balance",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No expense-category information is available.",
            features_used=[],
        )

    essential_total = sum(essential_values)

    # --------------------------------------------------------
    # If total expense is available, compare category
    # reconstruction against it.
    # --------------------------------------------------------

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    if total_expense is not None and total_expense > 0:
        discretionary_value = discretionary if discretionary is not None else 0.0

        category_total = essential_total + discretionary_value

        # Category coverage measures how much of the reported
        # total expense can be explained by available categories.
        #
        # This is NOT treated as a direct financial virtue.
        # It is used to determine whether the category composition
        # can be evaluated reliably.

        category_coverage = min(
            category_total / total_expense,
            1.0,
        )

        if category_total > 0:
            discretionary_share = discretionary_value / category_total

            score = _lower_is_better_score(
                discretionary_share,
                [
                    (0.10, 100),
                    (0.15, 95),
                    (0.20, 85),
                    (0.25, 75),
                    (0.30, 60),
                    (0.40, 40),
                    (0.50, 20),
                ],
            )

        else:
            score = 50.0

        status = (
            IndicatorStatus.AVAILABLE
            if category_coverage >= 0.80
            else IndicatorStatus.LIMITED
        )

        return IndicatorResult(
            name="essential_discretionary_balance",
            score=_round_score(score),
            coverage=round(category_coverage, 4),
            status=status,
            reason=(
                "Available essential and discretionary categories "
                "are evaluated as a spending composition."
            ),
            features_used=(
                essential_features
                + (["discretionary_expense"] if discretionary is not None else [])
                + ["synthetic_total_expense"]
            ),
        )

    # --------------------------------------------------------
    # No total expense
    # --------------------------------------------------------
    #
    # If both essential and discretionary data exist, we can
    # still calculate a local composition ratio, but confidence
    # is limited because the supplied categories may not represent
    # all spending.

    if discretionary is not None and essential_total > 0:
        discretionary_share = discretionary / (essential_total + discretionary)

        score = _lower_is_better_score(
            discretionary_share,
            [
                (0.10, 100),
                (0.15, 95),
                (0.20, 85),
                (0.25, 75),
                (0.30, 60),
                (0.40, 40),
                (0.50, 20),
            ],
        )

        return IndicatorResult(
            name="essential_discretionary_balance",
            score=_round_score(score),
            coverage=0.60,
            status=IndicatorStatus.LIMITED,
            reason=(
                "Category composition is available, but total "
                "reported spending is unavailable."
            ),
            features_used=(essential_features + ["discretionary_expense"]),
        )

    return IndicatorResult(
        name="essential_discretionary_balance",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.LIMITED,
        reason=(
            "Insufficient category information to evaluate "
            "essential versus discretionary spending."
        ),
        features_used=essential_features,
    )


# ============================================================
# Indicator 4
# Spending Pattern Coverage
# ============================================================


def score_spending_pattern_coverage(
    data: Mapping[str, Any],
) -> IndicatorResult:

    category_features = ESSENTIAL_EXPENSE_FEATURES + DISCRETIONARY_FEATURES

    available = 0
    features_used = []

    for feature in category_features:
        value = _finite_number(data.get(feature))

        if value is not None:
            available += 1
            features_used.append(feature)

    total_categories = len(category_features)

    if available == 0:
        return IndicatorResult(
            name="spending_pattern_coverage",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No spending-category data is available.",
            features_used=[],
        )

    coverage = available / total_categories

    # This is a data-quality / observability signal.
    #
    # It should NOT directly reward a particular spending pattern.
    score = coverage * 100

    if coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE
    else:
        status = IndicatorStatus.LIMITED

    return IndicatorResult(
        name="spending_pattern_coverage",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=(
            "Measures how completely the available spending categories are represented."
        ),
        features_used=features_used,
    )


# ============================================================
# Combine Indicators
# ============================================================


def combine_indicators(
    indicators: Mapping[str, IndicatorResult],
) -> Dict[str, Any]:

    usable = {
        name: result
        for name, result in indicators.items()
        if result.score is not None
        and result.status
        in {
            IndicatorStatus.AVAILABLE,
            IndicatorStatus.LIMITED,
        }
    }

    if not usable:
        return {
            "score": None,
            "coverage": 0.0,
            "status": IndicatorStatus.NOT_ESTABLISHED.value,
            "effective_weights": {},
        }

    total_weight = sum(INDICATOR_WEIGHTS[name] for name in usable)

    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / total_weight for name in usable
    }

    score = sum(usable[name].score * effective_weights[name] for name in usable)

    # Original weights determine evidence coverage.
    coverage = sum(INDICATOR_WEIGHTS[name] * usable[name].coverage for name in usable)

    coverage = _clamp(
        coverage,
        0.0,
        1.0,
    )

    if coverage >= 0.85:
        status = IndicatorStatus.AVAILABLE
    elif coverage > 0:
        status = IndicatorStatus.LIMITED
    else:
        status = IndicatorStatus.NOT_ESTABLISHED

    return {
        "score": _round_score(score),
        "coverage": round(coverage, 4),
        "status": status.value,
        "effective_weights": {
            name: round(weight, 6) for name, weight in effective_weights.items()
        },
    }


# ============================================================
# Confidence
# ============================================================


def confidence_from_coverage(
    coverage: float,
) -> str:

    coverage_percentage = _clamp(
        coverage * 100,
        0,
        100,
    )

    if coverage_percentage >= 80:
        return "High"

    if coverage_percentage >= 50:
        return "Moderate"

    return "Low"


# ============================================================
# Main Scoring Function
# ============================================================


def score_spending_behaviour(
    data: Mapping[str, Any],
) -> Dict[str, Any]:

    validation = validate_spending_features(data)

    indicators = {
        "overall_spending_burden": (score_overall_spending_burden(data)),
        "discretionary_spending_discipline": (
            score_discretionary_spending_discipline(data)
        ),
        "essential_discretionary_balance": (
            score_essential_discretionary_balance(data)
        ),
        "spending_pattern_coverage": (score_spending_pattern_coverage(data)),
    }

    combined = combine_indicators(indicators)

    return {
        "component": "spending_behaviour",
        "score": combined["score"],
        "maximum": 100,
        "coverage": combined["coverage"],
        "status": combined["status"],
        "confidence": confidence_from_coverage(combined["coverage"]),
        "effective_weights": combined["effective_weights"],
        "indicator_scores": {
            name: result.to_dict() for name, result in indicators.items()
        },
        "validation": validation,
    }


# ============================================================
# Batch Scoring
# ============================================================


def score_spending_batch(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:

    return [score_spending_behaviour(record) for record in records]


# ============================================================
# Pandas Adapter
# ============================================================


def score_spending_dataframe(df):
    """
    Score every row of a pandas DataFrame.

    Adds:

        spending_behaviour_score
        spending_behaviour_coverage
        spending_behaviour_status
        spending_behaviour_confidence
    """

    result_df = df.copy()

    scores = []
    coverages = []
    statuses = []
    confidences = []

    for _, row in result_df.iterrows():
        result = score_spending_behaviour(row.to_dict())

        scores.append(result["score"])
        coverages.append(result["coverage"])
        statuses.append(result["status"])
        confidences.append(result["confidence"])

    result_df["spending_behaviour_score"] = scores
    result_df["spending_behaviour_coverage"] = coverages
    result_df["spending_behaviour_status"] = statuses
    result_df["spending_behaviour_confidence"] = confidences

    return result_df


# ============================================================
# ML Feature Extraction
# ============================================================


def get_ml_features(
    data: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return engineered Spending Behaviour features suitable for
    a future supervised ML layer.

    No ML is trained or invoked.

    These features can later be used by a model predicting a
    genuine financial outcome.
    """

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    monthly_income = _finite_number(data.get("monthly_income"))

    discretionary = _finite_number(data.get("discretionary_expense"))

    spending_ratio = None

    if total_expense is not None and monthly_income is not None and monthly_income > 0:
        spending_ratio = total_expense / monthly_income

    discretionary_ratio = None

    if discretionary is not None and total_expense is not None and total_expense > 0:
        discretionary_ratio = discretionary / total_expense

    essential_total = 0.0
    essential_available = False

    for feature in ESSENTIAL_EXPENSE_FEATURES:
        value = _finite_number(data.get(feature))

        if value is not None:
            essential_total += value
            essential_available = True

    essential_discretionary_ratio = None

    if (
        essential_available
        and discretionary is not None
        and essential_total + discretionary > 0
    ):
        essential_discretionary_ratio = discretionary / (
            essential_total + discretionary
        )

    return {
        "monthly_income": monthly_income,
        "synthetic_total_expense": total_expense,
        "spending_to_income_ratio": spending_ratio,
        "discretionary_expense": discretionary,
        "discretionary_spending_ratio": discretionary_ratio,
        "essential_expense_total": (essential_total if essential_available else None),
        "essential_discretionary_ratio": (essential_discretionary_ratio),
        "upi_spending": _finite_number(data.get("upi_spending")),
        "upi_transaction_count": _finite_number(data.get("upi_transaction_count")),
        "digital_payment_ratio": _finite_number(data.get("digital_payment_ratio")),
    }


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    example = {
        "monthly_income": 75000,
        "synthetic_total_expense": 40000,
        "synthetic_spending_ratio": 0.5333,
        "food_expense": 8000,
        "rent_expense": 15000,
        "education_expense": 3000,
        "healthcare_expense": 2000,
        "transport_expense": 3000,
        "utility_expense": 3000,
        "discretionary_expense": 6000,
        # Context only:
        "upi_spending": 18000,
        "upi_transaction_count": 72,
        "digital_payment_ratio": 0.85,
    }

    result = score_spending_behaviour(example)

    print("\nSpending Behaviour")
    print("==================")

    print(f"Score:      {result['score']}/100")

    print(f"Coverage:   {result['coverage']:.2%}")

    print(f"Status:     {result['status']}")

    print(f"Confidence: {result['confidence']}")

    print("\nIndicators:")

    for name, indicator in result["indicator_scores"].items():
        print(f"  {name}: {indicator['score']}/100 ({indicator['status']})")

    print("\nEffective weights:")

    for name, weight in result["effective_weights"].items():
        print(f"  {name}: {weight:.2%}")

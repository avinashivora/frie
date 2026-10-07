"""
Affordability Scoring
=====================

FRIE Component: Affordability

Purpose
-------
Measures whether an individual's current financial obligations
are affordable relative to income.

Output
------
Affordability score: 0–100

Indicators
----------
    1. Debt-to-Income Burden       30%
    2. EMI / Income Burden         30%
    3. Expense / Income Burden     20%
    4. Available Surplus           20%

Design principles
-----------------
- Higher financial burden -> lower score.
- Missing != zero.
- DTI sources are treated as alternative evidence rather than
  blindly double-counted.
- Savings/assets are NOT scored here; they belong to
  Financial Resilience.
- Spending composition is NOT scored here; it belongs to
  Spending Behaviour.
- Credit repayment history is NOT scored here; it belongs to
  Credit Behaviour / Commitment Adherence.
- No demographic/context variable is directly scored.

Missing-data semantics
----------------------
AVAILABLE
    Sufficient information exists.

LIMITED
    Some relevant information exists, but the indicator is
    incomplete.

NOT_ESTABLISHED
    The financial relationship cannot be established from the
    available data.

UNAVAILABLE
    Expected information is unavailable.

Unavailable indicators have their weight redistributed across
the remaining usable indicators.
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
    "debt_to_income_burden": 0.30,
    "emi_income_burden": 0.30,
    "expense_income_burden": 0.20,
    "available_surplus": 0.20,
}


AFFORDABILITY_FEATURES = {
    "monthly_income",
    "current_dti",
    "bureau_dti",
    "current_loan_annuity",
    "synthetic_total_expense",
    "synthetic_total_emi",
    "available_surplus",
    "current_credit_amount",
    "goods_price",
}


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

    return isinstance(value, (int, float)) and not isinstance(
        value,
        bool,
    )


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


def validate_affordability_features(
    data: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Validate only features relevant to Affordability.

    No source values are modified.
    """

    result = {}

    numeric_features = {
        "monthly_income",
        "current_dti",
        "bureau_dti",
        "current_loan_annuity",
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
        "current_credit_amount",
        "goods_price",
    }

    for feature in AFFORDABILITY_FEATURES:
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

            # Monetary burden quantities cannot be negative.
            if feature not in {"available_surplus"}:
                if numeric_value < 0:
                    result[feature] = {
                        "state": FeatureState.INVALID.value,
                        "value": numeric_value,
                        "reason": "Value cannot be negative.",
                    }

                    continue

            # DTI is expected as a ratio in the dataset.
            if feature in {
                "current_dti",
                "bureau_dti",
            }:
                if numeric_value < 0:
                    result[feature] = {
                        "state": FeatureState.INVALID.value,
                        "value": numeric_value,
                        "reason": "DTI cannot be negative.",
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
    Score where lower burden is better.

    thresholds:
        [(upper_bound, score), ...]

    Example:
        <= 0.10 -> 100
        <= 0.20 -> 90
        <= 0.30 -> 75
        ...
    """

    for upper_bound, score in thresholds:
        if value <= upper_bound:
            return _clamp(score)

    return 0.0


# ============================================================
# Indicator 1
# Debt-to-Income Burden
# ============================================================


def score_debt_to_income_burden(
    data: Mapping[str, Any],
) -> IndicatorResult:
    """
    Score DTI using current_dti and/or bureau_dti.

    If both are available, they are treated as two observations
    of the same underlying concept rather than two independent
    burdens.

    Therefore the values are averaged rather than both being
    given independent weight.
    """

    current_dti = _finite_number(data.get("current_dti"))

    bureau_dti = _finite_number(data.get("bureau_dti"))

    dti_values = []
    features_used = []

    if current_dti is not None:
        dti_values.append(current_dti)
        features_used.append("current_dti")

    if bureau_dti is not None:
        dti_values.append(bureau_dti)
        features_used.append("bureau_dti")

    if not dti_values:
        return IndicatorResult(
            name="debt_to_income_burden",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No DTI information is available.",
            features_used=[],
        )

    # --------------------------------------------------------
    # If both exist, average them rather than double counting.
    # --------------------------------------------------------

    dti = sum(dti_values) / len(dti_values)

    score = _lower_is_better_score(
        dti,
        [
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 50),
            (0.50, 25),
        ],
    )

    if len(dti_values) == 2:
        coverage = 1.0
        status = IndicatorStatus.AVAILABLE
        reason = (
            "Current and bureau DTI are combined as alternative "
            "evidence of debt burden."
        )

    else:
        coverage = 0.75
        status = IndicatorStatus.LIMITED
        reason = (
            "Only one DTI source is available; the other source "
            "cannot independently corroborate debt burden."
        )

    return IndicatorResult(
        name="debt_to_income_burden",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=reason,
        features_used=features_used,
    )


# ============================================================
# Indicator 2
# EMI / Income Burden
# ============================================================


def score_emi_income_burden(
    data: Mapping[str, Any],
) -> IndicatorResult:

    monthly_income = _finite_number(data.get("monthly_income"))

    loan_annuity = _finite_number(data.get("current_loan_annuity"))

    # Use synthetic_total_emi only as a fallback if the current
    # loan annuity is unavailable.
    synthetic_emi = _finite_number(data.get("synthetic_total_emi"))

    if monthly_income is None or monthly_income <= 0:
        return IndicatorResult(
            name="emi_income_burden",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Monthly income is unavailable or invalid.",
            features_used=[],
        )

    if loan_annuity is not None:
        emi = loan_annuity
        emi_feature = "current_loan_annuity"
        coverage = 1.0
        status = IndicatorStatus.AVAILABLE

    elif synthetic_emi is not None:
        emi = synthetic_emi
        emi_feature = "synthetic_total_emi"
        coverage = 0.75
        status = IndicatorStatus.LIMITED

    else:
        return IndicatorResult(
            name="emi_income_burden",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No EMI information is available.",
            features_used=["monthly_income"],
        )

    emi_ratio = emi / monthly_income

    score = _lower_is_better_score(
        emi_ratio,
        [
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 50),
            (0.50, 25),
        ],
    )

    return IndicatorResult(
        name="emi_income_burden",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=("Monthly EMI obligation is evaluated relative to monthly income."),
        features_used=[
            "monthly_income",
            emi_feature,
        ],
    )


# ============================================================
# Indicator 3
# Expense / Income Burden
# ============================================================


def score_expense_income_burden(
    data: Mapping[str, Any],
) -> IndicatorResult:

    monthly_income = _finite_number(data.get("monthly_income"))

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    if monthly_income is None or monthly_income <= 0:
        return IndicatorResult(
            name="expense_income_burden",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Monthly income is unavailable or invalid.",
            features_used=[],
        )

    if total_expense is None:
        return IndicatorResult(
            name="expense_income_burden",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Total expense information is unavailable.",
            features_used=["monthly_income"],
        )

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
        name="expense_income_burden",
        score=_round_score(score),
        coverage=1.0,
        status=IndicatorStatus.AVAILABLE,
        reason=("Total recurring expenses are evaluated relative to monthly income."),
        features_used=[
            "synthetic_total_expense",
            "monthly_income",
        ],
    )


# ============================================================
# Indicator 4
# Available Surplus
# ============================================================


def score_available_surplus(
    data: Mapping[str, Any],
) -> IndicatorResult:

    surplus = _finite_number(data.get("available_surplus"))

    monthly_income = _finite_number(data.get("monthly_income"))

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    total_emi = _finite_number(data.get("synthetic_total_emi"))

    if surplus is None:
        return IndicatorResult(
            name="available_surplus",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Available surplus is unavailable.",
            features_used=[],
        )

    # --------------------------------------------------------
    # Preferred: surplus relative to income.
    # --------------------------------------------------------

    if monthly_income is not None and monthly_income > 0:
        surplus_ratio = surplus / monthly_income

        if surplus_ratio < 0:
            score = 0.0

        elif surplus_ratio < 0.05:
            score = 25 * (surplus_ratio / 0.05)

        elif surplus_ratio < 0.10:
            score = 25 + 25 * ((surplus_ratio - 0.05) / 0.05)

        elif surplus_ratio < 0.20:
            score = 50 + 25 * ((surplus_ratio - 0.10) / 0.10)

        elif surplus_ratio < 0.30:
            score = 75 + 15 * ((surplus_ratio - 0.20) / 0.10)

        else:
            score = 100.0

        return IndicatorResult(
            name="available_surplus",
            score=_round_score(score),
            coverage=1.0,
            status=IndicatorStatus.AVAILABLE,
            reason=(
                "Available monthly surplus is evaluated relative to monthly income."
            ),
            features_used=[
                "available_surplus",
                "monthly_income",
            ],
        )

    # --------------------------------------------------------
    # Fallback: surplus relative to obligations.
    # --------------------------------------------------------

    if total_expense is not None and total_emi is not None:
        obligations = total_expense + total_emi

        if obligations > 0:
            surplus_ratio = surplus / obligations

            if surplus_ratio < 0:
                score = 0.0

            elif surplus_ratio < 0.05:
                score = 25 * (surplus_ratio / 0.05)

            elif surplus_ratio < 0.10:
                score = 25 + 25 * ((surplus_ratio - 0.05) / 0.05)

            elif surplus_ratio < 0.20:
                score = 50 + 25 * ((surplus_ratio - 0.10) / 0.10)

            elif surplus_ratio < 0.30:
                score = 75 + 15 * ((surplus_ratio - 0.20) / 0.10)

            else:
                score = 100.0

            return IndicatorResult(
                name="available_surplus",
                score=_round_score(score),
                coverage=0.75,
                status=IndicatorStatus.LIMITED,
                reason=(
                    "Surplus is evaluated relative to expenses "
                    "and EMI because income is unavailable."
                ),
                features_used=[
                    "available_surplus",
                    "synthetic_total_expense",
                    "synthetic_total_emi",
                ],
            )

    return IndicatorResult(
        name="available_surplus",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.LIMITED,
        reason=(
            "Surplus is available but no suitable denominator exists for normalization."
        ),
        features_used=["available_surplus"],
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

    # Redistribute unavailable indicator weights proportionally.
    total_weight = sum(INDICATOR_WEIGHTS[name] for name in usable)

    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / total_weight for name in usable
    }

    score = sum(usable[name].score * effective_weights[name] for name in usable)

    # Coverage is based on ORIGINAL weights.
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


def score_affordability(
    data: Mapping[str, Any],
) -> Dict[str, Any]:

    validation = validate_affordability_features(data)

    indicators = {
        "debt_to_income_burden": (score_debt_to_income_burden(data)),
        "emi_income_burden": (score_emi_income_burden(data)),
        "expense_income_burden": (score_expense_income_burden(data)),
        "available_surplus": (score_available_surplus(data)),
    }

    combined = combine_indicators(indicators)

    return {
        "component": "affordability",
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


def score_affordability_batch(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:

    return [score_affordability(record) for record in records]


# ============================================================
# Pandas Adapter
# ============================================================


def score_affordability_dataframe(df):
    """
    Score every row of a pandas DataFrame.

    Adds:

        affordability_score
        affordability_coverage
        affordability_status
        affordability_confidence
    """

    result_df = df.copy()

    scores = []
    coverages = []
    statuses = []
    confidences = []

    for _, row in result_df.iterrows():
        result = score_affordability(row.to_dict())

        scores.append(result["score"])
        coverages.append(result["coverage"])
        statuses.append(result["status"])
        confidences.append(result["confidence"])

    result_df["affordability_score"] = scores
    result_df["affordability_coverage"] = coverages
    result_df["affordability_status"] = statuses
    result_df["affordability_confidence"] = confidences

    return result_df


# ============================================================
# ML Feature Extraction
# ============================================================


def get_ml_features(
    data: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return engineered Affordability features suitable for a
    future supervised ML layer.

    No ML is trained or invoked.

    The eventual model should predict a genuine financial
    outcome rather than reproduce a synthetic FRIE score.
    """

    income = _finite_number(data.get("monthly_income"))

    current_dti = _finite_number(data.get("current_dti"))

    bureau_dti = _finite_number(data.get("bureau_dti"))

    current_loan_annuity = _finite_number(data.get("current_loan_annuity"))

    total_expense = _finite_number(data.get("synthetic_total_expense"))

    total_emi = _finite_number(data.get("synthetic_total_emi"))

    surplus = _finite_number(data.get("available_surplus"))

    emi_income_ratio = None

    if income is not None and income > 0 and current_loan_annuity is not None:
        emi_income_ratio = current_loan_annuity / income

    expense_income_ratio = None

    if income is not None and income > 0 and total_expense is not None:
        expense_income_ratio = total_expense / income

    surplus_income_ratio = None

    if income is not None and income > 0 and surplus is not None:
        surplus_income_ratio = surplus / income

    combined_dti = None

    dti_values = [
        value
        for value in [
            current_dti,
            bureau_dti,
        ]
        if value is not None
    ]

    if dti_values:
        combined_dti = sum(dti_values) / len(dti_values)

    return {
        "monthly_income": income,
        "current_dti": current_dti,
        "bureau_dti": bureau_dti,
        "combined_dti": combined_dti,
        "current_loan_annuity": current_loan_annuity,
        "emi_income_ratio": emi_income_ratio,
        "synthetic_total_expense": total_expense,
        "expense_income_ratio": expense_income_ratio,
        "synthetic_total_emi": total_emi,
        "available_surplus": surplus,
        "surplus_income_ratio": surplus_income_ratio,
        "current_credit_amount": _finite_number(data.get("current_credit_amount")),
        "goods_price": _finite_number(data.get("goods_price")),
    }


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    example = {
        "monthly_income": 75000,
        "current_dti": 0.24,
        "bureau_dti": 0.26,
        "current_loan_annuity": 12000,
        "synthetic_total_expense": 40000,
        "synthetic_total_emi": 12000,
        "available_surplus": 23000,
        "current_credit_amount": 450000,
        "goods_price": 500000,
    }

    result = score_affordability(example)

    print("\nAffordability")
    print("=============")

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

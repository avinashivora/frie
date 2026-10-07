"""
Cash-Flow Stability Scoring
===========================

FRIE Component: Cash-Flow Stability

Purpose
-------
Measures the consistency and stability of a person's cash flow over time.

Primary signals:
    1. Cash-Flow Consistency
    2. Negative-Cash-Flow Exposure
    3. Minimum Cash-Flow Strength
    4. Income Stability

This module intentionally does NOT directly score:
    - savings
    - EMI burden
    - DTI
    - available surplus
    - spending composition

Those are handled primarily by:
    - Financial Resilience
    - Affordability
    - Spending Behaviour

Output
------
Cash-Flow Stability score: 0–100

Missing-data semantics
----------------------
Missing != bad.

Possible states:
    AVAILABLE
    LIMITED
    NOT_ESTABLISHED
    UNAVAILABLE

If one indicator is unavailable, its weight is redistributed
proportionally across the available indicators.

Important
---------
The current FRIE dataset does not provide a complete historical
time-series length for cash flow. Therefore, this implementation
uses the supplied aggregate cash-flow indicators rather than
inventing an observation period.
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
    "cashflow_consistency": 0.35,
    "negative_cashflow_exposure": 0.25,
    "minimum_cashflow_strength": 0.20,
    "income_stability": 0.20,
}


# Features used by this component.
CASHFLOW_FEATURES = {
    "cash_flow_mean",
    "cash_flow_std",
    "cash_flow_min",
    "cash_flow_negative_months",
    "employment_years",
    "income_type",
    "contract_type",
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

    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_number(value: Any) -> Optional[float]:
    if not _is_numeric(value):
        return None

    value = float(value)

    if not math.isfinite(value):
        return None

    return value


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _round_score(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    return round(_clamp(value), 2)


# ============================================================
# Validation
# ============================================================


def validate_cashflow_features(
    data: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Validate only features relevant to Cash-Flow Stability.

    This does not modify the source data.
    """

    result = {}

    numeric_features = {
        "cash_flow_mean",
        "cash_flow_std",
        "cash_flow_min",
        "cash_flow_negative_months",
        "employment_years",
    }

    for feature in CASHFLOW_FEATURES:
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

            if (
                feature
                in {
                    "cash_flow_std",
                    "cash_flow_negative_months",
                    "employment_years",
                }
                and numeric_value < 0
            ):
                result[feature] = {
                    "state": FeatureState.INVALID.value,
                    "value": numeric_value,
                    "reason": "Value cannot be negative.",
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
# Scorecard Helpers
# ============================================================


def _threshold_score(
    value: float,
    thresholds: List[tuple[float, float]],
) -> float:
    """
    Piecewise threshold score.

    thresholds:
        [(value_1, score_1), (value_2, score_2), ...]

    The score corresponding to the greatest threshold <= value
    is returned.

    This is appropriate for monotonic risk indicators such as:
        volatility
        negative months
        weak minimum cash flow
    """

    score = thresholds[0][1]

    for threshold, threshold_score in thresholds:
        if value >= threshold:
            score = threshold_score
        else:
            break

    return _clamp(score)


def _lower_is_better_score(
    value: float,
    thresholds: List[tuple[float, float]],
) -> float:
    """
    Piecewise score where lower values are better.

    Example:
        volatility = 0       -> 100
        volatility = 0.10    -> 95
        volatility = 0.25    -> 80
        ...
    """

    for threshold, score in thresholds:
        if value <= threshold:
            return _clamp(score)

    return 0.0


# ============================================================
# Indicator 1
# Cash-Flow Consistency
# ============================================================


def score_cashflow_consistency(
    data: Mapping[str, Any],
) -> IndicatorResult:

    mean = _finite_number(data.get("cash_flow_mean"))
    std = _finite_number(data.get("cash_flow_std"))

    if mean is None and std is None:
        return IndicatorResult(
            name="cashflow_consistency",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No cash-flow history is available.",
            features_used=[],
        )

    if mean is None or std is None:
        return IndicatorResult(
            name="cashflow_consistency",
            score=None,
            coverage=0.5,
            status=IndicatorStatus.LIMITED,
            reason="Insufficient cash-flow statistics.",
            features_used=[
                feature
                for feature in [
                    "cash_flow_mean",
                    "cash_flow_std",
                ]
                if _finite_number(data.get(feature)) is not None
            ],
        )

    # Coefficient of variation.
    #
    # We use abs(mean) to avoid sign-related division problems.
    #
    # A near-zero mean combined with non-trivial volatility is
    # inherently unstable.
    denominator = abs(mean)

    if denominator < 1e-9:
        if std == 0:
            score = 50.0
        else:
            score = 0.0

    else:
        volatility = std / denominator

        # Lower volatility = better stability.
        score = _lower_is_better_score(
            volatility,
            [
                (0.05, 100),
                (0.10, 95),
                (0.20, 85),
                (0.30, 75),
                (0.50, 60),
                (0.75, 45),
                (1.00, 30),
                (1.50, 15),
            ],
        )

    return IndicatorResult(
        name="cashflow_consistency",
        score=_round_score(score),
        coverage=1.0,
        status=IndicatorStatus.AVAILABLE,
        reason="Cash-flow variability relative to mean cash flow.",
        features_used=[
            "cash_flow_mean",
            "cash_flow_std",
        ],
    )


# ============================================================
# Indicator 2
# Negative Cash-Flow Exposure
# ============================================================


def score_negative_cashflow_exposure(
    data: Mapping[str, Any],
) -> IndicatorResult:

    negative_months = _finite_number(data.get("cash_flow_negative_months"))

    if negative_months is None:
        return IndicatorResult(
            name="negative_cashflow_exposure",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Negative cash-flow history is unavailable.",
            features_used=[],
        )

    # The dataset provides the number of negative months but not
    # the observation-window length.
    #
    # Therefore we deliberately DO NOT convert this into a
    # negative-month percentage.
    #
    # The absolute count is used as supplied by the dataset.

    score = _lower_is_better_score(
        negative_months,
        [
            (0, 100),
            (1, 85),
            (2, 70),
            (3, 50),
            (4, 30),
            (6, 10),
        ],
    )

    return IndicatorResult(
        name="negative_cashflow_exposure",
        score=_round_score(score),
        coverage=1.0,
        status=IndicatorStatus.AVAILABLE,
        reason=(
            "Scores the observed count of negative cash-flow months; "
            "no observation-period denominator is assumed."
        ),
        features_used=[
            "cash_flow_negative_months",
        ],
    )


# ============================================================
# Indicator 3
# Minimum Cash-Flow Strength
# ============================================================


def score_minimum_cashflow_strength(
    data: Mapping[str, Any],
) -> IndicatorResult:

    minimum = _finite_number(data.get("cash_flow_min"))
    mean = _finite_number(data.get("cash_flow_mean"))
    std = _finite_number(data.get("cash_flow_std"))

    if minimum is None:
        return IndicatorResult(
            name="minimum_cashflow_strength",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Minimum cash-flow observation is unavailable.",
            features_used=[],
        )

    # Best case:
    # minimum cash flow is positive.
    #
    # If mean/std are also available, evaluate the minimum relative
    # to typical cash flow. This prevents raw rupee values from
    # becoming a scale-dependent score.
    if mean is not None and std is not None and std > 0:
        robust_position = (minimum - mean) / std

        # Convert the relative position into a score.
        #
        # Around the mean       -> ~80
        # 1 SD below mean       -> ~60
        # 2 SD below mean       -> ~40
        # 3 SD below mean       -> ~20
        # Very weak             -> 0
        #
        # This is a stability signal, not a profitability signal.

        if robust_position >= 0:
            score = 100.0
        elif robust_position >= -0.5:
            score = 85.0
        elif robust_position >= -1.0:
            score = 70.0
        elif robust_position >= -1.5:
            score = 55.0
        elif robust_position >= -2.0:
            score = 40.0
        elif robust_position >= -3.0:
            score = 20.0
        else:
            score = 0.0

        coverage = 1.0
        status = IndicatorStatus.AVAILABLE
        reason = (
            "Minimum cash flow evaluated relative to mean and cash-flow volatility."
        )

        features_used = [
            "cash_flow_min",
            "cash_flow_mean",
            "cash_flow_std",
        ]

    else:
        # If only minimum cash flow exists, use its sign as a
        # conservative standalone indicator.
        #
        # We avoid arbitrary rupee thresholds because the dataset
        # contains individuals with different income scales.

        if minimum > 0:
            score = 100.0
        elif minimum == 0:
            score = 50.0
        else:
            score = 0.0

        coverage = 0.5
        status = IndicatorStatus.LIMITED
        reason = (
            "Only minimum cash flow is available; relative "
            "cash-flow context is unavailable."
        )

        features_used = ["cash_flow_min"]

    return IndicatorResult(
        name="minimum_cashflow_strength",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=reason,
        features_used=features_used,
    )


# ============================================================
# Indicator 4
# Income Stability
# ============================================================


def score_income_stability(
    data: Mapping[str, Any],
) -> IndicatorResult:

    employment_years = _finite_number(data.get("employment_years"))

    income_type = data.get("income_type")
    contract_type = data.get("contract_type")

    available = 0
    score_components = []

    features_used = []

    # --------------------------------------------------------
    # Employment tenure
    # --------------------------------------------------------

    if employment_years is not None:
        available += 1
        features_used.append("employment_years")

        if employment_years >= 10:
            tenure_score = 100
        elif employment_years >= 7:
            tenure_score = 90
        elif employment_years >= 5:
            tenure_score = 80
        elif employment_years >= 3:
            tenure_score = 65
        elif employment_years >= 1:
            tenure_score = 45
        else:
            tenure_score = 25

        score_components.append(tenure_score)

    # --------------------------------------------------------
    # Income type
    # --------------------------------------------------------

    if not _is_missing(income_type):
        available += 1
        features_used.append("income_type")

        income_text = str(income_type).strip().lower()

        # These are intentionally broad categories.
        #
        # If the dataset contains different categorical labels,
        # unknown categories receive a neutral score rather than
        # being treated as risky.

        if any(
            token in income_text
            for token in [
                "pension",
                "retired",
            ]
        ):
            income_type_score = 90

        elif any(
            token in income_text
            for token in [
                "salary",
                "salaried",
                "employee",
            ]
        ):
            income_type_score = 90

        elif any(
            token in income_text
            for token in [
                "business",
                "self",
                "entrepreneur",
            ]
        ):
            income_type_score = 75

        elif any(
            token in income_text
            for token in [
                "contract",
                "freelance",
            ]
        ):
            income_type_score = 65

        else:
            # Unknown category:
            # don't infer that it is financially unstable.
            income_type_score = 70

        score_components.append(income_type_score)

    # --------------------------------------------------------
    # Contract type
    # --------------------------------------------------------

    if not _is_missing(contract_type):
        available += 1
        features_used.append("contract_type")

        contract_text = str(contract_type).strip().lower()

        if any(
            token in contract_text
            for token in [
                "permanent",
                "full-time",
                "full time",
                "regular",
            ]
        ):
            contract_score = 95

        elif any(
            token in contract_text
            for token in [
                "temporary",
                "contract",
                "fixed",
            ]
        ):
            contract_score = 65

        elif any(
            token in contract_text
            for token in [
                "part-time",
                "part time",
            ]
        ):
            contract_score = 70

        else:
            # Unknown category gets neutral treatment.
            contract_score = 70

        score_components.append(contract_score)

    if not score_components:
        return IndicatorResult(
            name="income_stability",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No employment or income-stability information is available.",
            features_used=[],
        )

    score = sum(score_components) / len(score_components)

    coverage = available / 3.0

    if coverage >= 0.999:
        status = IndicatorStatus.AVAILABLE
    else:
        status = IndicatorStatus.LIMITED

    return IndicatorResult(
        name="income_stability",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=(
            "Employment tenure and available income/contract "
            "information are used as stability signals."
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

    # Redistribute weights only among usable indicators.
    #
    # Example:
    # if consistency is missing, its 35% is proportionally
    # redistributed across the remaining indicators.

    total_weight = sum(INDICATOR_WEIGHTS[name] for name in usable)

    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / total_weight for name in usable
    }

    score = sum(usable[name].score * effective_weights[name] for name in usable)

    # Coverage is weighted by the ORIGINAL importance of each
    # indicator. This prevents a component from appearing fully
    # reliable simply because its remaining indicators scored well.
    coverage = sum(INDICATOR_WEIGHTS[name] * usable[name].coverage for name in usable)

    # Coverage cannot exceed the fraction of the original
    # indicator weight for which information was actually present.
    total_available_weight = sum(INDICATOR_WEIGHTS[name] for name in usable)

    if total_available_weight > 0:
        normalized_coverage = coverage
    else:
        normalized_coverage = 0.0

    if normalized_coverage >= 0.85:
        status = IndicatorStatus.AVAILABLE
    elif normalized_coverage > 0:
        status = IndicatorStatus.LIMITED
    else:
        status = IndicatorStatus.NOT_ESTABLISHED

    return {
        "score": _round_score(score),
        "coverage": round(_clamp(normalized_coverage, 0, 1), 4),
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

    coverage = _clamp(coverage * 100, 0, 100)

    if coverage >= 80:
        return "High"

    if coverage >= 50:
        return "Moderate"

    return "Low"


# ============================================================
# Main Scoring Function
# ============================================================


def score_cashflow_stability(
    data: Mapping[str, Any],
) -> Dict[str, Any]:

    validation = validate_cashflow_features(data)

    indicators = {
        "cashflow_consistency": score_cashflow_consistency(data),
        "negative_cashflow_exposure": score_negative_cashflow_exposure(data),
        "minimum_cashflow_strength": score_minimum_cashflow_strength(data),
        "income_stability": score_income_stability(data),
    }

    combined = combine_indicators(indicators)

    return {
        "component": "cashflow_stability",
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


def score_cashflow_batch(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:

    return [score_cashflow_stability(record) for record in records]


# ============================================================
# Pandas Adapter
# ============================================================


def score_cashflow_dataframe(df):
    """
    Score every row of a pandas DataFrame.

    Returns the original DataFrame with:
        cashflow_stability_score
        cashflow_stability_coverage
        cashflow_stability_status
        cashflow_stability_confidence
    """

    result_df = df.copy()

    scores = []
    coverages = []
    statuses = []
    confidences = []

    for _, row in result_df.iterrows():
        result = score_cashflow_stability(row.to_dict())

        scores.append(result["score"])
        coverages.append(result["coverage"])
        statuses.append(result["status"])
        confidences.append(result["confidence"])

    result_df["cashflow_stability_score"] = scores
    result_df["cashflow_stability_coverage"] = coverages
    result_df["cashflow_stability_status"] = statuses
    result_df["cashflow_stability_confidence"] = confidences

    return result_df


# ============================================================
# ML Feature Extraction
# ============================================================


def get_ml_features(
    data: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return engineered Cash-Flow Stability features suitable
    for a future supervised ML layer.

    This function does NOT train or invoke ML.

    ML should only be trained once FRIE has a genuine outcome
    label such as:
        - repayment/default outcome
        - delinquency event
        - policy payment lapse
        - another validated financial outcome

    It should NOT be trained simply to reproduce a synthetic
    FRIE score.
    """

    mean = _finite_number(data.get("cash_flow_mean"))
    std = _finite_number(data.get("cash_flow_std"))
    minimum = _finite_number(data.get("cash_flow_min"))

    if mean is not None and abs(mean) > 1e-9:
        volatility_ratio = std / abs(mean) if std is not None else None
    else:
        volatility_ratio = None

    minimum_zscore = None

    if minimum is not None and mean is not None and std is not None and std > 0:
        minimum_zscore = (minimum - mean) / std

    return {
        "cash_flow_mean": mean,
        "cash_flow_std": std,
        "cash_flow_min": minimum,
        "cash_flow_negative_months": _finite_number(
            data.get("cash_flow_negative_months")
        ),
        "cashflow_volatility_ratio": volatility_ratio,
        "minimum_cashflow_zscore": minimum_zscore,
        "employment_years": _finite_number(data.get("employment_years")),
    }


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    example = {
        "cash_flow_mean": 45000,
        "cash_flow_std": 7000,
        "cash_flow_min": 31000,
        "cash_flow_negative_months": 0,
        "employment_years": 5,
        "income_type": "Salary",
        "contract_type": "Permanent",
    }

    result = score_cashflow_stability(example)

    print("\nCash-Flow Stability")
    print("===================")

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

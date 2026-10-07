"""
Financial Resilience Scoring
============================

FRIE Component: Financial Resilience

Purpose
-------
Measures the ability of an individual to absorb financial shocks
using available liquidity, savings capacity, long-term assets,
and recurring financial surplus.

Output
------
Financial Resilience score: 0–100

Primary indicators
------------------
    1. Liquidity Buffer          35%
    2. Savings Capacity          25%
    3. Long-Term Asset Buffer    20%
    4. Surplus Resilience        20%

Design principles
-----------------
- Missing != zero.
- No financial history is not automatically a poor score.
- Liquid resources are more useful for immediate shocks than
  long-term assets.
- Large balances receive diminishing marginal benefit.
- Affordability variables are used only where necessary to
  establish the size of the financial buffer.
- Demographic/context variables are not directly scored.

This module does not train or invoke ML.
A future supervised ML layer should only be introduced once
FRIE has a genuine financial outcome label.
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
    "liquidity_buffer": 0.35,
    "savings_capacity": 0.25,
    "long_term_asset_buffer": 0.20,
    "surplus_resilience": 0.20,
}


RESILIENCE_FEATURES = {
    # Liquidity
    "savings_balance",
    "fd_amount",
    "rd_contribution",
    # Savings capacity
    "monthly_savings",
    "savings_rate",
    # Long-term assets
    "mutual_fund_balance",
    "ppf_contribution",
    "nps_contribution",
    "sip_contribution",
    # Buffer denominator / surplus
    "synthetic_total_expense",
    "synthetic_total_emi",
    "available_surplus",
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


def validate_resilience_features(
    data: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Validate only features relevant to Financial Resilience.

    Validation does not modify source data.
    """

    result = {}

    numeric_features = {
        "savings_balance",
        "fd_amount",
        "rd_contribution",
        "monthly_savings",
        "savings_rate",
        "mutual_fund_balance",
        "ppf_contribution",
        "nps_contribution",
        "sip_contribution",
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
    }

    for feature in RESILIENCE_FEATURES:
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

            # Financial balances and expense values cannot be
            # negative.
            if feature != "available_surplus" and numeric_value < 0:
                result[feature] = {
                    "state": FeatureState.INVALID.value,
                    "value": numeric_value,
                    "reason": "Value cannot be negative.",
                }

                continue

            # Savings rate is a ratio and should normally be
            # between 0 and 1 in this dataset.
            if feature == "savings_rate" and not 0 <= numeric_value <= 1:
                result[feature] = {
                    "state": FeatureState.INVALID.value,
                    "value": numeric_value,
                    "reason": "Savings rate must be between 0 and 1.",
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
# Utility Scoring Functions
# ============================================================


def _buffer_score(
    months: float,
) -> float:
    """
    Score a financial buffer expressed in months of obligations.

    The thresholds intentionally have diminishing returns.

    0 months       -> 0
    0.5 months     -> 20
    1 month        -> 40
    2 months       -> 65
    3 months       -> 80
    6 months       -> 95
    9+ months      -> 100

    This avoids allowing extremely large balances to dominate
    the resilience score.
    """

    if months <= 0:
        return 0.0

    if months < 0.5:
        return 20 * (months / 0.5)

    if months < 1:
        return 20 + 20 * ((months - 0.5) / 0.5)

    if months < 2:
        return 40 + 25 * ((months - 1) / 1)

    if months < 3:
        return 65 + 15 * ((months - 2) / 1)

    if months < 6:
        return 80 + 15 * ((months - 3) / 3)

    if months < 9:
        return 95 + 5 * ((months - 6) / 3)

    return 100.0


def _savings_rate_score(
    savings_rate: float,
) -> float:
    """
    Score savings capacity.

    Higher savings rate is generally better, but the benefit
    plateaus rather than increasing indefinitely.
    """

    if savings_rate <= 0:
        return 0.0

    if savings_rate < 0.05:
        return 20 * (savings_rate / 0.05)

    if savings_rate < 0.10:
        return 20 + 20 * ((savings_rate - 0.05) / 0.05)

    if savings_rate < 0.20:
        return 40 + 25 * ((savings_rate - 0.10) / 0.10)

    if savings_rate < 0.30:
        return 65 + 20 * ((savings_rate - 0.20) / 0.10)

    if savings_rate < 0.40:
        return 85 + 10 * ((savings_rate - 0.30) / 0.10)

    return 100.0


def _surplus_score(
    surplus_ratio: float,
) -> float:
    """
    Score recurring surplus relative to monthly obligations.

    The ratio is:

        available_surplus /
        (synthetic_total_expense + synthetic_total_emi)

    A positive recurring surplus indicates capacity to absorb
    ordinary financial shocks.
    """

    if surplus_ratio < 0:
        return 0.0

    if surplus_ratio < 0.05:
        return 25 * (surplus_ratio / 0.05)

    if surplus_ratio < 0.10:
        return 25 + 25 * ((surplus_ratio - 0.05) / 0.05)

    if surplus_ratio < 0.20:
        return 50 + 25 * ((surplus_ratio - 0.10) / 0.10)

    if surplus_ratio < 0.30:
        return 75 + 15 * ((surplus_ratio - 0.20) / 0.10)

    return 100.0


# ============================================================
# Indicator 1
# Liquidity Buffer
# ============================================================


def score_liquidity_buffer(
    data: Mapping[str, Any],
) -> IndicatorResult:

    liquid_components = [
        "savings_balance",
        "fd_amount",
        "rd_contribution",
    ]

    available_assets = []
    features_used = []

    for feature in liquid_components:
        value = _finite_number(data.get(feature))

        if value is not None:
            available_assets.append(value)
            features_used.append(feature)

    if not available_assets:
        return IndicatorResult(
            name="liquidity_buffer",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No liquid savings or deposit information is available.",
            features_used=[],
        )

    expense = _finite_number(data.get("synthetic_total_expense"))

    emi = _finite_number(data.get("synthetic_total_emi"))

    liquid_assets = sum(available_assets)

    # We need a denominator to express liquidity as months of
    # financial obligations.
    if expense is not None and emi is not None:
        monthly_obligations = expense + emi

        if monthly_obligations > 0:
            buffer_months = liquid_assets / monthly_obligations

            score = _buffer_score(buffer_months)

            coverage = len(available_assets) / 3.0

            return IndicatorResult(
                name="liquidity_buffer",
                score=_round_score(score),
                coverage=coverage,
                status=(
                    IndicatorStatus.AVAILABLE
                    if coverage >= 0.99
                    else IndicatorStatus.LIMITED
                ),
                reason=(
                    "Liquid financial resources are expressed as "
                    "months of current expenses and EMI obligations."
                ),
                features_used=features_used
                + [
                    "synthetic_total_expense",
                    "synthetic_total_emi",
                ],
            )

    # --------------------------------------------------------
    # Fallback when obligation denominator is unavailable
    # --------------------------------------------------------
    #
    # We cannot responsibly convert a raw ₹ balance into a
    # resilience score without knowing the scale of the user's
    # obligations.
    #
    # Therefore we return LIMITED rather than inventing a
    # universal rupee threshold.

    return IndicatorResult(
        name="liquidity_buffer",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.LIMITED,
        reason=(
            "Liquid assets are available but the expense/EMI "
            "denominator needed to measure the buffer is missing."
        ),
        features_used=features_used,
    )


# ============================================================
# Indicator 2
# Savings Capacity
# ============================================================


def score_savings_capacity(
    data: Mapping[str, Any],
) -> IndicatorResult:

    savings_rate = _finite_number(data.get("savings_rate"))

    monthly_savings = _finite_number(data.get("monthly_savings"))

    components = []
    features_used = []

    if savings_rate is not None:
        components.append(_savings_rate_score(savings_rate))

        features_used.append("savings_rate")

    if monthly_savings is not None:
        # A raw monthly savings amount is deliberately not scored
        # using a universal rupee threshold.
        #
        # Without income normalization, ₹20,000 savings means
        # something very different for two different earners.
        #
        # Therefore this feature contributes as contextual
        # evidence only when savings_rate is unavailable.

        if savings_rate is None:
            if monthly_savings > 0:
                monthly_score = 70.0
            elif monthly_savings == 0:
                monthly_score = 40.0
            else:
                monthly_score = 0.0

            components.append(monthly_score)

        features_used.append("monthly_savings")

    if not components:
        return IndicatorResult(
            name="savings_capacity",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No savings-capacity information is available.",
            features_used=[],
        )

    score = sum(components) / len(components)

    if savings_rate is not None:
        coverage = 1.0
        status = IndicatorStatus.AVAILABLE

    else:
        coverage = 0.5
        status = IndicatorStatus.LIMITED

    return IndicatorResult(
        name="savings_capacity",
        score=_round_score(score),
        coverage=coverage,
        status=status,
        reason=(
            "Savings rate is the primary normalized measure of "
            "ongoing savings capacity."
        ),
        features_used=features_used,
    )


# ============================================================
# Indicator 3
# Long-Term Asset Buffer
# ============================================================


def score_long_term_asset_buffer(
    data: Mapping[str, Any],
) -> IndicatorResult:

    asset_features = [
        "mutual_fund_balance",
        "ppf_contribution",
        "nps_contribution",
    ]

    assets = []
    features_used = []

    for feature in asset_features:
        value = _finite_number(data.get(feature))

        if value is not None:
            assets.append(value)
            features_used.append(feature)

    if not assets:
        return IndicatorResult(
            name="long_term_asset_buffer",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="No long-term investment asset information is available.",
            features_used=[],
        )

    total_assets = sum(assets)

    # --------------------------------------------------------
    # Prefer relative asset strength where income is available.
    # --------------------------------------------------------
    #
    # This prevents wealthy/high-income individuals and lower-
    # income individuals from being compared using raw balances.
    #
    # Annual income is approximated from monthly income if it
    # exists in the dataset.
    #
    # This is a resilience context measure, not an investment-
    # performance measure.

    monthly_income = _finite_number(data.get("monthly_income"))

    if monthly_income is not None and monthly_income > 0:
        annual_income = monthly_income * 12

        asset_to_income = total_assets / annual_income

        if asset_to_income <= 0:
            score = 0.0

        elif asset_to_income < 0.25:
            score = 25 + (25 * asset_to_income / 0.25)

        elif asset_to_income < 0.50:
            score = 50 + (15 * (asset_to_income - 0.25) / 0.25)

        elif asset_to_income < 1.0:
            score = 65 + (15 * (asset_to_income - 0.50) / 0.50)

        elif asset_to_income < 2.0:
            score = 80 + (15 * (asset_to_income - 1.0) / 1.0)

        else:
            score = 100.0

        coverage = len(assets) / 3.0

        return IndicatorResult(
            name="long_term_asset_buffer",
            score=_round_score(score),
            coverage=coverage,
            status=(
                IndicatorStatus.AVAILABLE
                if coverage >= 0.99
                else IndicatorStatus.LIMITED
            ),
            reason=(
                "Long-term assets are evaluated relative to "
                "annual income to avoid raw-balance bias."
            ),
            features_used=features_used + ["monthly_income"],
        )

    # --------------------------------------------------------
    # No income denominator
    # --------------------------------------------------------
    #
    # Raw assets alone are insufficient for a reliable resilience
    # score, so return a limited state rather than inventing
    # arbitrary rupee thresholds.

    return IndicatorResult(
        name="long_term_asset_buffer",
        score=None,
        coverage=0.0,
        status=IndicatorStatus.LIMITED,
        reason=(
            "Long-term assets are available but monthly income "
            "is unavailable for normalization."
        ),
        features_used=features_used,
    )


# ============================================================
# Indicator 4
# Surplus Resilience
# ============================================================


def score_surplus_resilience(
    data: Mapping[str, Any],
) -> IndicatorResult:

    surplus = _finite_number(data.get("available_surplus"))

    expense = _finite_number(data.get("synthetic_total_expense"))

    emi = _finite_number(data.get("synthetic_total_emi"))

    if surplus is None:
        return IndicatorResult(
            name="surplus_resilience",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED,
            reason="Available surplus is unavailable.",
            features_used=[],
        )

    if expense is None or emi is None:
        # The raw surplus is informative, but cannot be reliably
        # compared across people without a denominator.

        return IndicatorResult(
            name="surplus_resilience",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.LIMITED,
            reason=(
                "Available surplus exists, but expense and EMI "
                "information is insufficient for normalization."
            ),
            features_used=["available_surplus"],
        )

    obligations = expense + emi

    if obligations <= 0:
        return IndicatorResult(
            name="surplus_resilience",
            score=None,
            coverage=0.0,
            status=IndicatorStatus.LIMITED,
            reason="Financial obligation denominator is zero or invalid.",
            features_used=[
                "available_surplus",
                "synthetic_total_expense",
                "synthetic_total_emi",
            ],
        )

    surplus_ratio = surplus / obligations

    score = _surplus_score(surplus_ratio)

    return IndicatorResult(
        name="surplus_resilience",
        score=_round_score(score),
        coverage=1.0,
        status=IndicatorStatus.AVAILABLE,
        reason=(
            "Recurring surplus is evaluated relative to monthly "
            "expense and EMI obligations."
        ),
        features_used=[
            "available_surplus",
            "synthetic_total_expense",
            "synthetic_total_emi",
        ],
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

    # Dynamic redistribution of unavailable indicator weights.
    total_weight = sum(INDICATOR_WEIGHTS[name] for name in usable)

    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / total_weight for name in usable
    }

    score = sum(usable[name].score * effective_weights[name] for name in usable)

    # Coverage remains tied to original weights.
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


def score_financial_resilience(
    data: Mapping[str, Any],
) -> Dict[str, Any]:

    validation = validate_resilience_features(data)

    indicators = {
        "liquidity_buffer": score_liquidity_buffer(data),
        "savings_capacity": score_savings_capacity(data),
        "long_term_asset_buffer": score_long_term_asset_buffer(data),
        "surplus_resilience": score_surplus_resilience(data),
    }

    combined = combine_indicators(indicators)

    return {
        "component": "financial_resilience",
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


def score_resilience_batch(
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:

    return [score_financial_resilience(record) for record in records]


# ============================================================
# Pandas Adapter
# ============================================================


def score_resilience_dataframe(df):
    """
    Score every row of a pandas DataFrame.

    Returns the original DataFrame with:

        financial_resilience_score
        financial_resilience_coverage
        financial_resilience_status
        financial_resilience_confidence
    """

    result_df = df.copy()

    scores = []
    coverages = []
    statuses = []
    confidences = []

    for _, row in result_df.iterrows():
        result = score_financial_resilience(row.to_dict())

        scores.append(result["score"])
        coverages.append(result["coverage"])
        statuses.append(result["status"])
        confidences.append(result["confidence"])

    result_df["financial_resilience_score"] = scores
    result_df["financial_resilience_coverage"] = coverages
    result_df["financial_resilience_status"] = statuses
    result_df["financial_resilience_confidence"] = confidences

    return result_df


# ============================================================
# ML Feature Extraction
# ============================================================


def get_ml_features(
    data: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return engineered Financial Resilience features suitable
    for a future supervised ML layer.

    No ML is trained or invoked here.

    A future model should use a genuine financial outcome label,
    rather than learning to reproduce the synthetic FRIE score.
    """

    savings_balance = _finite_number(data.get("savings_balance"))

    fd_amount = _finite_number(data.get("fd_amount"))

    rd_contribution = _finite_number(data.get("rd_contribution"))

    liquid_assets = None

    if any(
        value is not None
        for value in [
            savings_balance,
            fd_amount,
            rd_contribution,
        ]
    ):
        liquid_assets = sum(
            value or 0
            for value in [
                savings_balance,
                fd_amount,
                rd_contribution,
            ]
        )

    expense = _finite_number(data.get("synthetic_total_expense"))

    emi = _finite_number(data.get("synthetic_total_emi"))

    monthly_income = _finite_number(data.get("monthly_income"))

    obligations = None

    if expense is not None and emi is not None:
        obligations = expense + emi

    liquidity_months = None

    if liquid_assets is not None and obligations is not None and obligations > 0:
        liquidity_months = liquid_assets / obligations

    long_term_assets = sum(
        value or 0
        for value in [
            _finite_number(data.get("mutual_fund_balance")),
            _finite_number(data.get("ppf_contribution")),
            _finite_number(data.get("nps_contribution")),
        ]
    )

    asset_to_income = None

    if monthly_income is not None and monthly_income > 0:
        asset_to_income = long_term_assets / (monthly_income * 12)

    surplus = _finite_number(data.get("available_surplus"))

    surplus_ratio = None

    if surplus is not None and obligations is not None and obligations > 0:
        surplus_ratio = surplus / obligations

    return {
        "liquid_assets": liquid_assets,
        "liquidity_buffer_months": liquidity_months,
        "monthly_savings": _finite_number(data.get("monthly_savings")),
        "savings_rate": _finite_number(data.get("savings_rate")),
        "long_term_assets": long_term_assets,
        "long_term_assets_to_annual_income": asset_to_income,
        "available_surplus": surplus,
        "surplus_ratio": surplus_ratio,
    }


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    example = {
        "monthly_income": 75000,
        "savings_balance": 180000,
        "fd_amount": 100000,
        "rd_contribution": 5000,
        "monthly_savings": 15000,
        "savings_rate": 0.20,
        "mutual_fund_balance": 250000,
        "ppf_contribution": 50000,
        "nps_contribution": 30000,
        "synthetic_total_expense": 40000,
        "synthetic_total_emi": 10000,
        "available_surplus": 25000,
    }

    result = score_financial_resilience(example)

    print("\nFinancial Resilience")
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

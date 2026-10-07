"""
FRIE - Commitment Adherence Scoring
====================================

Siloed implementation for the Commitment Adherence dimension.

Output:
    Commitment Adherence Score: 0-100

Design:
    RAW FEATURES
        ↓
    Validation
        ↓
    Feature state classification
        ↓
    Derived indicators
        ↓
    Indicator-level normalization
        ↓
    Missing/invalid feature handling
        ↓
    Dynamic weight redistribution
        ↓
    Commitment Adherence Score
        ↓
    Coverage + Status + Confidence + Explanation

Important:
    Missing data is NOT treated as zero.
    Invalid data is NOT treated as zero.
    Unestablished behaviour is NOT treated as poor behaviour.

Current ML decision:
    No ML model is trained here because the supplied FRIE dataset does not
    contain a genuine future commitment-failure/default outcome label.

    A future ML calibration layer can consume the derived indicators and
    predict an empirically observed outcome such as missed_payment_90d.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional


# ============================================================================
# 1. STATES
# ============================================================================


class FeatureState(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_ESTABLISHED = "not_established"


class IndicatorStatus(str, Enum):
    AVAILABLE = "available"
    LIMITED = "limited"
    NOT_ESTABLISHED = "not_established"
    UNAVAILABLE = "unavailable"


# ============================================================================
# 2. RESULT OBJECTS
# ============================================================================


@dataclass
class IndicatorResult:
    """
    Result for an individual commitment indicator.

    score:
        0-100 if calculable.

    coverage:
        0-1 indicating how much of the indicator's evidence was available.

    status:
        available / limited / not_established / unavailable

    used_features:
        Features that actually contributed.

    missing_features:
        Expected features that were absent.

    invalid_features:
        Features that were present but invalid.
    """

    score: Optional[float]
    coverage: float
    status: str
    used_features: list[str]
    missing_features: list[str]
    invalid_features: list[str]


# ============================================================================
# 3. FEATURE DEFINITIONS
# ============================================================================

# Features directly relevant to Commitment Adherence.
#
# Some are used only as supporting inputs for derived ratios rather than being
# independently scored. This prevents double counting.

PAYMENT_FEATURES = (
    "on_time_payment_ratio",
    "payment_coverage_ratio",
    "total_late_payments",
    "total_on_time_payments",
    "total_installments",
    "average_payment_delay",
    "total_payment_delay_days",
    "payment_difference",
    "total_amount_due",
    "total_amount_paid",
)

DELINQUENCY_FEATURES = (
    "bureau_overdue_ratio",
    "bureau_overdue_days",
    "bureau_overdue_account_count",
    "bureau_overdue_amount",
    "credit_prolongation_count",
    "max_card_dpd",
    "max_card_dpd_default",
    "pos_dpd_count",
    "max_pos_dpd",
    "max_pos_dpd_default",
)

RECURRING_FEATURES = (
    "current_loan_annuity",
    "synthetic_total_emi",
    "avg_minimum_payment",
    "total_amount_due",
    "total_amount_paid",
)

INSURANCE_FEATURES = (
    "health_insurance",
    "life_insurance",
    "insurance_premium",
    "insurance_payment_consistency",
)


# ============================================================================
# 4. INDICATOR WEIGHTS
# ============================================================================

# These are weights BETWEEN indicators.
#
# Insurance is deliberately optional. If insurance history does not exist,
# its 15% is redistributed to the available indicators.

INDICATOR_WEIGHTS = {
    "payment_reliability": 0.40,
    "delinquency_management": 0.25,
    "recurring_commitment": 0.20,
    "insurance_adherence": 0.15,
}


# Weights INSIDE each indicator.
#
# Important:
#   total_amount_paid / total_amount_due
#   is represented through payment_coverage_ratio where available.
#
# Therefore source columns are not independently rewarded again.

PAYMENT_RELIABILITY_WEIGHTS = {
    "on_time_payment_ratio": 0.30,
    "payment_coverage_ratio": 0.30,
    "late_payment_frequency": 0.15,
    "average_payment_delay": 0.10,
    "payment_gap": 0.15,
}


DELINQUENCY_WEIGHTS = {
    "bureau_overdue_ratio": 0.25,
    "bureau_overdue_days": 0.20,
    "bureau_overdue_accounts": 0.15,
    "bureau_overdue_amount": 0.10,
    "credit_prolongation": 0.10,
    "card_dpd": 0.10,
    "pos_dpd": 0.10,
}


RECURRING_COMMITMENT_WEIGHTS = {
    "payment_fulfillment": 0.70,
    "recurring_payment_consistency": 0.30,
}


INSURANCE_WEIGHTS = {
    "insurance_payment_consistency": 0.80,
    "insurance_history_presence": 0.20,
}


# ============================================================================
# 5. GENERAL UTILITIES
# ============================================================================


def is_missing(value: Any) -> bool:
    """Return True for None/NaN values."""

    if value is None:
        return True

    if isinstance(value, float) and math.isnan(value):
        return True

    return False


def is_finite_number(value: Any) -> bool:
    """Return True if value is a finite numeric value."""

    if isinstance(value, bool):
        return False

    try:
        value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(value)


def safe_float(value: Any) -> Optional[float]:
    """Convert a value to finite float or return None."""

    if is_missing(value):
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def clip_0_100(value: Optional[float]) -> Optional[float]:
    """Clip a score to the FRIE 0-100 range."""

    if value is None:
        return None

    return max(0.0, min(100.0, float(value)))


# ============================================================================
# 6. FEATURE VALIDATION
# ============================================================================


def validate_feature(
    row: Mapping[str, Any],
    feature: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> FeatureState:
    """
    Classify a feature.

    Missing:
        Feature absent or null.

    Invalid:
        Feature exists but violates its expected numeric range.

    Available:
        Valid usable value.

    Not established:
        Determined separately where a behaviour genuinely does not exist.
    """

    if feature not in row:
        return FeatureState.MISSING

    value = row.get(feature)

    if is_missing(value):
        return FeatureState.MISSING

    numeric = safe_float(value)

    if numeric is None:
        return FeatureState.INVALID

    if minimum is not None and numeric < minimum:
        return FeatureState.INVALID

    if maximum is not None and numeric > maximum:
        return FeatureState.INVALID

    return FeatureState.AVAILABLE


def validate_row(row: Mapping[str, Any]) -> Dict[str, FeatureState]:
    """
    Validate all commitment-related raw features.

    The function intentionally does not silently repair invalid values.
    """

    states: Dict[str, FeatureState] = {}

    bounded_0_1 = {
        "on_time_payment_ratio",
        "payment_coverage_ratio",
        "insurance_payment_consistency",
    }

    nonnegative = {
        "total_late_payments",
        "total_on_time_payments",
        "total_installments",
        "average_payment_delay",
        "total_payment_delay_days",
        "payment_difference",
        "total_amount_due",
        "total_amount_paid",
        "bureau_overdue_ratio",
        "bureau_overdue_days",
        "bureau_overdue_account_count",
        "bureau_overdue_amount",
        "credit_prolongation_count",
        "max_card_dpd",
        "max_card_dpd_default",
        "pos_dpd_count",
        "max_pos_dpd",
        "max_pos_dpd_default",
        "current_loan_annuity",
        "synthetic_total_emi",
        "avg_minimum_payment",
        "insurance_premium",
    }

    binary = {
        "health_insurance",
        "life_insurance",
    }

    for feature in PAYMENT_FEATURES + DELINQUENCY_FEATURES + RECURRING_FEATURES:
        if feature in bounded_0_1:
            states[feature] = validate_feature(
                row,
                feature,
                minimum=0.0,
                maximum=1.0,
            )
        elif feature in nonnegative:
            states[feature] = validate_feature(
                row,
                feature,
                minimum=0.0,
            )

    for feature in INSURANCE_FEATURES:
        if feature in bounded_0_1:
            states[feature] = validate_feature(
                row,
                feature,
                minimum=0.0,
                maximum=1.0,
            )
        elif feature in binary:
            states[feature] = validate_feature(
                row,
                feature,
                minimum=0.0,
                maximum=1.0,
            )
        else:
            states[feature] = validate_feature(
                row,
                feature,
                minimum=0.0,
            )

    return states


# ============================================================================
# 7. NORMALIZATION FUNCTIONS
# ============================================================================


def ratio_score(value: Optional[float]) -> Optional[float]:
    """
    Convert a 0-1 reliability ratio to 0-100.
    """

    if value is None:
        return None

    return clip_0_100(value * 100.0)


def inverse_threshold_score(
    value: Optional[float],
    thresholds: list[tuple[float, float]],
) -> Optional[float]:
    """
    Lower-is-better threshold scoring.

    thresholds:
        [(maximum_value, score), ...]

    Example:
        0 days   -> 100
        <=7 days -> 90
        <=30     -> 70
        ...
    """

    if value is None:
        return None

    for limit, score in thresholds:
        if value <= limit:
            return float(score)

    return 0.0


def weighted_mean(
    values: Mapping[str, Optional[float]],
    weights: Mapping[str, float],
) -> tuple[Optional[float], float]:
    """
    Weighted average with dynamic redistribution.

    Returns:
        score, coverage

    coverage:
        fraction of the original indicator weight that was available.
    """

    total_weight = sum(weights.values())

    if total_weight <= 0:
        return None, 0.0

    valid = {
        key: value
        for key, value in values.items()
        if value is not None and is_finite_number(value) and key in weights
    }

    if not valid:
        return None, 0.0

    available_weight = sum(weights[key] for key in valid)

    score = sum(float(valid[key]) * weights[key] for key in valid) / available_weight

    coverage = available_weight / total_weight

    return clip_0_100(score), coverage


# ============================================================================
# 8. DERIVED FEATURE CALCULATIONS
# ============================================================================


def calculate_payment_fulfillment_ratio(
    row: Mapping[str, Any],
) -> Optional[float]:
    """
    total_amount_paid / total_amount_due

    Capped at 1.0 because paying above the required amount should not create
    an artificial reliability score above 100.
    """

    paid = safe_float(row.get("total_amount_paid"))
    due = safe_float(row.get("total_amount_due"))

    if paid is None or due is None or due <= 0:
        return None

    return min(max(paid / due, 0.0), 1.0)


def calculate_late_payment_frequency(
    row: Mapping[str, Any],
) -> Optional[float]:
    """
    total_late_payments / total_installments

    Lower is better.
    """

    late = safe_float(row.get("total_late_payments"))
    installments = safe_float(row.get("total_installments"))

    if late is None or installments is None or installments <= 0:
        return None

    return max(0.0, late / installments)


def calculate_payment_gap_ratio(
    row: Mapping[str, Any],
) -> Optional[float]:
    """
    Measures underpayment only.

    payment_difference =
        required amount - actual amount paid

    Positive:
        underpayment

    Zero:
        exact payment

    Negative:
        overpayment

    Overpayment is not rewarded beyond a perfect score.
    """

    difference = safe_float(row.get("payment_difference"))
    due = safe_float(row.get("total_amount_due"))

    if difference is None or due is None or due <= 0:
        return None

    return max(difference, 0.0) / due


def calculate_delinquency_features(
    row: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Build normalized delinquency inputs.
    """

    overdue_ratio = safe_float(row.get("bureau_overdue_ratio"))

    if overdue_ratio is None:
        overdue_amount = safe_float(row.get("bureau_overdue_amount"))
        credit_amount = safe_float(row.get("bureau_credit_amount"))

        if (
            overdue_amount is not None
            and credit_amount is not None
            and credit_amount > 0
        ):
            overdue_ratio = overdue_amount / credit_amount

    return {
        "bureau_overdue_ratio": overdue_ratio,
        "bureau_overdue_days": safe_float(row.get("bureau_overdue_days")),
        "bureau_overdue_accounts": safe_float(row.get("bureau_overdue_account_count")),
        "bureau_overdue_amount": safe_float(row.get("bureau_overdue_amount")),
        "credit_prolongation": safe_float(row.get("credit_prolongation_count")),
        "card_dpd": safe_float(row.get("max_card_dpd")),
        "pos_dpd": safe_float(row.get("max_pos_dpd")),
    }


# ============================================================================
# 9. PAYMENT RELIABILITY
# ============================================================================


def score_payment_reliability(
    row: Mapping[str, Any],
) -> IndicatorResult:
    """
    Score payment reliability from 0-100.

    Components:
        on-time ratio
        payment coverage
        late-payment frequency
        average delay
        payment gap
    """

    values: Dict[str, Optional[float]] = {}

    on_time = safe_float(row.get("on_time_payment_ratio"))
    if on_time is not None and 0 <= on_time <= 1:
        values["on_time_payment_ratio"] = ratio_score(on_time)

    coverage = safe_float(row.get("payment_coverage_ratio"))
    if coverage is not None and 0 <= coverage <= 1:
        values["payment_coverage_ratio"] = ratio_score(coverage)

    late_frequency = calculate_late_payment_frequency(row)

    if late_frequency is not None:
        values["late_payment_frequency"] = inverse_threshold_score(
            late_frequency,
            [
                (0.00, 100),
                (0.02, 95),
                (0.05, 85),
                (0.10, 70),
                (0.20, 50),
                (0.35, 25),
                (float("inf"), 0),
            ],
        )

    delay = safe_float(row.get("average_payment_delay"))

    if delay is not None:
        values["average_payment_delay"] = inverse_threshold_score(
            delay,
            [
                (0, 100),
                (7, 90),
                (30, 70),
                (60, 50),
                (90, 25),
                (180, 10),
                (float("inf"), 0),
            ],
        )

    gap = calculate_payment_gap_ratio(row)

    if gap is not None:
        values["payment_gap"] = inverse_threshold_score(
            gap,
            [
                (0.00, 100),
                (0.05, 90),
                (0.10, 75),
                (0.25, 50),
                (0.50, 25),
                (float("inf"), 0),
            ],
        )

    score, coverage = weighted_mean(
        values,
        PAYMENT_RELIABILITY_WEIGHTS,
    )

    expected = set(PAYMENT_RELIABILITY_WEIGHTS.keys())
    used = set(values.keys())

    missing = sorted(expected - used)

    if score is None:
        status = IndicatorStatus.UNAVAILABLE.value
    elif coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE.value
    else:
        status = IndicatorStatus.LIMITED.value

    return IndicatorResult(
        score=score,
        coverage=coverage,
        status=status,
        used_features=sorted(used),
        missing_features=missing,
        invalid_features=[],
    )


# ============================================================================
# 10. DELINQUENCY MANAGEMENT
# ============================================================================


def score_delinquency_management(
    row: Mapping[str, Any],
) -> IndicatorResult:
    """
    Score delinquency behaviour.

    Lower delinquency = higher score.
    """

    raw = calculate_delinquency_features(row)

    values: Dict[str, Optional[float]] = {}

    if raw["bureau_overdue_ratio"] is not None:
        values["bureau_overdue_ratio"] = inverse_threshold_score(
            raw["bureau_overdue_ratio"],
            [
                (0.00, 100),
                (0.02, 85),
                (0.05, 70),
                (0.10, 50),
                (0.20, 25),
                (float("inf"), 0),
            ],
        )

    if raw["bureau_overdue_days"] is not None:
        values["bureau_overdue_days"] = inverse_threshold_score(
            raw["bureau_overdue_days"],
            [
                (0, 100),
                (7, 90),
                (30, 70),
                (60, 50),
                (90, 25),
                (180, 10),
                (float("inf"), 0),
            ],
        )

    if raw["bureau_overdue_accounts"] is not None:
        values["bureau_overdue_accounts"] = inverse_threshold_score(
            raw["bureau_overdue_accounts"],
            [
                (0, 100),
                (1, 75),
                (2, 50),
                (3, 25),
                (float("inf"), 0),
            ],
        )

    if raw["bureau_overdue_amount"] is not None:
        # Absolute overdue amount is weak without an exposure denominator.
        # Use a conservative threshold rather than pretending it is a ratio.
        values["bureau_overdue_amount"] = inverse_threshold_score(
            raw["bureau_overdue_amount"],
            [
                (0, 100),
                (1000, 90),
                (5000, 75),
                (10000, 50),
                (25000, 25),
                (float("inf"), 0),
            ],
        )

    if raw["credit_prolongation"] is not None:
        values["credit_prolongation"] = inverse_threshold_score(
            raw["credit_prolongation"],
            [
                (0, 100),
                (1, 80),
                (2, 60),
                (3, 40),
                (5, 20),
                (float("inf"), 0),
            ],
        )

    if raw["card_dpd"] is not None:
        values["card_dpd"] = inverse_threshold_score(
            raw["card_dpd"],
            [
                (0, 100),
                (7, 90),
                (30, 70),
                (60, 50),
                (90, 25),
                (180, 10),
                (float("inf"), 0),
            ],
        )

    if raw["pos_dpd"] is not None:
        values["pos_dpd"] = inverse_threshold_score(
            raw["pos_dpd"],
            [
                (0, 100),
                (7, 90),
                (30, 70),
                (60, 50),
                (90, 25),
                (180, 10),
                (float("inf"), 0),
            ],
        )

    score, coverage = weighted_mean(
        values,
        DELINQUENCY_WEIGHTS,
    )

    expected = set(DELINQUENCY_WEIGHTS.keys())
    used = set(values.keys())

    if score is None:
        status = IndicatorStatus.UNAVAILABLE.value
    elif coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE.value
    else:
        status = IndicatorStatus.LIMITED.value

    return IndicatorResult(
        score=score,
        coverage=coverage,
        status=status,
        used_features=sorted(used),
        missing_features=sorted(expected - used),
        invalid_features=[],
    )


# ============================================================================
# 11. RECURRING COMMITMENT
# ============================================================================


def score_recurring_commitment(
    row: Mapping[str, Any],
) -> IndicatorResult:
    """
    Score recurring financial commitment fulfilment.

    Primary signal:
        total_amount_paid / total_amount_due

    Secondary signal:
        existence/consistency of recurring payment obligation.

    IMPORTANT:
        Having a large EMI is not itself bad commitment adherence.
        It is an affordability issue. Therefore obligation size is not
        directly penalized here.
    """

    values: Dict[str, Optional[float]] = {}

    fulfillment = calculate_payment_fulfillment_ratio(row)

    if fulfillment is not None:
        values["payment_fulfillment"] = ratio_score(fulfillment)

    # Payment consistency is derived from the existence of a meaningful
    # recurring obligation plus available payment history.
    #
    # It does NOT reward larger obligations.
    due = safe_float(row.get("total_amount_due"))
    paid = safe_float(row.get("total_amount_paid"))

    if due is not None and due > 0 and paid is not None:
        values["recurring_payment_consistency"] = ratio_score(
            min(max(paid / due, 0.0), 1.0)
        )

    score, coverage = weighted_mean(
        values,
        RECURRING_COMMITMENT_WEIGHTS,
    )

    expected = set(RECURRING_COMMITMENT_WEIGHTS.keys())
    used = set(values.keys())

    if score is None:
        status = IndicatorStatus.UNAVAILABLE.value
    elif coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE.value
    else:
        status = IndicatorStatus.LIMITED.value

    return IndicatorResult(
        score=score,
        coverage=coverage,
        status=status,
        used_features=sorted(used),
        missing_features=sorted(expected - used),
        invalid_features=[],
    )


# ============================================================================
# 12. INSURANCE ADHERENCE
# ============================================================================


def insurance_history_status(
    row: Mapping[str, Any],
) -> IndicatorStatus:
    """
    Determine whether insurance commitment is:

        AVAILABLE
        NOT_ESTABLISHED
        UNAVAILABLE
    """

    health = safe_float(row.get("health_insurance"))
    life = safe_float(row.get("life_insurance"))

    consistency = row.get("insurance_payment_consistency")
    premium = safe_float(row.get("insurance_premium"))

    insurance_exists = (
        health == 1
        or life == 1
        or (premium is not None and premium > 0)
        or consistency is not None
    )

    if not insurance_exists:
        return IndicatorStatus.NOT_ESTABLISHED

    if consistency is None:
        return IndicatorStatus.UNAVAILABLE

    return IndicatorStatus.AVAILABLE


def score_insurance_adherence(
    row: Mapping[str, Any],
) -> IndicatorResult:
    """
    Insurance payment commitment.

    No insurance history:
        NOT_ESTABLISHED

    Insurance exists but payment history is unavailable:
        UNAVAILABLE

    Insurance payment consistency available:
        score normally.
    """

    status = insurance_history_status(row)

    if status == IndicatorStatus.NOT_ESTABLISHED:
        return IndicatorResult(
            score=None,
            coverage=0.0,
            status=IndicatorStatus.NOT_ESTABLISHED.value,
            used_features=[],
            missing_features=["insurance_payment_consistency"],
            invalid_features=[],
        )

    consistency = safe_float(row.get("insurance_payment_consistency"))

    if consistency is None or not 0 <= consistency <= 1:
        return IndicatorResult(
            score=None,
            coverage=0.0,
            status=IndicatorStatus.UNAVAILABLE.value,
            used_features=[],
            missing_features=[],
            invalid_features=["insurance_payment_consistency"],
        )

    return IndicatorResult(
        score=ratio_score(consistency),
        coverage=1.0,
        status=IndicatorStatus.AVAILABLE.value,
        used_features=["insurance_payment_consistency"],
        missing_features=[],
        invalid_features=[],
    )


# ============================================================================
# 13. DYNAMIC INDICATOR WEIGHTING
# ============================================================================


def combine_indicators(
    indicators: Mapping[str, IndicatorResult],
) -> Dict[str, Any]:
    """
    Combine the four commitment indicators.

    Missing/unestablished indicators are excluded.

    Their weights are redistributed proportionally among available
    indicators.

    Example:
        normal:
            payment       40%
            delinquency   25%
            recurring     20%
            insurance     15%

        no insurance:
            payment       47.06%
            delinquency   29.41%
            recurring     23.53%
    """

    available = {}

    for name, result in indicators.items():
        if result.score is None:
            continue

        if result.status not in {
            IndicatorStatus.AVAILABLE.value,
            IndicatorStatus.LIMITED.value,
        }:
            continue

        available[name] = result

    if not available:
        return {
            "score": None,
            "coverage": 0.0,
            "status": IndicatorStatus.NOT_ESTABLISHED.value,
            "effective_weights": {},
        }

    available_weight = sum(INDICATOR_WEIGHTS[name] for name in available)

    if available_weight <= 0:
        return {
            "score": None,
            "coverage": 0.0,
            "status": IndicatorStatus.UNAVAILABLE.value,
            "effective_weights": {},
        }

    # Pure weight redistribution.
    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / available_weight for name in available
    }

    score = sum(available[name].score * effective_weights[name] for name in available)

    # Evidence coverage.
    #
    # Each indicator contributes its original importance multiplied by
    # the proportion of its internal evidence that was available.
    evidence_coverage = sum(
        INDICATOR_WEIGHTS[name] * available[name].coverage for name in available
    )

    # Missing/unestablished dimensions do not make the score zero.
    # They reduce evidence coverage/confidence.
    overall_coverage = evidence_coverage

    if overall_coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE.value
    elif overall_coverage > 0:
        status = IndicatorStatus.LIMITED.value
    else:
        status = IndicatorStatus.UNAVAILABLE.value

    return {
        "score": round(clip_0_100(score), 2),
        "coverage": round(overall_coverage * 100, 2),
        "status": status,
        "effective_weights": {
            key: round(value, 6) for key, value in effective_weights.items()
        },
    }


# ============================================================================
# 14. CONFIDENCE
# ============================================================================


def confidence_from_coverage(coverage: float) -> str:
    """
    Convert evidence coverage to a human-readable confidence level.
    """

    if coverage >= 80:
        return "High"

    if coverage >= 50:
        return "Moderate"

    if coverage > 0:
        return "Low"

    return "Insufficient"


# ============================================================================
# 15. COMPLETE COMMITMENT SCORER
# ============================================================================


def score_commitment_adherence(
    row: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Main public function.

    Parameters
    ----------
    row:
        One customer record as a dictionary-like object.

    Returns
    -------
    dict
        Complete Commitment Adherence result.
    """

    # ------------------------------------------------------------------------
    # Validate raw features
    # ------------------------------------------------------------------------

    validation = validate_row(row)

    # ------------------------------------------------------------------------
    # Calculate individual indicators
    # ------------------------------------------------------------------------

    payment = score_payment_reliability(row)

    delinquency = score_delinquency_management(row)

    recurring = score_recurring_commitment(row)

    insurance = score_insurance_adherence(row)

    indicators = {
        "payment_reliability": payment,
        "delinquency_management": delinquency,
        "recurring_commitment": recurring,
        "insurance_adherence": insurance,
    }

    # ------------------------------------------------------------------------
    # Combine with dynamic redistribution
    # ------------------------------------------------------------------------

    combined = combine_indicators(indicators)

    # ------------------------------------------------------------------------
    # Invalid raw features
    # ------------------------------------------------------------------------

    invalid_features = sorted(
        feature
        for feature, state in validation.items()
        if state == FeatureState.INVALID
    )

    missing_features = sorted(
        feature
        for feature, state in validation.items()
        if state == FeatureState.MISSING
    )

    # ------------------------------------------------------------------------
    # Final confidence
    # ------------------------------------------------------------------------

    confidence = confidence_from_coverage(combined["coverage"])

    # ------------------------------------------------------------------------
    # Return structured result
    # ------------------------------------------------------------------------

    return {
        "score": combined["score"],
        "maximum": 100,
        "coverage": combined["coverage"],
        "status": combined["status"],
        "confidence": confidence,
        "effective_weights": combined["effective_weights"],
        "indicators": {name: asdict(result) for name, result in indicators.items()},
        "data_quality": {
            "missing_features": missing_features,
            "invalid_features": invalid_features,
        },
        "validation": {feature: state.value for feature, state in validation.items()},
    }


# ============================================================================
# 16. BATCH SCORING
# ============================================================================


def score_commitment_batch(
    rows: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    """
    Score multiple customer records.
    """

    return [score_commitment_adherence(row) for row in rows]


# ============================================================================
# 17. OPTIONAL PANDAS ADAPTER
# ============================================================================


def score_commitment_dataframe(df):
    """
    Convenience adapter for pandas DataFrames.

    This function deliberately imports pandas locally so that the core
    scoring module does not require pandas merely to score one record.
    """

    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    results = []

    for _, row in df.iterrows():
        result = score_commitment_adherence(row.to_dict())

        results.append(
            {
                "commitment_score": result["score"],
                "commitment_coverage": result["coverage"],
                "commitment_status": result["status"],
                "commitment_confidence": result["confidence"],
            }
        )

    return pd.DataFrame(results, index=df.index)


# ============================================================================
# 18. FUTURE ML INTERFACE
# ============================================================================


def get_ml_features(
    row: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return compact, model-ready commitment features.

    This function does NOT train or invoke an ML model.

    It exists so that a future empirically trained/calibrated model can use
    the same feature-processing layer without changing the FRIE API.

    Recommended future target:
        observed missed payment / delinquency / commitment failure.

    Do not train a model against the score produced by this module unless the
    explicit objective is score imitation rather than prediction.
    """

    payment_fulfillment = calculate_payment_fulfillment_ratio(row)

    late_frequency = calculate_late_payment_frequency(row)

    payment_gap = calculate_payment_gap_ratio(row)

    delinquency = calculate_delinquency_features(row)

    return {
        "on_time_payment_ratio": safe_float(row.get("on_time_payment_ratio")),
        "payment_coverage_ratio": safe_float(row.get("payment_coverage_ratio")),
        "payment_fulfillment_ratio": payment_fulfillment,
        "late_payment_frequency": late_frequency,
        "payment_gap_ratio": payment_gap,
        "bureau_overdue_ratio": delinquency["bureau_overdue_ratio"],
        "bureau_overdue_days": delinquency["bureau_overdue_days"],
        "bureau_overdue_account_count": delinquency["bureau_overdue_accounts"],
        "credit_prolongation_count": delinquency["credit_prolongation"],
        "max_card_dpd": delinquency["card_dpd"],
        "max_pos_dpd": delinquency["pos_dpd"],
        "insurance_payment_consistency": safe_float(
            row.get("insurance_payment_consistency")
        ),
    }


# ============================================================================
# 19. SIMPLE TEST / DEMO
# ============================================================================

if __name__ == "__main__":
    # Example with complete credit/payment history and no insurance history.

    example_customer = {
        "on_time_payment_ratio": 0.94,
        "payment_coverage_ratio": 0.97,
        "total_late_payments": 2,
        "total_on_time_payments": 35,
        "total_installments": 37,
        "average_payment_delay": 3,
        "total_payment_delay_days": 6,
        "payment_difference": 100,
        "total_amount_due": 10000,
        "total_amount_paid": 9900,
        "bureau_overdue_ratio": 0.01,
        "bureau_overdue_days": 5,
        "bureau_overdue_account_count": 1,
        "bureau_overdue_amount": 500,
        "credit_prolongation_count": 0,
        "max_card_dpd": 0,
        "max_card_dpd_default": 0,
        "pos_dpd_count": 0,
        "max_pos_dpd": 0,
        "max_pos_dpd_default": 0,
        "current_loan_annuity": 15000,
        "synthetic_total_emi": 15000,
        "avg_minimum_payment": 500,
        # No insurance history:
        "health_insurance": 0,
        "life_insurance": 0,
        "insurance_premium": 0,
        "insurance_payment_consistency": None,
    }

    result = score_commitment_adherence(example_customer)

    from pprint import pprint

    pprint(result)

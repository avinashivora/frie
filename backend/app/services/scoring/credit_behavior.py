"""
FRIE - Credit Behaviour Scoring
================================

Siloed implementation for the Credit Behaviour dimension.

Output:
    Credit Behaviour Score: 0-100

Design:
    RAW CREDIT FEATURES
            ↓
        Validation
            ↓
       Feature states
            ↓
      Derived indicators
            ↓
      Indicator scoring
            ↓
    Missing/invalid handling
            ↓
    Dynamic weight redistribution
            ↓
      Credit Behaviour /100
            ↓
    Coverage + status + confidence

Credit Behaviour measures:
    1. Credit History & Exposure
    2. Repayment Reliability
    3. Delinquency Severity
    4. Credit Utilisation
    5. Credit Application Behaviour

Important:
    - Missing != zero.
    - Invalid != zero.
    - No credit history != bad credit.
    - Lack of established credit history is reported as NOT_ESTABLISHED.
    - DTI/debt burden is intentionally not made a major component here because
      it belongs primarily to Affordability.
    - No ML model is trained against the current synthetic FRIE score.
      A future ML layer can use these derived indicators when a real credit
      outcome label exists.
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
    score: Optional[float]
    coverage: float
    status: str
    used_features: list[str]
    missing_features: list[str]
    invalid_features: list[str]


# ============================================================================
# 3. FEATURE DEFINITIONS
# ============================================================================

# ---------------------------------------------------------------------------
# Credit history / exposure
# ---------------------------------------------------------------------------

HISTORY_FEATURES = (
    "bureau_account_count",
    "active_credit_count",
    "closed_credit_count",
    "bureau_credit_amount",
    "bureau_debt_amount",
    "bureau_credit_limit",
    "pos_account_records",
    "previous_application_count",
    "previous_approved_count",
    "previous_refused_count",
    "previous_credit_amount",
    "previous_avg_credit",
    "previous_avg_annuity",
    "previous_avg_down_payment",
)


# ---------------------------------------------------------------------------
# Repayment behaviour
# ---------------------------------------------------------------------------

REPAYMENT_FEATURES = (
    "total_installments",
    "total_amount_due",
    "total_amount_paid",
    "total_late_payments",
    "total_on_time_payments",
    "average_payment_delay",
    "total_payment_delay_days",
    "payment_difference",
    "on_time_payment_ratio",
    "payment_coverage_ratio",
)


# ---------------------------------------------------------------------------
# Delinquency
# ---------------------------------------------------------------------------

DELINQUENCY_FEATURES = (
    "bureau_overdue_amount",
    "bureau_overdue_days",
    "bureau_overdue_account_count",
    "bureau_overdue_ratio",
    "credit_prolongation_count",
    "max_card_dpd",
    "max_card_dpd_default",
    "pos_dpd_count",
    "max_pos_dpd",
    "max_pos_dpd_default",
)


# ---------------------------------------------------------------------------
# Credit utilisation
# ---------------------------------------------------------------------------

UTILISATION_FEATURES = (
    "avg_credit_card_balance",
    "max_credit_card_balance",
    "avg_credit_limit",
    "total_card_drawings",
    "total_card_payments",
    "avg_minimum_payment",
    "avg_credit_utilisation",
)


# ---------------------------------------------------------------------------
# Application behaviour
# ---------------------------------------------------------------------------

APPLICATION_FEATURES = (
    "previous_application_count",
    "previous_approved_count",
    "previous_refused_count",
    "previous_approval_ratio",
)


# ============================================================================
# 4. TOP-LEVEL INDICATOR WEIGHTS
# ============================================================================

# These represent the conceptual composition of Credit Behaviour.

INDICATOR_WEIGHTS = {
    "credit_history": 0.15,
    "repayment_reliability": 0.30,
    "delinquency_severity": 0.30,
    "credit_utilisation": 0.15,
    "application_behaviour": 0.10,
}


# ============================================================================
# 5. INTERNAL INDICATOR WEIGHTS
# ============================================================================

HISTORY_WEIGHTS = {
    "credit_history_depth": 0.30,
    "active_credit_exposure": 0.20,
    "credit_closure_history": 0.15,
    "credit_exposure": 0.20,
    "previous_credit_experience": 0.15,
}


REPAYMENT_WEIGHTS = {
    "on_time_payment_ratio": 0.35,
    "payment_coverage_ratio": 0.30,
    "late_payment_frequency": 0.15,
    "average_payment_delay": 0.10,
    "payment_gap": 0.10,
}


DELINQUENCY_WEIGHTS = {
    "overdue_ratio": 0.25,
    "overdue_days": 0.20,
    "overdue_accounts": 0.15,
    "overdue_amount": 0.10,
    "credit_prolongation": 0.10,
    "card_dpd": 0.10,
    "pos_dpd": 0.10,
}


UTILISATION_WEIGHTS = {
    "credit_utilisation": 0.60,
    "card_balance_to_limit": 0.20,
    "credit_limit_headroom": 0.20,
}


APPLICATION_WEIGHTS = {
    "approval_ratio": 0.55,
    "refusal_ratio": 0.25,
    "application_activity": 0.20,
}


# ============================================================================
# 6. GENERAL UTILITIES
# ============================================================================


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, float) and math.isnan(value):
        return True

    return False


def safe_float(value: Any) -> Optional[float]:
    if is_missing(value):
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


def is_finite_number(value: Any) -> bool:
    return safe_float(value) is not None


def clip_0_100(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    return max(0.0, min(100.0, float(value)))


# ============================================================================
# 7. FEATURE VALIDATION
# ============================================================================


def validate_feature(
    row: Mapping[str, Any],
    feature: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> FeatureState:

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
    Validate all Credit Behaviour features.

    Ratios:
        0-1

    Counts/amounts:
        >= 0
    """

    states: Dict[str, FeatureState] = {}

    bounded_0_1 = {
        "on_time_payment_ratio",
        "payment_coverage_ratio",
        "avg_credit_utilisation",
        "previous_approval_ratio",
    }

    nonnegative = {
        "bureau_account_count",
        "active_credit_count",
        "closed_credit_count",
        "bureau_credit_amount",
        "bureau_debt_amount",
        "bureau_credit_limit",
        "pos_account_records",
        "previous_application_count",
        "previous_approved_count",
        "previous_refused_count",
        "previous_credit_amount",
        "previous_avg_credit",
        "previous_avg_annuity",
        "previous_avg_down_payment",
        "total_installments",
        "total_amount_due",
        "total_amount_paid",
        "total_late_payments",
        "total_on_time_payments",
        "average_payment_delay",
        "total_payment_delay_days",
        "payment_difference",
        "bureau_overdue_amount",
        "bureau_overdue_days",
        "bureau_overdue_account_count",
        "bureau_overdue_ratio",
        "credit_prolongation_count",
        "max_card_dpd",
        "max_card_dpd_default",
        "pos_dpd_count",
        "max_pos_dpd",
        "max_pos_dpd_default",
        "avg_credit_card_balance",
        "max_credit_card_balance",
        "avg_credit_limit",
        "total_card_drawings",
        "total_card_payments",
        "avg_minimum_payment",
    }

    all_features = (
        HISTORY_FEATURES
        + REPAYMENT_FEATURES
        + DELINQUENCY_FEATURES
        + UTILISATION_FEATURES
        + APPLICATION_FEATURES
    )

    for feature in all_features:
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

        else:
            states[feature] = validate_feature(row, feature)

    return states


# ============================================================================
# 8. NORMALIZATION
# ============================================================================


def ratio_score(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    return clip_0_100(value * 100.0)


def inverse_threshold_score(
    value: Optional[float],
    thresholds: list[tuple[float, float]],
) -> Optional[float]:

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

    total_weight = sum(weights.values())

    if total_weight <= 0:
        return None, 0.0

    valid = {
        key: value
        for key, value in values.items()
        if key in weights and value is not None and is_finite_number(value)
    }

    if not valid:
        return None, 0.0

    available_weight = sum(weights[key] for key in valid)

    score = sum(float(valid[key]) * weights[key] for key in valid) / available_weight

    coverage = available_weight / total_weight

    return clip_0_100(score), coverage


# ============================================================================
# 9. CREDIT HISTORY
# ============================================================================


def score_credit_history(
    row: Mapping[str, Any],
) -> IndicatorResult:

    values: Dict[str, Optional[float]] = {}

    account_count = safe_float(row.get("bureau_account_count"))

    if account_count is not None:
        # Having some established credit history is positive.
        # This is deliberately capped; more accounts are not infinitely better.
        values["credit_history_depth"] = inverse_threshold_score(
            account_count,
            [
                (0, 0),
                (1, 50),
                (2, 70),
                (3, 80),
                (5, 90),
                (float("inf"), 100),
            ],
        )

    active = safe_float(row.get("active_credit_count"))

    if active is not None:
        values["active_credit_exposure"] = inverse_threshold_score(
            active,
            [
                (0, 100),
                (1, 90),
                (2, 80),
                (3, 70),
                (5, 55),
                (float("inf"), 40),
            ],
        )

    closed = safe_float(row.get("closed_credit_count"))

    if closed is not None:
        values["credit_closure_history"] = inverse_threshold_score(
            closed,
            [
                (0, 30),
                (1, 60),
                (2, 75),
                (3, 85),
                (5, 95),
                (float("inf"), 100),
            ],
        )

    bureau_credit = safe_float(row.get("bureau_credit_amount"))

    bureau_debt = safe_float(row.get("bureau_debt_amount"))

    if bureau_credit is not None and bureau_credit > 0:
        # Outstanding debt as a proportion of bureau credit.
        if bureau_debt is not None:
            debt_ratio = min(
                max(bureau_debt / bureau_credit, 0.0),
                1.0,
            )

            values["credit_exposure"] = inverse_threshold_score(
                debt_ratio,
                [
                    (0.10, 100),
                    (0.25, 90),
                    (0.50, 75),
                    (0.70, 55),
                    (0.90, 30),
                    (1.00, 10),
                    (float("inf"), 0),
                ],
            )

    previous_credit = safe_float(row.get("previous_credit_amount"))

    if previous_credit is not None:
        values["previous_credit_experience"] = 50.0 if previous_credit > 0 else 0.0

    score, coverage = weighted_mean(
        values,
        HISTORY_WEIGHTS,
    )

    expected = set(HISTORY_WEIGHTS)
    used = set(values)

    if score is None:
        status = IndicatorStatus.NOT_ESTABLISHED.value
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
# 10. REPAYMENT RELIABILITY
# ============================================================================


def calculate_late_payment_frequency(
    row: Mapping[str, Any],
) -> Optional[float]:

    late = safe_float(row.get("total_late_payments"))

    installments = safe_float(row.get("total_installments"))

    if late is None or installments is None:
        return None

    if installments <= 0:
        return None

    return max(0.0, late / installments)


def calculate_payment_gap_ratio(
    row: Mapping[str, Any],
) -> Optional[float]:

    difference = safe_float(row.get("payment_difference"))

    due = safe_float(row.get("total_amount_due"))

    if difference is None or due is None:
        return None

    if due <= 0:
        return None

    # Positive difference = underpayment.
    # Negative difference = overpayment.
    # Overpayment is not rewarded above 100.
    return max(difference, 0.0) / due


def score_repayment_reliability(
    row: Mapping[str, Any],
) -> IndicatorResult:

    values: Dict[str, Optional[float]] = {}

    on_time = safe_float(row.get("on_time_payment_ratio"))

    if on_time is not None:
        values["on_time_payment_ratio"] = ratio_score(on_time)

    coverage = safe_float(row.get("payment_coverage_ratio"))

    if coverage is not None:
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
        REPAYMENT_WEIGHTS,
    )

    expected = set(REPAYMENT_WEIGHTS)
    used = set(values)

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
# 11. DELINQUENCY
# ============================================================================


def score_delinquency_severity(
    row: Mapping[str, Any],
) -> IndicatorResult:

    values: Dict[str, Optional[float]] = {}

    overdue_ratio = safe_float(row.get("bureau_overdue_ratio"))

    # If the precomputed ratio is absent, derive it where possible.
    if overdue_ratio is None:
        overdue_amount = safe_float(row.get("bureau_overdue_amount"))

        bureau_credit = safe_float(row.get("bureau_credit_amount"))

        if (
            overdue_amount is not None
            and bureau_credit is not None
            and bureau_credit > 0
        ):
            overdue_ratio = overdue_amount / bureau_credit

    if overdue_ratio is not None:
        values["overdue_ratio"] = inverse_threshold_score(
            overdue_ratio,
            [
                (0.00, 100),
                (0.02, 85),
                (0.05, 70),
                (0.10, 50),
                (0.20, 25),
                (float("inf"), 0),
            ],
        )

    overdue_days = safe_float(row.get("bureau_overdue_days"))

    if overdue_days is not None:
        values["overdue_days"] = inverse_threshold_score(
            overdue_days,
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

    overdue_accounts = safe_float(row.get("bureau_overdue_account_count"))

    if overdue_accounts is not None:
        values["overdue_accounts"] = inverse_threshold_score(
            overdue_accounts,
            [
                (0, 100),
                (1, 75),
                (2, 50),
                (3, 25),
                (float("inf"), 0),
            ],
        )

    overdue_amount = safe_float(row.get("bureau_overdue_amount"))

    if overdue_amount is not None:
        values["overdue_amount"] = inverse_threshold_score(
            overdue_amount,
            [
                (0, 100),
                (1000, 90),
                (5000, 75),
                (10000, 50),
                (25000, 25),
                (float("inf"), 0),
            ],
        )

    prolongation = safe_float(row.get("credit_prolongation_count"))

    if prolongation is not None:
        values["credit_prolongation"] = inverse_threshold_score(
            prolongation,
            [
                (0, 100),
                (1, 80),
                (2, 60),
                (3, 40),
                (5, 20),
                (float("inf"), 0),
            ],
        )

    card_dpd = safe_float(row.get("max_card_dpd"))

    if card_dpd is not None:
        values["card_dpd"] = inverse_threshold_score(
            card_dpd,
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

    pos_dpd = safe_float(row.get("max_pos_dpd"))

    if pos_dpd is not None:
        values["pos_dpd"] = inverse_threshold_score(
            pos_dpd,
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

    expected = set(DELINQUENCY_WEIGHTS)
    used = set(values)

    if score is None:
        status = IndicatorStatus.NOT_ESTABLISHED.value
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
# 12. CREDIT UTILISATION
# ============================================================================


def score_credit_utilisation(
    row: Mapping[str, Any],
) -> IndicatorResult:

    values: Dict[str, Optional[float]] = {}

    utilisation = safe_float(row.get("avg_credit_utilisation"))

    if utilisation is not None:
        values["credit_utilisation"] = inverse_threshold_score(
            utilisation,
            [
                (0.10, 100),
                (0.30, 90),
                (0.50, 75),
                (0.70, 55),
                (0.90, 30),
                (1.00, 10),
                (float("inf"), 0),
            ],
        )

    balance = safe_float(row.get("avg_credit_card_balance"))

    limit = safe_float(row.get("avg_credit_limit"))

    if balance is not None and limit is not None and limit > 0:
        balance_ratio = max(
            0.0,
            balance / limit,
        )

        values["card_balance_to_limit"] = inverse_threshold_score(
            balance_ratio,
            [
                (0.10, 100),
                (0.30, 90),
                (0.50, 75),
                (0.70, 55),
                (0.90, 30),
                (1.00, 10),
                (float("inf"), 0),
            ],
        )

        values["credit_limit_headroom"] = clip_0_100(
            (1.0 - min(balance_ratio, 1.0)) * 100
        )

    score, coverage = weighted_mean(
        values,
        UTILISATION_WEIGHTS,
    )

    expected = set(UTILISATION_WEIGHTS)
    used = set(values)

    if score is None:
        status = IndicatorStatus.NOT_ESTABLISHED.value
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
# 13. APPLICATION BEHAVIOUR
# ============================================================================


def score_application_behaviour(
    row: Mapping[str, Any],
) -> IndicatorResult:

    values: Dict[str, Optional[float]] = {}

    applications = safe_float(row.get("previous_application_count"))

    approved = safe_float(row.get("previous_approved_count"))

    refused = safe_float(row.get("previous_refused_count"))

    approval_ratio = safe_float(row.get("previous_approval_ratio"))

    # Prefer the supplied ratio.
    if approval_ratio is not None:
        values["approval_ratio"] = ratio_score(approval_ratio)

    # Otherwise derive it.
    elif applications is not None and applications > 0:
        if approved is not None:
            derived_approval = approved / applications

            derived_approval = min(
                max(derived_approval, 0.0),
                1.0,
            )

            values["approval_ratio"] = ratio_score(derived_approval)

    if applications is not None and applications > 0:
        if refused is not None:
            refusal_ratio = min(
                max(refused / applications, 0.0),
                1.0,
            )

            values["refusal_ratio"] = inverse_threshold_score(
                refusal_ratio,
                [
                    (0.00, 100),
                    (0.10, 90),
                    (0.25, 75),
                    (0.50, 50),
                    (0.75, 25),
                    (1.00, 0),
                    (float("inf"), 0),
                ],
            )

        # Application activity itself is contextual rather than a direct
        # penalty. We use a capped score to avoid treating high application
        # counts as automatically irresponsible.
        values["application_activity"] = inverse_threshold_score(
            applications,
            [
                (0, 100),
                (1, 100),
                (3, 95),
                (5, 85),
                (10, 70),
                (20, 50),
                (float("inf"), 30),
            ],
        )

    score, coverage = weighted_mean(
        values,
        APPLICATION_WEIGHTS,
    )

    expected = set(APPLICATION_WEIGHTS)
    used = set(values)

    if score is None:
        # No application history is not bad credit.
        status = IndicatorStatus.NOT_ESTABLISHED.value
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
# 14. DYNAMIC TOP-LEVEL WEIGHTING
# ============================================================================


def combine_indicators(
    indicators: Mapping[str, IndicatorResult],
) -> Dict[str, Any]:
    """
    Dynamically redistribute the five Credit Behaviour indicator weights.

    NOT_ESTABLISHED indicators are excluded without treating them as zero.

    Example:

        Normal:
            History       15%
            Repayment     30%
            Delinquency   30%
            Utilisation   15%
            Applications  10%

        No credit history:
            indicators that cannot be established are excluded and their
            weights are redistributed across the remaining valid indicators.
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

    # Redistribute missing indicator weights.
    effective_weights = {
        name: INDICATOR_WEIGHTS[name] / available_weight for name in available
    }

    score = sum(available[name].score * effective_weights[name] for name in available)

    # Evidence coverage is based on original importance and actual
    # evidence availability.
    evidence_coverage = sum(
        INDICATOR_WEIGHTS[name] * available[name].coverage for name in available
    )

    if evidence_coverage >= 0.80:
        status = IndicatorStatus.AVAILABLE.value
    elif evidence_coverage > 0:
        status = IndicatorStatus.LIMITED.value
    else:
        status = IndicatorStatus.UNAVAILABLE.value

    return {
        "score": round(
            clip_0_100(score),
            2,
        ),
        "coverage": round(
            evidence_coverage * 100,
            2,
        ),
        "status": status,
        "effective_weights": {
            name: round(weight, 6) for name, weight in effective_weights.items()
        },
    }


# ============================================================================
# 15. CONFIDENCE
# ============================================================================


def confidence_from_coverage(
    coverage: float,
) -> str:

    if coverage >= 80:
        return "High"

    if coverage >= 50:
        return "Moderate"

    if coverage > 0:
        return "Low"

    return "Insufficient"


# ============================================================================
# 16. MAIN PUBLIC FUNCTION
# ============================================================================


def score_credit_behaviour(
    row: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Main Credit Behaviour scoring function.

    Returns a structured 0-100 result.
    """

    validation = validate_row(row)

    indicators = {
        "credit_history": score_credit_history(row),
        "repayment_reliability": score_repayment_reliability(row),
        "delinquency_severity": score_delinquency_severity(row),
        "credit_utilisation": score_credit_utilisation(row),
        "application_behaviour": score_application_behaviour(row),
    }

    combined = combine_indicators(indicators)

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

    confidence = confidence_from_coverage(combined["coverage"])

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
# 17. BATCH SCORING
# ============================================================================


def score_credit_batch(
    rows: Iterable[Mapping[str, Any]],
) -> list[Dict[str, Any]]:

    return [score_credit_behaviour(row) for row in rows]


# ============================================================================
# 18. PANDAS ADAPTER
# ============================================================================


def score_credit_dataframe(df):
    """
    Score every row of a pandas DataFrame.

    Returns only the fields required by the six-factor FRIE layer.
    """

    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    results = []

    for _, row in df.iterrows():
        result = score_credit_behaviour(row.to_dict())

        results.append(
            {
                "credit_score": result["score"],
                "credit_coverage": result["coverage"],
                "credit_status": result["status"],
                "credit_confidence": result["confidence"],
            }
        )

    return pd.DataFrame(
        results,
        index=df.index,
    )


# ============================================================================
# 19. FUTURE ML FEATURE VECTOR
# ============================================================================


def get_ml_features(
    row: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Return compact derived Credit Behaviour features for a future ML model.

    This function does NOT train or invoke ML.

    Recommended future targets:
        - default within 12 months
        - serious delinquency within 12 months
        - missed credit payment within 90 days
        - credit account becoming delinquent

    The model should predict an observed outcome, not reproduce the
    deterministic FRIE score.
    """

    late = safe_float(row.get("total_late_payments"))

    installments = safe_float(row.get("total_installments"))

    late_frequency = None

    if late is not None and installments is not None and installments > 0:
        late_frequency = late / installments

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

    balance = safe_float(row.get("avg_credit_card_balance"))

    limit = safe_float(row.get("avg_credit_limit"))

    card_balance_ratio = None

    if balance is not None and limit is not None and limit > 0:
        card_balance_ratio = balance / limit

    approval_ratio = safe_float(row.get("previous_approval_ratio"))

    if approval_ratio is None:
        applications = safe_float(row.get("previous_application_count"))

        approved = safe_float(row.get("previous_approved_count"))

        if applications is not None and applications > 0 and approved is not None:
            approval_ratio = approved / applications

    return {
        "credit_history_depth": safe_float(row.get("bureau_account_count")),
        "active_credit_count": safe_float(row.get("active_credit_count")),
        "closed_credit_count": safe_float(row.get("closed_credit_count")),
        "bureau_credit_amount": safe_float(row.get("bureau_credit_amount")),
        "bureau_debt_amount": safe_float(row.get("bureau_debt_amount")),
        "late_payment_frequency": late_frequency,
        "on_time_payment_ratio": safe_float(row.get("on_time_payment_ratio")),
        "payment_coverage_ratio": safe_float(row.get("payment_coverage_ratio")),
        "bureau_overdue_ratio": overdue_ratio,
        "bureau_overdue_days": safe_float(row.get("bureau_overdue_days")),
        "bureau_overdue_account_count": safe_float(
            row.get("bureau_overdue_account_count")
        ),
        "credit_prolongation_count": safe_float(row.get("credit_prolongation_count")),
        "max_card_dpd": safe_float(row.get("max_card_dpd")),
        "max_pos_dpd": safe_float(row.get("max_pos_dpd")),
        "avg_credit_utilisation": safe_float(row.get("avg_credit_utilisation")),
        "card_balance_to_limit": card_balance_ratio,
        "previous_application_count": safe_float(row.get("previous_application_count")),
        "previous_approval_ratio": approval_ratio,
        "previous_refused_count": safe_float(row.get("previous_refused_count")),
    }


# ============================================================================
# 20. DEMO
# ============================================================================

if __name__ == "__main__":
    example_customer = {
        # Credit history
        "bureau_account_count": 5,
        "active_credit_count": 2,
        "closed_credit_count": 3,
        "bureau_credit_amount": 500000,
        "bureau_debt_amount": 150000,
        "bureau_credit_limit": 300000,
        "pos_account_records": 2,
        # Repayment
        "total_installments": 48,
        "total_amount_due": 100000,
        "total_amount_paid": 98000,
        "total_late_payments": 2,
        "total_on_time_payments": 46,
        "average_payment_delay": 3,
        "total_payment_delay_days": 6,
        "payment_difference": 2000,
        "on_time_payment_ratio": 0.958,
        "payment_coverage_ratio": 0.98,
        # Delinquency
        "bureau_overdue_amount": 1000,
        "bureau_overdue_days": 5,
        "bureau_overdue_account_count": 1,
        "bureau_overdue_ratio": 0.002,
        "credit_prolongation_count": 0,
        "max_card_dpd": 0,
        "max_card_dpd_default": 0,
        "pos_dpd_count": 0,
        "max_pos_dpd": 0,
        "max_pos_dpd_default": 0,
        # Card
        "avg_credit_card_balance": 30000,
        "max_credit_card_balance": 45000,
        "avg_credit_limit": 100000,
        "total_card_drawings": 20,
        "total_card_payments": 20,
        "avg_minimum_payment": 1500,
        "avg_credit_utilisation": 0.30,
        # Previous applications
        "previous_application_count": 5,
        "previous_approved_count": 4,
        "previous_refused_count": 1,
        "previous_credit_amount": 300000,
        "previous_avg_credit": 75000,
        "previous_avg_annuity": 6000,
        "previous_avg_down_payment": 10000,
        "previous_approval_ratio": 0.80,
    }

    from pprint import pprint

    result = score_credit_behaviour(example_customer)

    pprint(result)

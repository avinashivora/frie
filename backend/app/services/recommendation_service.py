"""Rule-based, informational recommendations from stored FRIE indicators."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

RECOMMENDATION_THRESHOLD = 55.0
HIGH_PRIORITY_THRESHOLD = 35.0
MEDIUM_PRIORITY_THRESHOLD = 45.0

_RULES: dict[str, dict[str, str]] = {
    "income_stability": {
        "category": "Income & Employment",
        "title": "Review income and employment stability",
        "description": "Consider whether there are practical steps to maintain or strengthen income and employment stability.",
    },
    "cashflow_stability": {
        "category": "Cash-flow Stability",
        "title": "Review recurring expenses and cash-flow buffer",
        "description": "Review recurring expenses and consider maintaining a stronger buffer for changes in monthly cash flow.",
    },
    "payment_discipline": {
        "category": "Payment Discipline",
        "title": "Review repayment consistency and timing",
        "description": "Review repayment schedules and payment timing to help maintain consistent repayments.",
    },
    "savings_discipline": {
        "category": "Savings",
        "title": "Review your monthly savings behaviour",
        "description": "Review recurring expenses and savings allocation in light of your current income and goals.",
    },
    "commitment_adherence": {
        "category": "Financial Commitments",
        "title": "Review recurring financial commitments",
        "description": "Review recurring commitments and payment consistency where applicable.",
    },
    "debt_burden": {
        "category": "Debt Burden",
        "title": "Review debt obligations and repayment load",
        "description": "Review current debt obligations and EMI commitments in the context of your income.",
    },
    "financial_stress": {
        "category": "Financial Stress",
        "title": "Review expenses, cash-flow pressure and reserves",
        "description": "Review recurring expenses, cash-flow pressure and available emergency reserves.",
    },
    "financial_resilience": {
        "category": "Financial Resilience",
        "title": "Review your emergency savings position",
        "description": "Consider whether your savings and existing investments provide an appropriate buffer for your circumstances.",
    },
}

_LABELS = {
    "income_stability": "Income Stability",
    "cashflow_stability": "Cash-flow Stability",
    "payment_discipline": "Payment Discipline",
    "savings_discipline": "Savings Discipline",
    "commitment_adherence": "Commitment Adherence",
    "debt_burden": "Debt Burden",
    "financial_stress": "Financial Stress",
    "financial_resilience": "Financial Resilience",
}

_SOURCE_RULES: dict[str, dict[str, str]] = {
    "credit": {
        "category": "Credit Report",
        "title": "Add your credit report",
        "description": "Your credit history is not currently available. Adding a credit report can improve the completeness of the repayment assessment.",
        "related_indicator": "payment_discipline",
        "related_indicator_label": "Payment Discipline",
    },
    "insurance": {
        "category": "Insurance Details",
        "title": "Add your insurance details",
        "description": "Insurance information is not currently available. Adding policy and payment information can include protection and commitment behaviour.",
        "related_indicator": "commitment_adherence",
        "related_indicator_label": "Commitment Adherence",
    },
    "investments": {
        "category": "Investment Details",
        "title": "Add your investment details",
        "description": "Investment information is not currently available. Adding your holdings or confirming that you have none can improve the completeness of your resilience assessment.",
        "related_indicator": "financial_resilience",
        "related_indicator_label": "Financial Resilience",
    },
    "loans": {
        "category": "Loan Details",
        "title": "Add loan details or confirm that you have no loan",
        "description": "Loan information is not currently available. Add your loan details or confirm that you have no loan to improve the completeness of your debt-burden assessment.",
        "related_indicator": "debt_burden",
        "related_indicator_label": "Debt Burden",
    },
}


def _score(value: Any) -> float | None:
    """Read either a numeric indicator or its API detail envelope."""
    if isinstance(value, Mapping):
        value = value.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not 0.0 <= numeric <= 100.0:
        return None
    return numeric


def generate_recommendations(
    indicators: Mapping[str, Any], *, missing_sources: list[str] | tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    """Return score-sorted prototype guidance for indicators below 55/100.

    The recommendation thresholds are informational prototype heuristics, not
    universal financial standards. No score-impact claim is made.
    """
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for key, rule in _RULES.items():
        score = _score(indicators.get(key))
        if score is None or score >= RECOMMENDATION_THRESHOLD:
            continue
        priority = (
            "High"
            if score < HIGH_PRIORITY_THRESHOLD
            else "Medium"
            if score < MEDIUM_PRIORITY_THRESHOLD
            else "Low"
        )
        label = _LABELS[key]
        recommendation = {
            **rule,
            "priority": priority,
            "related_indicator": key,
            "related_indicator_label": label,
            "indicator_score": round(score, 2),
            "reason": (
                f"Your {label} indicator is {score:.0f}/100, below the prototype "
                f"recommendation threshold of {RECOMMENDATION_THRESHOLD:.0f}/100."
            ),
        }
        candidates.append((score, key, recommendation))

    candidates.sort(key=lambda item: (item[0], item[1]))
    result = [item[2] for item in candidates]
    for source in ("credit", "insurance", "investments", "loans"):
        if source not in missing_sources:
            continue
        rule = _SOURCE_RULES[source]
        # A low indicator recommendation is already more actionable than a
        # duplicate "add information" card for the same source.
        if any(
            item["related_indicator"] == rule["related_indicator"] for item in result
        ):
            continue
        result.append(
            {
                **rule,
                "priority": "Low",
                "indicator_score": None,
                "reason": "This information has not been provided yet and is optional when your other sources support an assessment.",
            }
        )
    return result

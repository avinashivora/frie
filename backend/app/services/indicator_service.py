"""Prototype v1.0 FRIE indicator calculations ported from Frie_score.ipynb.

Indicator scores describe the methodology dimensions. They are independent of
the V2 model prediction and its local SHAP explanation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

INDICATOR_META: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "income_stability",
        "Income Stability",
        "Employment stability using employment history as a proxy; monthly income history is not available in this prototype.",
        ("Income & employment details",),
        "Employment tenure is a prototype proxy, not a longitudinal measure of income.",
    ),
    (
        "cashflow_stability",
        "Cash-flow Stability",
        "Cash-flow variability, negative months, and minimum monthly cash flow.",
        ("Bank statement", "Income & employment details"),
        "Combines cash-flow variability (50%), negative months (30%), and minimum cash flow relative to income (20%).",
    ),
    (
        "payment_discipline",
        "Payment Discipline",
        "On-time repayments, payment coverage, and payment timing.",
        ("Credit report",),
        "Combines on-time payments (50%), payment coverage (30%), and payment delay (20%).",
    ),
    (
        "savings_discipline",
        "Savings Discipline",
        "Monthly savings behaviour relative to income.",
        ("Bank statement", "Income & employment details"),
        "20% is the prototype savings-rate benchmark, not a universal financial standard.",
    ),
    (
        "commitment_adherence",
        "Commitment Adherence",
        "Insurance payment consistency and repayment coverage.",
        ("Insurance details", "Credit report"),
        "Combines insurance payment consistency (70%) and payment coverage (30%); utility-payment history is not assumed.",
    ),
    (
        "debt_burden",
        "Debt Burden",
        "Current repayment burden and credit debt relative to annual income.",
        ("Loan details", "Credit report", "Income & employment details"),
        "Current repayment burden and credit exposure use 70% and 30% weights. Lower burden produces a higher score.",
    ),
    (
        "financial_stress",
        "Financial Stress",
        "Expense pressure, negative cash-flow months, overdue behaviour, and savings buffer.",
        ("Bank statement", "Credit report"),
        "Lower current financial pressure produces a higher score.",
    ),
    (
        "financial_resilience",
        "Financial Resilience",
        "Savings buffer, investment participation, and minimum cash-flow strength.",
        ("Bank statement", "Investment details", "Income & employment details"),
        "The savings buffer uses a six-month prototype benchmark; investment participation counts six product types and caps at three.",
    ),
)

_COMPONENT_LABELS: dict[str, str] = {
    "income_stability": "Employment history",
    "cashflow_stability": "Cash-flow variability, negative months, minimum cash flow",
    "payment_discipline": "Repayment consistency, coverage, payment timing",
    "savings_discipline": "Savings behaviour",
    "commitment_adherence": "Insurance payment consistency, repayment coverage",
    "debt_burden": "Repayment commitments, credit debt relative to annual income",
    "financial_stress": "Expenses, negative cash-flow months, overdue behaviour, savings buffer",
    "financial_resilience": "Savings buffer, investment participation, minimum cash flow",
}


def _number(features: Mapping[str, Any], name: str) -> float | None:
    value = features.get(name)
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


def _higher(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    return _bounded((value - minimum) / (maximum - minimum) * 100.0)


def _lower(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    return _bounded((maximum - value) / (maximum - minimum) * 100.0)


def _weighted(
    components: Sequence[tuple[float | None, float]],
    *,
    neutral_if_missing: bool = False,
) -> tuple[float | None, int]:
    """Notebook weighted average, ignoring missing inputs.

    The application reports no score when every component is unavailable. The
    original notebook's all-missing fallback of 50 is available for reference
    validation. Normal assessments only use the documented neutral fallback for
    Income Stability; unavailable financial behaviour remains limited.
    """
    available = [(value, weight) for value, weight in components if value is not None]
    denominator = sum(weight for _, weight in available)
    if denominator == 0:
        return (50.0 if neutral_if_missing else None), 0
    return _bounded(
        sum(value * weight for value, weight in available) / denominator
    ), len(available)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _score_components(
    features: Mapping[str, Any], *, notebook_compatible: bool = False
) -> tuple[dict[str, float | None], dict[str, int]]:
    get = lambda name: _number(features, name)
    monthly_income = get("monthly_income")
    cash_mean, cash_std = get("cash_flow_mean"), get("cash_flow_std")
    cash_min, negative_months = get("cash_flow_min"), get("cash_flow_negative_months")

    cash_cv = _ratio(cash_std, abs(cash_mean) if cash_mean is not None else None)
    negative_month_score = _higher(
        None if negative_months is None else 12 - negative_months, 0, 12
    )
    minimum_cash_score = (
        None
        if _ratio(cash_min, monthly_income) is None
        else _bounded(max(0.0, min(1.0, _ratio(cash_min, monthly_income))) * 100.0)
    )

    on_time = get("on_time_payment_ratio")
    coverage = get("payment_coverage_ratio")
    average_delay = get("average_payment_delay")
    insurance_consistency = get("insurance_payment_consistency")
    current_dti = get("current_dti")
    annual_income = None if monthly_income is None else monthly_income * 12
    bureau_debt = get("bureau_debt_amount")
    bureau_ratio = _ratio(
        None if bureau_debt is None else max(0.0, bureau_debt), annual_income
    )
    total_expense_raw = get("synthetic_total_expense")
    total_expense = None if total_expense_raw is None else max(0.0, total_expense_raw)
    income_for_expense = None if monthly_income is None else max(0.0, monthly_income)
    expense_ratio = _ratio(total_expense, income_for_expense)
    overdue_days = get("bureau_overdue_days")
    savings_balance_raw = get("savings_balance")
    savings_balance = (
        None if savings_balance_raw is None else max(0.0, savings_balance_raw)
    )
    savings_buffer = _ratio(savings_balance, total_expense)

    savings_rate = get("savings_rate")
    investment_names = (
        "fd_amount",
        "rd_contribution",
        "sip_contribution",
        "mutual_fund_balance",
        "ppf_contribution",
        "nps_contribution",
    )
    investment_values = [get(name) for name in investment_names]
    # The original notebook fills unknown investment columns with zero. For a
    # real assessment, require the declarations/documents for all six holdings
    # to be settled before treating an absent value as confirmed none.
    investments_known = notebook_compatible or all(
        value is not None for value in investment_values
    )
    investment_count = sum(
        value > 0 for value in investment_values if value is not None
    )
    investment_score = (
        _higher(float(investment_count), 0, 3) if investments_known else None
    )

    scores: dict[str, float | None] = {}
    counts: dict[str, int] = {}
    scores["income_stability"] = (
        50.0
        if get("employment_years") is None
        else _higher(get("employment_years"), 0, 20)
    )
    counts["income_stability"] = 1 if get("employment_years") is not None else 0
    scores["cashflow_stability"], counts["cashflow_stability"] = _weighted(
        (
            (_lower(cash_cv, 0, 1), 0.50),
            (negative_month_score, 0.30),
            (minimum_cash_score, 0.20),
        ),
        neutral_if_missing=notebook_compatible,
    )
    scores["payment_discipline"], counts["payment_discipline"] = _weighted(
        (
            (
                _higher(None if on_time is None else max(0.0, min(1.0, on_time)), 0, 1),
                0.50,
            ),
            (
                _higher(
                    None if coverage is None else max(0.0, min(1.0, coverage)), 0, 1
                ),
                0.30,
            ),
            (
                _lower(
                    None if average_delay is None else max(0.0, average_delay), 0, 60
                ),
                0.20,
            ),
        ),
        neutral_if_missing=notebook_compatible,
    )
    scores["savings_discipline"] = (
        (50.0 if notebook_compatible else None)
        if savings_rate is None
        else _bounded(savings_rate / 0.20 * 100.0)
    )
    counts["savings_discipline"] = int(savings_rate is not None)
    scores["commitment_adherence"], counts["commitment_adherence"] = _weighted(
        (
            (
                _higher(
                    None
                    if insurance_consistency is None
                    else max(0.0, min(1.0, insurance_consistency)),
                    0,
                    1,
                ),
                0.70,
            ),
            (
                _higher(
                    None if coverage is None else max(0.0, min(1.0, coverage)), 0, 1
                ),
                0.30,
            ),
        ),
        neutral_if_missing=notebook_compatible,
    )
    scores["debt_burden"], counts["debt_burden"] = _weighted(
        (
            (
                _lower(None if current_dti is None else max(0.0, current_dti), 0, 0.50),
                0.70,
            ),
            (_lower(bureau_ratio, 0, 2), 0.30),
        ),
        neutral_if_missing=notebook_compatible,
    )
    scores["financial_stress"], counts["financial_stress"] = _weighted(
        (
            (_lower(expense_ratio, 0, 1), 0.30),
            (negative_month_score, 0.25),
            (
                _lower(None if overdue_days is None else max(0.0, overdue_days), 0, 90),
                0.25,
            ),
            (_higher(savings_buffer, 0, 6), 0.20),
        ),
        neutral_if_missing=notebook_compatible,
    )
    scores["financial_resilience"], counts["financial_resilience"] = _weighted(
        (
            (_higher(savings_buffer, 0, 6), 0.50),
            (investment_score, 0.25),
            (minimum_cash_score, 0.25),
        ),
        neutral_if_missing=notebook_compatible,
    )
    return scores, counts


def calculate_indicator_details(
    features: Mapping[str, Any], *, notebook_compatible: bool = False
) -> dict[str, dict[str, Any]]:
    """Return v1.0 indicator scores and user-readable detail/availability."""
    scores, component_counts = _score_components(
        features, notebook_compatible=notebook_compatible
    )
    details: dict[str, dict[str, Any]] = {}
    for key, label, measures, sources, note in INDICATOR_META:
        score = scores[key]
        if score is not None:
            unavailable_reason = None
            availability = (
                "AVAILABLE"
                if component_counts[key]
                >= {
                    "cashflow_stability": 3,
                    "payment_discipline": 3,
                    "commitment_adherence": 2,
                    "debt_burden": 2,
                    "financial_stress": 4,
                    "financial_resilience": 3,
                }.get(key, 1)
                else "LIMITED"
            )
        elif key == "savings_discipline":
            availability, unavailable_reason = (
                "LIMITED",
                "Add income and bank information to calculate savings behaviour.",
            )
        elif key == "income_stability":
            availability, unavailable_reason = "AVAILABLE", None
        else:
            availability, unavailable_reason = (
                "LIMITED",
                f"Add {', '.join(sources).lower()} to calculate this indicator.",
            )
        details[key] = {
            "score": score,
            "available": score is not None,
            "availability": availability,
            "unavailable_reason": unavailable_reason,
            "label": label,
            "measures": measures,
            "based_on": list(sources),
            "methodology_note": note,
            "component_count": component_counts[key],
        }
    return details


def calculate_indicators(
    features: Mapping[str, Any], *, notebook_compatible: bool = False
) -> dict[str, float | None]:
    """Return the public eight-key indicator map, without SHAP/model inputs."""
    return {
        key: detail["score"]
        for key, detail in calculate_indicator_details(
            features, notebook_compatible=notebook_compatible
        ).items()
    }


def calculate_methodology_score(indicators: Mapping[str, Any]) -> float | None:
    """Equal-weight v1.0 composite, only when all eight indicators exist."""
    values = [indicators.get(key) for key, *_ in INDICATOR_META]
    if any(
        value is None or isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        return None
    return round(sum(float(value) for value in values) / 8, 2)

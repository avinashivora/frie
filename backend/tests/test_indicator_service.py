from pathlib import Path
import pandas as pd
import pytest

from app.services.indicator_service import calculate_indicator_details, calculate_indicators


def test_income_stability_uses_documented_employment_proxy_and_neutral_missing() -> None:
    assert calculate_indicators({"employment_years": 0})["income_stability"] == 0
    assert calculate_indicators({"employment_years": 10})["income_stability"] == 50
    assert calculate_indicators({"employment_years": 20})["income_stability"] == 100
    assert calculate_indicators({"employment_years": 24})["income_stability"] == 100
    details = calculate_indicator_details({})["income_stability"]
    assert details["score"] == 50
    assert details["availability"] == "LIMITED"
    assert "prototype proxy" in details["methodology_note"]


def test_savings_discipline_uses_twenty_percent_prototype_benchmark() -> None:
    assert calculate_indicators({"savings_rate": 0})["savings_discipline"] == 0
    assert calculate_indicators({"savings_rate": 0.1})["savings_discipline"] == 50
    assert calculate_indicators({"savings_rate": 0.2})["savings_discipline"] == 100
    assert calculate_indicators({"savings_rate": 0.3})["savings_discipline"] == 100
    assert calculate_indicators({"savings_rate": -0.1})["savings_discipline"] == 0
    assert calculate_indicators({})["savings_discipline"] is None


def test_all_eight_v1_formulas_and_component_weights() -> None:
    features = {
        "employment_years": 10, "cash_flow_mean": 100, "cash_flow_std": 50,
        "cash_flow_min": 20000, "cash_flow_negative_months": 3, "monthly_income": 100000,
        "on_time_payment_ratio": .8, "payment_coverage_ratio": .9, "average_payment_delay": 30,
        "savings_rate": .1, "insurance_payment_consistency": .5, "current_dti": .2,
        "bureau_debt_amount": 120000, "synthetic_total_expense": 60000,
        "bureau_overdue_days": 45, "savings_balance": 60000,
        "fd_amount": 1, "rd_contribution": 0, "sip_contribution": 1,
        "mutual_fund_balance": 0, "ppf_contribution": 0, "nps_contribution": 0,
    }
    scores = calculate_indicators(features)
    assert scores == pytest.approx({
        "income_stability": 50, "cashflow_stability": 51.5,
        "payment_discipline": 77, "savings_discipline": 50,
        "commitment_adherence": 62, "debt_burden": 70.5,
        "financial_stress": 46.5833333333, "financial_resilience": 30,
    })
    assert len(scores) == 8
    assert all(value is not None and 0 <= value <= 100 for value in scores.values())


def test_indicators_respect_missing_inputs_instead_of_creating_scores() -> None:
    scores = calculate_indicators({"employment_years": 5, "savings_rate": .1})
    assert scores["income_stability"] == 25
    assert scores["savings_discipline"] == 50
    assert all(value is None for key, value in scores.items() if key not in {"income_stability", "savings_discipline"})
    detail = calculate_indicator_details({})["payment_discipline"]
    assert detail["score"] is None
    assert detail["availability"] == "LIMITED"
    assert detail["unavailable_reason"]


def test_indicator_directionality() -> None:
    base = {
        "employment_years": 5, "cash_flow_mean": 100, "cash_flow_std": 80,
        "cash_flow_min": 10000, "cash_flow_negative_months": 6, "monthly_income": 100000,
        "on_time_payment_ratio": .5, "payment_coverage_ratio": .5, "average_payment_delay": 40,
        "savings_rate": .05, "insurance_payment_consistency": .4, "current_dti": .4,
        "bureau_debt_amount": 900000, "synthetic_total_expense": 90000,
        "bureau_overdue_days": 60, "savings_balance": 10000,
        "fd_amount": 0, "rd_contribution": 0, "sip_contribution": 0,
        "mutual_fund_balance": 0, "ppf_contribution": 0, "nps_contribution": 0,
    }
    changed = dict(base, cash_flow_std=10, cash_flow_negative_months=0,
                   on_time_payment_ratio=1, payment_coverage_ratio=1,
                   average_payment_delay=0, savings_rate=.2, current_dti=0,
                   bureau_debt_amount=0, synthetic_total_expense=30000,
                   bureau_overdue_days=0, savings_balance=180000,
                   sip_contribution=1)
    before, after = calculate_indicators(base), calculate_indicators(changed)
    for indicator in before:
        assert after[indicator] >= before[indicator]


def test_backend_matches_original_notebook_scored_1000_rows() -> None:
    """Compare against Frie_score.ipynb output within floating-point precision."""
    dataset = Path(r"D:\frie\Model Train\frie_scored_1000_calibrated.csv")
    if not dataset.is_file():
        pytest.skip("Original FRIE 1,000-row scored output is not available in this environment.")
    frame = pd.read_csv(dataset)
    keys = (
        "income_stability", "cashflow_stability", "payment_discipline", "savings_discipline",
        "commitment_adherence", "debt_burden", "financial_stress", "financial_resilience",
    )
    source_columns = (
        "employment_years", "cash_flow_mean", "cash_flow_std", "cash_flow_min", "cash_flow_negative_months",
        "monthly_income", "on_time_payment_ratio", "payment_coverage_ratio", "average_payment_delay",
        "savings_rate", "insurance_payment_consistency", "current_dti", "bureau_debt_amount",
        "synthetic_total_expense", "bureau_overdue_days", "savings_balance", "fd_amount", "rd_contribution",
        "sip_contribution", "mutual_fund_balance", "ppf_contribution", "nps_contribution",
    )
    predictions = [calculate_indicators(row, notebook_compatible=True) for row in frame[list(source_columns)].to_dict("records")]
    for key in keys:
        actual = pd.Series([row[key] for row in predictions], dtype="float64")
        difference = (actual - frame[f"{key}_score"]).abs()
        assert difference.max() < 1e-10, (key, difference.max())
        assert difference.mean() < 1e-11

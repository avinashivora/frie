from __future__ import annotations

from copy import deepcopy

from app.core.config import get_settings
from app.schemas.prediction import PredictionResponse
from app.services.prediction_service import PredictionService
from app.services.scoring.frie_score import DIMENSION_ORDER
from app.services.scoring.profiles import PROFILE_WEIGHTS


FEATURES = {
    "monthly_income": 75000.0,
    "current_dti": 0.24,
    "bureau_dti": 0.26,
    "current_loan_annuity": 9000.0,
    "synthetic_total_emi": 9000.0,
    "synthetic_total_expense": 36000.0,
    "available_surplus": 30000.0,
    "synthetic_spending_ratio": 0.48,
    "food_expense": 8000.0,
    "rent_expense": 15000.0,
    "education_expense": 2000.0,
    "healthcare_expense": 1500.0,
    "transport_expense": 3000.0,
    "utility_expense": 2500.0,
    "discretionary_expense": 4000.0,
    "cash_flow_mean": 30000.0,
    "cash_flow_std": 5000.0,
    "cash_flow_min": 12000.0,
    "cash_flow_negative_months": 0,
    "employment_years": 4.0,
    "income_type": "Salary",
    "contract_type": "Permanent",
    "savings_balance": 180000.0,
    "monthly_savings": 12000.0,
    "savings_rate": 0.16,
    "fd_amount": 30000.0,
    "rd_contribution": 2000.0,
    "mutual_fund_balance": 40000.0,
    "ppf_contribution": 1000.0,
    "nps_contribution": 1000.0,
    "health_insurance": 1,
    "life_insurance": 1,
    "insurance_premium": 1500.0,
    "insurance_payment_consistency": 0.95,
    "bureau_account_count": 3,
    "active_credit_count": 1,
    "closed_credit_count": 2,
    "bureau_credit_amount": 400000.0,
    "bureau_debt_amount": 90000.0,
    "bureau_credit_limit": 200000.0,
    "bureau_overdue_amount": 0.0,
    "bureau_overdue_days": 0.0,
    "bureau_overdue_account_count": 0.0,
    "total_installments": 30,
    "total_amount_due": 90000.0,
    "total_amount_paid": 90000.0,
    "total_late_payments": 0,
    "total_on_time_payments": 30,
    "average_payment_delay": 0.0,
    "total_payment_delay_days": 0.0,
    "payment_difference": 0.0,
    "on_time_payment_ratio": 1.0,
    "payment_coverage_ratio": 1.0,
    "previous_application_count": 2,
    "previous_approved_count": 2,
    "previous_refused_count": 0,
    "avg_credit_card_balance": 10000.0,
    "max_credit_card_balance": 12000.0,
    "avg_credit_limit": 50000.0,
    "avg_credit_utilisation": 0.20,
    "max_card_dpd": 0,
    "pos_account_records": 1,
    "avg_pos_installments": 12.0,
    "avg_future_installments": 4.0,
    "pos_dpd_count": 0,
    "max_pos_dpd": 0,
}


def assess(features):
    return PredictionService(get_settings()).predict(features)


def test_six_dimension_result_is_schema_valid_and_deterministic():
    first = assess(FEATURES)
    second = assess(deepcopy(FEATURES))
    assert first == second
    assert set(first["dimensions"]) == set(DIMENSION_ORDER)
    assert 0 <= first["frie_score"]["value"] <= 600
    assert 0 <= first["profile"]["score"] <= 100
    assert PredictionResponse.model_validate(first)
    for result in first["dimensions"].values():
        if result["score"] is not None:
            assert 0 <= result["score"] <= 100


def test_configured_and_effective_profile_weights_normalize():
    result = assess(FEATURES)
    for weights in PROFILE_WEIGHTS.values():
        assert abs(sum(weights.values()) - 1.0) < 1e-9
    effective = result["profile"]["effective_weights"]
    assert abs(sum(effective.values()) - 1.0) < 1e-6


def test_missing_credit_history_is_not_scored_as_zero():
    features = {key: value for key, value in FEATURES.items() if not key.startswith(("bureau_", "active_credit", "closed_credit", "total_", "average_payment", "payment_", "on_time_", "previous_", "avg_credit", "max_credit", "max_card", "pos_", "avg_pos", "avg_future", "max_pos_dpd"))}
    result = assess(features)
    assert result["dimensions"]["credit_behaviour"]["status"] == "NOT_ESTABLISHED"
    assert result["dimensions"]["credit_behaviour"]["score"] is None
    assert result["dimensions"]["commitment_adherence"]["coverage"] < 1.0
    assert result["frie_score"]["available_dimensions"] < 6


def test_missing_insurance_does_not_zero_commitment_dimension():
    features = dict(FEATURES)
    for key in ("health_insurance", "life_insurance", "insurance_premium", "insurance_payment_consistency"):
        features.pop(key)
    result = assess(features)
    commitment = result["dimensions"]["commitment_adherence"]
    assert commitment["score"] is not None and commitment["score"] > 0
    assert commitment["coverage"] < 1.0


def test_missing_bank_cashflow_group_keeps_income_evidence_partial():
    features = {
        "monthly_income": 75000.0,
        "employment_years": 4.0,
        "income_type": "Salary",
        "contract_type": "Permanent",
    }
    cashflow = assess(features)["dimensions"]["cashflow_stability"]
    assert cashflow["score"] is not None
    assert cashflow["coverage"] < 1.0
    assert cashflow["status"] == "LIMITED"


def test_dimensions_are_calculated_once_per_assessment(monkeypatch):
    import app.services.prediction_service as service_module

    original = service_module.calculate_dimensions
    calls = 0

    def counted(features):
        nonlocal calls
        calls += 1
        return original(features)

    monkeypatch.setattr(service_module, "calculate_dimensions", counted)
    PredictionService(get_settings()).predict(FEATURES, profile="loan")
    assert calls == 1


def test_zero_is_evidence_and_missing_is_not():
    zero = assess({"monthly_income": 75000.0, "synthetic_total_expense": 0.0})
    missing = assess({"monthly_income": 75000.0})
    zero_expense = zero["dimensions"]["spending_behaviour"]
    missing_expense = missing["dimensions"]["spending_behaviour"]
    assert zero_expense["score"] is not None
    assert missing_expense["score"] is None


def test_high_dti_and_negative_surplus_lower_affordability():
    baseline = assess(FEATURES)["dimensions"]["affordability"]["score"]
    pressured = dict(FEATURES, current_dti=0.70, bureau_dti=0.70, available_surplus=-1000.0)
    assert assess(pressured)["dimensions"]["affordability"]["score"] < baseline


def test_underpayment_is_not_rewarded_as_overpayment():
    underpaid = dict(FEATURES, payment_difference=5000.0)
    overpaid = dict(FEATURES, payment_difference=-5000.0)
    underpaid_score = assess(underpaid)["dimensions"]["credit_behaviour"]["score"]
    overpaid_score = assess(overpaid)["dimensions"]["credit_behaviour"]["score"]
    assert overpaid_score >= underpaid_score


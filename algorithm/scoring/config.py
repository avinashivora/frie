AFFORDABILITY_WEIGHTS = {
    "expense_ratio": 0.20,
    "emi_ratio": 0.25,
    "surplus_ratio": 0.20,
    "current_dti": 0.20,
    "bureau_dti": 0.15,
}

STABILITY_WEIGHTS = {
    "cashflow_volatility": 0.35,
    "cashflow_min": 0.25,
    "negative_months": 0.25,
    "employment_stability": 0.15,
}

CREDIT_WEIGHTS = {
    "payment_reliability": 0.20,
    "payment_coverage": 0.15,
    "overdue_ratio": 0.15,
    "overdue_days": 0.10,
    "overdue_accounts": 0.10,
    "credit_utilisation": 0.10,
    "credit_prolongation": 0.05,
    "card_dpd": 0.05,
    "pos_dpd": 0.05,
    "previous_approval": 0.05,
}

COMMITMENT_WEIGHTS = {
    "payment_adherence": 0.30,
    "payment_coverage": 0.25,
    "payment_difference": 0.15,
    "late_payment_frequency": 0.15,
    "insurance_payment_adherence": 0.15,
}

RESILIENCE_WEIGHTS = {
    "savings_rate": 0.25,
    "liquidity_buffer": 0.35,
    "long_term_assets": 0.20,
    "surplus_ratio": 0.20,
}

SPENDING_WEIGHTS = {
    "spending_burden": 0.40,
    "discretionary_ratio": 0.30,
    "upi_income_ratio": 0.15,
    "digital_payment_ratio": 0.15,
}
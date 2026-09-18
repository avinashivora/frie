import pandas as pd


EXPECTED_COLUMNS = [
    "customer_id",
    "gender",
    "age_years",
    "children_count",
    "family_size",
    "family_status",
    "education_level",
    "housing_type",
    "owns_car",
    "owns_property",
    "monthly_income",
    "income_type",
    "employment_years",
    "occupation",
    "organization_type",
    "contract_type",
    "current_credit_amount",
    "current_loan_annuity",
    "goods_price",
    "bureau_account_count",
    "active_credit_count",
    "closed_credit_count",
    "bureau_credit_amount",
    "bureau_debt_amount",
    "bureau_credit_limit",
    "bureau_overdue_amount",
    "bureau_overdue_days",
    "bureau_overdue_account_count",
    "credit_prolongation_count",
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
    "previous_application_count",
    "previous_approved_count",
    "previous_refused_count",
    "previous_credit_amount",
    "previous_avg_credit",
    "previous_avg_annuity",
    "previous_avg_down_payment",
    "avg_credit_card_balance",
    "max_credit_card_balance",
    "avg_credit_limit",
    "total_card_drawings",
    "total_card_payments",
    "avg_minimum_payment",
    "avg_credit_utilisation",
    "max_card_dpd",
    "max_card_dpd_default",
    "pos_account_records",
    "avg_pos_installments",
    "avg_future_installments",
    "pos_dpd_count",
    "max_pos_dpd",
    "max_pos_dpd_default",
    "current_dti",
    "bureau_dti",
    "previous_approval_ratio",
    "city_tier",
    "occupation_band",
    "indian_household_size",
    "synthetic_spending_ratio",
    "food_expense",
    "rent_expense",
    "education_expense",
    "healthcare_expense",
    "transport_expense",
    "utility_expense",
    "discretionary_expense",
    "synthetic_total_expense",
    "synthetic_total_emi",
    "available_surplus",
    "monthly_savings",
    "savings_rate",
    "savings_balance",
    "fd_amount",
    "rd_contribution",
    "upi_spending",
    "upi_transaction_count",
    "digital_payment_ratio",
    "sip_contribution",
    "mutual_fund_balance",
    "ppf_contribution",
    "nps_contribution",
    "health_insurance",
    "life_insurance",
    "insurance_premium",
    "insurance_payment_consistency",
    "cash_flow_mean",
    "cash_flow_std",
    "cash_flow_min",
    "cash_flow_negative_months",
]


NON_NEGATIVE_COLUMNS = [
    "children_count",
    "family_size",
    "monthly_income",
    "employment_years",
    "current_credit_amount",
    "current_loan_annuity",
    "goods_price",
    "bureau_account_count",
    "active_credit_count",
    "closed_credit_count",
    "bureau_credit_amount",
    "bureau_debt_amount",
    "bureau_credit_limit",
    "bureau_overdue_amount",
    "bureau_overdue_days",
    "bureau_overdue_account_count",
    "credit_prolongation_count",
    "total_installments",
    "total_amount_due",
    "total_amount_paid",
    "total_late_payments",
    "total_on_time_payments",
    "average_payment_delay",
    "total_payment_delay_days",
    "previous_application_count",
    "previous_approved_count",
    "previous_refused_count",
    "previous_credit_amount",
    "previous_avg_credit",
    "previous_avg_annuity",
    "previous_avg_down_payment",
    "avg_credit_card_balance",
    "max_credit_card_balance",
    "avg_credit_limit",
    "total_card_drawings",
    "total_card_payments",
    "avg_minimum_payment",
    "avg_credit_utilisation",
    "max_card_dpd",
    "max_card_dpd_default",
    "pos_account_records",
    "avg_pos_installments",
    "avg_future_installments",
    "pos_dpd_count",
    "max_pos_dpd",
    "max_pos_dpd_default",
    "current_dti",
    "bureau_dti",
    "synthetic_spending_ratio",
    "food_expense",
    "rent_expense",
    "education_expense",
    "healthcare_expense",
    "transport_expense",
    "utility_expense",
    "discretionary_expense",
    "synthetic_total_expense",
    "synthetic_total_emi",
    "monthly_savings",
    "savings_balance",
    "fd_amount",
    "rd_contribution",
    "upi_spending",
    "upi_transaction_count",
    "sip_contribution",
    "mutual_fund_balance",
    "ppf_contribution",
    "nps_contribution",
    "insurance_premium",
    "cash_flow_negative_months",
]


BOUNDED_COLUMNS = [
    "on_time_payment_ratio",
    "payment_coverage_ratio",
    "previous_approval_ratio",
    "avg_credit_utilisation",
    "synthetic_spending_ratio",
    "savings_rate",
    "digital_payment_ratio",
    "insurance_payment_consistency",
]


BINARY_COLUMNS = [
    "owns_car",
    "owns_property",
    "health_insurance",
    "life_insurance",
]


def validate_schema(df: pd.DataFrame) -> dict:
    errors = []
    warnings = []

    missing_columns = [
        col for col in EXPECTED_COLUMNS
        if col not in df.columns
    ]

    unexpected_columns = [
        col for col in df.columns
        if col not in EXPECTED_COLUMNS
    ]

    if missing_columns:
        errors.append({
            "type": "missing_columns",
            "columns": missing_columns
        })

    if unexpected_columns:
        warnings.append({
            "type": "unexpected_columns",
            "columns": unexpected_columns
        })

    return errors, warnings


def validate_duplicates(df: pd.DataFrame) -> list:
    errors = []

    if "customer_id" in df.columns:
        duplicates = df[df["customer_id"].duplicated(keep=False)]

        if not duplicates.empty:
            errors.append({
                "type": "duplicate_customer_id",
                "customer_ids": duplicates["customer_id"].tolist()
            })

    return errors


def validate_numeric_ranges(df: pd.DataFrame) -> list:
    errors = []

    for column in NON_NEGATIVE_COLUMNS:
        if column not in df.columns:
            continue

        invalid = df[column].notna() & (df[column] < 0)

        if invalid.any():
            errors.append({
                "type": "negative_value",
                "column": column,
                "rows": df.index[invalid].tolist()
            })

    for column in BOUNDED_COLUMNS:
        if column not in df.columns:
            continue

        invalid = df[column].notna() & (
            (df[column] < 0) | (df[column] > 1)
        )

        if invalid.any():
            errors.append({
                "type": "out_of_range",
                "column": column,
                "expected": "0 <= value <= 1",
                "rows": df.index[invalid].tolist()
            })

    return errors


def validate_binary_columns(df: pd.DataFrame) -> list:
    errors = []

    for column in BINARY_COLUMNS:
        if column not in df.columns:
            continue

        invalid = df[column].notna() & ~df[column].isin([0, 1])

        if invalid.any():
            errors.append({
                "type": "invalid_binary_value",
                "column": column,
                "expected": [0, 1],
                "rows": df.index[invalid].tolist()
            })

    return errors


def validate_relationships(df: pd.DataFrame) -> list:
    warnings = []

    required = [
        "total_installments",
        "total_late_payments",
        "total_on_time_payments",
    ]

    if all(col in df.columns for col in required):
        invalid = (
            df["total_late_payments"] +
            df["total_on_time_payments"]
            > df["total_installments"]
        )

        if invalid.any():
            warnings.append({
                "type": "payment_count_mismatch",
                "rows": df.index[invalid].tolist()
            })

    required = [
        "monthly_income",
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
    ]

    if all(col in df.columns for col in required):
        expected_surplus = (
            df["monthly_income"]
            - df["synthetic_total_expense"]
            - df["synthetic_total_emi"]
        )

        tolerance = 0.01 * df["monthly_income"].abs().clip(lower=1)

        invalid = (
            df["available_surplus"].notna()
            & expected_surplus.notna()
            & (
                (df["available_surplus"] - expected_surplus).abs()
                > tolerance
            )
        )

        if invalid.any():
            warnings.append({
                "type": "surplus_consistency_warning",
                "rows": df.index[invalid].tolist()
            })

    return warnings


def validate_dataframe(df: pd.DataFrame) -> dict:
    errors, warnings = validate_schema(df)

    errors.extend(validate_duplicates(df))
    errors.extend(validate_numeric_ranges(df))
    errors.extend(validate_binary_columns(df))
    warnings.extend(validate_relationships(df))

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
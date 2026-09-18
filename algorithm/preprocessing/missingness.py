import pandas as pd


FEATURE_GROUPS = {
    "credit": [
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
    ],

    "cashflow": [
        "monthly_income",
        "income_type",
        "employment_years",
        "contract_type",
        "cash_flow_mean",
        "cash_flow_std",
        "cash_flow_min",
        "cash_flow_negative_months",
    ],

    "affordability": [
        "monthly_income",
        "current_credit_amount",
        "current_loan_annuity",
        "current_dti",
        "bureau_dti",
        "synthetic_total_expense",
        "synthetic_total_emi",
        "available_surplus",
        "synthetic_spending_ratio",
    ],

    "resilience": [
        "monthly_savings",
        "savings_rate",
        "savings_balance",
        "fd_amount",
        "rd_contribution",
        "sip_contribution",
        "mutual_fund_balance",
        "ppf_contribution",
        "nps_contribution",
    ],

    "commitments": [
        "total_installments",
        "total_amount_due",
        "total_amount_paid",
        "total_late_payments",
        "total_on_time_payments",
        "payment_difference",
        "on_time_payment_ratio",
        "payment_coverage_ratio",
        "insurance_premium",
        "insurance_payment_consistency",
    ],

    "spending": [
        "food_expense",
        "rent_expense",
        "education_expense",
        "healthcare_expense",
        "transport_expense",
        "utility_expense",
        "discretionary_expense",
        "synthetic_total_expense",
        "synthetic_spending_ratio",
        "upi_spending",
        "upi_transaction_count",
        "digital_payment_ratio",
    ],
}


def calculate_column_missingness(df: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=df.columns)

    result["missing_count"] = df.isna().sum()
    result["observed_count"] = df.notna().sum()
    result["missing_ratio"] = df.isna().mean()
    result["available_ratio"] = df.notna().mean()

    return result


def calculate_group_coverage(df: pd.DataFrame) -> pd.DataFrame:
    records = []

    for group, columns in FEATURE_GROUPS.items():
        available_columns = [
            column for column in columns
            if column in df.columns
        ]

        if not available_columns:
            records.append({
                "group": group,
                "coverage": 0.0,
                "available_features": 0,
                "total_features": len(columns),
            })
            continue

        coverage = df[available_columns].notna().mean(axis=1)

        records.append({
            "group": group,
            "coverage": coverage.mean(),
            "available_features": len(available_columns),
            "total_features": len(columns),
        })

    return pd.DataFrame(records)


def add_row_availability_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for group, columns in FEATURE_GROUPS.items():
        available_columns = [
            column for column in columns
            if column in df.columns
        ]

        if not available_columns:
            df[f"{group}_data_available"] = False
            df[f"{group}_data_coverage"] = 0.0
            continue

        coverage = df[available_columns].notna().mean(axis=1)

        df[f"{group}_data_coverage"] = coverage

        df[f"{group}_data_available"] = coverage > 0

    return df


def generate_missingness_report(df: pd.DataFrame) -> dict:
    column_report = calculate_column_missingness(df)
    group_report = calculate_group_coverage(df)

    return {
        "column_missingness": column_report,
        "group_coverage": group_report,
        "overall_coverage": float(df.notna().mean().mean()),
    }


def process_missingness(df: pd.DataFrame):
    processed_df = add_row_availability_flags(df)

    report = generate_missingness_report(processed_df)

    return processed_df, report
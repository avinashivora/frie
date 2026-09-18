import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_resilience_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    income = df["monthly_income"].replace(0, pd.NA)

    savings_rate = (
        df["monthly_savings"] / income
    )

    monthly_expenses = (
        df["synthetic_total_expense"]
        + df["synthetic_total_emi"]
    ).replace(0, pd.NA)

    liquid_assets = (
        df["savings_balance"]
        + df["fd_amount"]
        + df["rd_contribution"]
    )

    liquidity_buffer = (
        liquid_assets / monthly_expenses
    )

    long_term_assets = (
        df["mutual_fund_balance"]
        + df["ppf_contribution"]
        + df["nps_contribution"]
    )

    out["savings_rate"] = normalize_indicator(
        savings_rate,
        method="threshold",
        higher_is_better=True,
        thresholds=[
            (0.00, 0),
            (0.05, 25),
            (0.10, 50),
            (0.20, 75),
            (0.30, 90),
            (float("inf"), 100),
        ],
    )

    out["liquidity_buffer"] = normalize_indicator(
        liquidity_buffer,
        method="threshold",
        higher_is_better=True,
        thresholds=[
            (0.25, 10),
            (0.50, 25),
            (1.00, 50),
            (3.00, 75),
            (6.00, 90),
            (float("inf"), 100),
        ],
    )

    out["long_term_assets"] = normalize_indicator(
        long_term_assets,
        method="percentile",
        higher_is_better=True,
    )

    out["surplus_ratio"] = normalize_indicator(
        df["available_surplus"] / income,
        method="threshold",
        higher_is_better=True,
        thresholds=[
            (0.00, 0),
            (0.05, 25),
            (0.10, 50),
            (0.20, 75),
            (0.30, 90),
            (float("inf"), 100),
        ],
    )

    return out
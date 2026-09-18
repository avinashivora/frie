import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_spending_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    income = df["monthly_income"].replace(0, pd.NA)

    expense_ratio = (
        df["synthetic_total_expense"] / income
    )

    discretionary_ratio = (
        df["discretionary_expense"]
        / df["synthetic_total_expense"].replace(0, pd.NA)
    )

    upi_income_ratio = (
        df["upi_spending"] / income
    )

    out["spending_burden"] = normalize_indicator(
        expense_ratio,
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.30, 100),
            (0.40, 90),
            (0.50, 75),
            (0.60, 55),
            (0.70, 35),
            (0.80, 15),
            (float("inf"), 0),
        ],
    )

    out["discretionary_ratio"] = normalize_indicator(
        discretionary_ratio,
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 55),
            (0.50, 30),
            (float("inf"), 0),
        ],
    )

    out["upi_income_ratio"] = normalize_indicator(
        upi_income_ratio,
        method="minmax",
        higher_is_better=False,
    )

    out["digital_payment_ratio"] = normalize_indicator(
        df["digital_payment_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    return out
import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_affordability_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    income = df["monthly_income"].replace(0, pd.NA)

    expense_ratio = (
        df["synthetic_total_expense"] / income
    )

    emi_ratio = (
        df["synthetic_total_emi"] / income
    )

    surplus_ratio = (
        df["available_surplus"] / income
    )

    out["expense_ratio"] = normalize_indicator(
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

    out["emi_ratio"] = normalize_indicator(
        emi_ratio,
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 50),
            (0.50, 25),
            (float("inf"), 0),
        ],
    )

    out["surplus_ratio"] = normalize_indicator(
        surplus_ratio,
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

    out["current_dti"] = normalize_indicator(
        df["current_dti"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 50),
            (0.50, 25),
            (float("inf"), 0),
        ],
    )

    out["bureau_dti"] = normalize_indicator(
        df["bureau_dti"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.10, 100),
            (0.20, 90),
            (0.30, 75),
            (0.40, 50),
            (0.50, 25),
            (float("inf"), 0),
        ],
    )

    return out
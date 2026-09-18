import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_cashflow_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    mean_cashflow = df["cash_flow_mean"].abs().replace(0, pd.NA)

    volatility = (
        df["cash_flow_std"] / mean_cashflow
    )

    out["cashflow_volatility"] = normalize_indicator(
        volatility,
        method="minmax",
        higher_is_better=False,
    )

    out["cashflow_min"] = normalize_indicator(
        df["cash_flow_min"],
        method="robust_zscore",
        higher_is_better=True,
    )

    out["negative_months"] = normalize_indicator(
        df["cash_flow_negative_months"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (1, 85),
            (2, 70),
            (3, 50),
            (4, 30),
            (6, 10),
            (float("inf"), 0),
        ],
    )

    out["employment_stability"] = normalize_indicator(
        df["employment_years"],
        method="minmax",
        higher_is_better=True,
    )

    return out
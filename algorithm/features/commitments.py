import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_commitment_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    out["payment_adherence"] = normalize_indicator(
        df["on_time_payment_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    out["payment_coverage"] = normalize_indicator(
        df["payment_coverage_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    out["payment_difference"] = normalize_indicator(
        df["payment_difference"],
        method="robust_zscore",
        higher_is_better=True,
    )

    out["late_payment_frequency"] = normalize_indicator(
        df["total_late_payments"],
        method="percentile",
        higher_is_better=False,
    )

    out["insurance_payment_adherence"] = normalize_indicator(
        df["insurance_payment_consistency"],
        method="bounded",
        higher_is_better=True,
    )

    return out
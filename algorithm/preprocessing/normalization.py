import numpy as np
import pandas as pd


def bounded_score(
    series: pd.Series,
    higher_is_better: bool = True
) -> pd.Series:
    """
    Normalize a 0-1 variable to a 0-100 score.
    """

    score = series.clip(0, 1) * 100

    if not higher_is_better:
        score = 100 - score

    return score


def minmax_score(
    series: pd.Series,
    higher_is_better: bool = True,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99
) -> pd.Series:
    """
    Robust min-max normalization using percentile bounds.
    """

    result = pd.Series(np.nan, index=series.index, dtype=float)

    valid = series.dropna()

    if valid.empty:
        return result

    lower = valid.quantile(lower_quantile)
    upper = valid.quantile(upper_quantile)

    if lower == upper:
        result.loc[valid.index] = 50.0
        return result

    clipped = series.clip(lower, upper)

    score = (
        (clipped - lower) /
        (upper - lower)
    ) * 100

    if not higher_is_better:
        score = 100 - score

    return score


def percentile_score(
    series: pd.Series,
    higher_is_better: bool = True
) -> pd.Series:
    """
    Convert observations to percentile-based 0-100 scores.
    """

    result = series.rank(
        pct=True,
        method="average"
    ) * 100

    if not higher_is_better:
        result = 100 - result

    return result


def threshold_score(
    series: pd.Series,
    thresholds: list,
    higher_is_better: bool = True
) -> pd.Series:
    """
    Piecewise threshold scoring.

    thresholds:
        [(upper_bound, score), ...]
    """

    result = pd.Series(np.nan, index=series.index, dtype=float)

    for idx, value in series.items():

        if pd.isna(value):
            continue

        assigned_score = thresholds[-1][1]

        for bound, score in thresholds:
            if value <= bound:
                assigned_score = score
                break

        result.loc[idx] = assigned_score

    if higher_is_better:
        return result

    return 100 - result


def robust_zscore(
    series: pd.Series,
    higher_is_better: bool = True
) -> pd.Series:
    """
    Robust standardization using median and MAD,
    converted to a bounded 0-100 score.
    """

    median = series.median()
    mad = (series - median).abs().median()

    if pd.isna(mad) or mad == 0:
        return pd.Series(
            50.0,
            index=series.index
        )

    robust_z = (series - median) / (1.4826 * mad)

    # Bound influence of extreme observations
    robust_z = robust_z.clip(-3, 3)

    score = ((robust_z + 3) / 6) * 100

    if not higher_is_better:
        score = 100 - score

    return score


def normalize_indicator(
    series: pd.Series,
    method: str,
    higher_is_better: bool = True,
    **kwargs
) -> pd.Series:

    if method == "bounded":
        return bounded_score(
            series,
            higher_is_better
        )

    if method == "minmax":
        return minmax_score(
            series,
            higher_is_better,
            **kwargs
        )

    if method == "percentile":
        return percentile_score(
            series,
            higher_is_better
        )

    if method == "threshold":
        return threshold_score(
            series,
            kwargs["thresholds"],
            higher_is_better
        )

    if method == "robust_zscore":
        return robust_zscore(
            series,
            higher_is_better
        )

    raise ValueError(
        f"Unknown normalization method: {method}"
    )
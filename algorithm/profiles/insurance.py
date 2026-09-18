import pandas as pd

from profiles.config import INSURANCE_WEIGHTS


def calculate_insurance_score(scores: pd.DataFrame) -> pd.Series:
    weighted_score = pd.Series(0.0, index=scores.index)
    available_weight = pd.Series(0.0, index=scores.index)

    for dimension, weight in INSURANCE_WEIGHTS.items():
        if dimension not in scores.columns:
            continue

        values = pd.to_numeric(scores[dimension], errors="coerce")
        valid = values.notna()

        weighted_score.loc[valid] += values.loc[valid] * weight
        available_weight.loc[valid] += weight

    return (
        weighted_score.div(available_weight)
        .clip(0, 100)
        .round(2)
    )
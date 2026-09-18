import pandas as pd
from config import RESILIENCE_WEIGHTS


def calculate_resilience_score(features: pd.DataFrame) -> pd.Series:
    weighted_score = pd.Series(0.0, index=features.index)
    available_weight = pd.Series(0.0, index=features.index)

    for feature, weight in RESILIENCE_WEIGHTS.items():
        if feature not in features.columns:
            continue

        values = pd.to_numeric(features[feature], errors="coerce")
        valid = values.notna()

        weighted_score.loc[valid] += values.loc[valid] * weight
        available_weight.loc[valid] += weight

    score = weighted_score.div(available_weight).mul(100)
    return score.clip(0, 100).round(2)
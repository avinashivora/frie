import pandas as pd


def get_dimension_contributors(
    scores: pd.DataFrame,
    weights: dict,
    top_n: int = 3,
) -> pd.DataFrame:
    results = []

    for index, row in scores.iterrows():
        contributions = {}

        for dimension, weight in weights.items():
            value = row.get(dimension)

            if pd.notna(value):
                contributions[dimension] = value * weight

        ranked = sorted(
            contributions.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

        results.append(
            {
                "customer_id": index,
                "contributors": ranked,
            }
        )

    return pd.DataFrame(results)
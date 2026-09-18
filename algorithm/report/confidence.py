import pandas as pd


DIMENSION_COVERAGE = {
    "credit_score": "credit_data_coverage",
    "affordability_score": "affordability_data_coverage",
    "cashflow_stability_score": "cashflow_data_coverage",
    "resilience_score": "resilience_data_coverage",
    "commitment_score": "commitment_data_coverage",
    "spending_score": "spending_data_coverage",
}


def calculate_dimension_coverage(
    df: pd.DataFrame,
) -> pd.DataFrame:
    coverage = pd.DataFrame(index=df.index)

    for score, coverage_column in DIMENSION_COVERAGE.items():
        if coverage_column in df.columns:
            coverage[score] = (
                pd.to_numeric(
                    df[coverage_column],
                    errors="coerce",
                )
                .clip(0, 1)
                .mul(100)
                .round(2)
            )
        else:
            coverage[score] = pd.NA

    return coverage


def calculate_overall_coverage(
    dimension_coverage: pd.DataFrame,
) -> pd.Series:
    return (
        dimension_coverage
        .mean(axis=1, skipna=True)
        .round(2)
    )


def classify_confidence(
    coverage: pd.Series,
) -> pd.Series:
    return pd.cut(
        coverage,
        bins=[-1, 49.99, 79.99, 100],
        labels=["Low", "Moderate", "High"],
    )
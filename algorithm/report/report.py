import pandas as pd

from report.confidence import (
    calculate_dimension_coverage,
    calculate_overall_coverage,
    classify_confidence,
)


def build_report(
    df: pd.DataFrame,
    scores: pd.DataFrame,
    profiles: pd.DataFrame,
) -> pd.DataFrame:

    dimension_coverage = calculate_dimension_coverage(df)

    overall_coverage = calculate_overall_coverage(
        dimension_coverage
    )

    confidence = classify_confidence(
        overall_coverage
    )

    report = pd.DataFrame(index=df.index)

    report["neutral_score"] = profiles["neutral_score"]
    report["loan_score"] = profiles["loan_score"]
    report["insurance_score"] = profiles["insurance_score"]

    report["credit_score"] = scores["credit_score"]
    report["affordability_score"] = scores["affordability_score"]
    report["cashflow_stability_score"] = (
        scores["cashflow_stability_score"]
    )
    report["resilience_score"] = scores["resilience_score"]
    report["commitment_score"] = scores["commitment_score"]
    report["spending_score"] = scores["spending_score"]

    report["data_coverage"] = overall_coverage
    report["confidence"] = confidence.astype(str)

    return report
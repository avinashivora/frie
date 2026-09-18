# IMPORTS
import pandas as pd
from constants import DATA_PATH

from preprocessing import (
    validate_dataframe, 
    process_missingness,
    normalize_indicator
)

from features import (
    build_credit_features,
    build_affordability_features,
    build_cashflow_features,
    build_resilience_features,
    build_commitment_features,
    build_spending_features
)

from scoring import (
    calculate_credit_score,
    calculate_affordability_score,
    calculate_stability_score,
    calculate_resilience_score,
    calculate_commitment_score,
    calculate_spending_score,
)

from profile import (
    calculate_neutral_score,
    calculate_loan_score,
    calculate_insurance_score
)

from report import (
    build_report
)


# STANDARD PIPELINE FUNCTIONS

def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def preprocess(df: pd.DataFrame):
    validation_report = validate_dataframe(df)

    if not validation_report["is_valid"]:
        raise ValueError(
            f"Validation failed: {validation_report['errors']}"
        )

    processed_df, missingness_report = process_missingness(df)

    return processed_df, validation_report, missingness_report


def build_all_features(df: pd.DataFrame) -> dict:
    return {
        "credit": build_credit_features(df),
        "affordability": build_affordability_features(df),
        "cashflow": build_cashflow_features(df),
        "resilience": build_resilience_features(df),
        "commitments": build_commitment_features(df),
        "spending": build_spending_features(df),
    }


def calculate_component_scores(features):
    scores = pd.DataFrame(index=features.index)

    scores["credit_score"] = calculate_credit_score(features)
    scores["affordability_score"] = calculate_affordability_score(features)
    scores["cashflow_stability_score"] = calculate_stability_score(features)
    scores["resilience_score"] = calculate_resilience_score(features)
    scores["commitment_score"] = calculate_commitment_score(features)
    scores["spending_score"] = calculate_spending_score(features)

    return scores


def build_profiles(scores):
    profiles = scores.copy()

    profiles["neutral_score"] = calculate_neutral_score(scores)
    profiles["loan_score"] = calculate_loan_score(scores)
    profiles["insurance_score"] = calculate_insurance_score(scores)

    return profiles


def build_frie_report(df, scores, profiles):
    return build_report(
        df=df,
        scores=scores,
        profiles=profiles,
    )
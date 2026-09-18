from pipeline import (
    load_data,
    preprocess,
    build_all_features,
    calculate_component_scores,
    build_profiles,
    build_frie_report,
)

from constants import DATA_PATH

# MAIN EXECUTION BLOCK

def main():
    # 1. Load the data
    df = load_data()

    # 2. Validate + missingness
    processed_df, validation, missingness = preprocess(df)

    # 3. Feature engineering
    features = build_all_features(processed_df)

    # 4. Dimension scores
    scores = calculate_component_scores(features)

    # 5. Purpose-specific profiles
    profiles = build_profiles(scores)

    # 6. Final FRIE report
    report = build_frie_report(df, scores, profiles)

    print(f"\nVALIDATION REPORT")
    print(validation)

    print(f"\nMISSINGNESS REPORT")
    print(missingness)
    
    print(f"\nFEATURES")
    for name, feature_df in features.items():
        print(f"\n{name.upper()}")
        print(feature_df.head())

    print(f"\nCOMPONENT SCORES")
    print(scores.head())

    print(f"\nPROFILES")
    print(profiles.head())

    print(f"\nFRIE REPORT")
    print(report.head())


if __name__ == "__main__":
    main()
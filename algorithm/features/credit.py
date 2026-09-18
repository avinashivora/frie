import pandas as pd

from preprocessing.normalization import normalize_indicator


def build_credit_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    # Payment reliability
    out["payment_reliability"] = normalize_indicator(
        df["on_time_payment_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    # Payment coverage
    out["payment_coverage"] = normalize_indicator(
        df["payment_coverage_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    # Overdue amount relative to credit exposure
    overdue_ratio = (
        df["bureau_overdue_amount"]
        / df["bureau_credit_amount"].replace(0, pd.NA)
    )

    out["overdue_ratio"] = normalize_indicator(
        overdue_ratio,
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.00, 100),
            (0.02, 85),
            (0.05, 70),
            (0.10, 50),
            (0.20, 25),
            (float("inf"), 0),
        ],
    )

    # Delinquency severity
    out["overdue_days"] = normalize_indicator(
        df["bureau_overdue_days"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (7, 90),
            (30, 70),
            (60, 50),
            (90, 25),
            (180, 10),
            (float("inf"), 0),
        ],
    )

    # Number of overdue accounts
    out["overdue_accounts"] = normalize_indicator(
        df["bureau_overdue_account_count"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (1, 75),
            (2, 50),
            (3, 25),
            (float("inf"), 0),
        ],
    )

    # Credit utilisation
    out["credit_utilisation"] = normalize_indicator(
        df["avg_credit_utilisation"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0.10, 100),
            (0.30, 90),
            (0.50, 75),
            (0.70, 55),
            (0.90, 30),
            (1.00, 10),
            (float("inf"), 0),
        ],
    )

    # Credit prolongation
    out["credit_prolongation"] = normalize_indicator(
        df["credit_prolongation_count"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (1, 80),
            (2, 60),
            (3, 40),
            (5, 20),
            (float("inf"), 0),
        ],
    )

    # Card delinquency
    out["card_dpd"] = normalize_indicator(
        df["max_card_dpd"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (7, 90),
            (30, 70),
            (60, 50),
            (90, 25),
            (180, 0),
            (float("inf"), 0),
        ],
    )

    # POS delinquency
    out["pos_dpd"] = normalize_indicator(
        df["max_pos_dpd"],
        method="threshold",
        higher_is_better=False,
        thresholds=[
            (0, 100),
            (7, 90),
            (30, 70),
            (60, 50),
            (90, 25),
            (180, 0),
            (float("inf"), 0),
        ],
    )

    # Previous application approval behaviour
    out["previous_approval"] = normalize_indicator(
        df["previous_approval_ratio"],
        method="bounded",
        higher_is_better=True,
    )

    return out
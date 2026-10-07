"""Missing-Feature FRIE Score Approximation Experiment.

This script trains and evaluates models that can handle missing features
by simulating realistic document-level missingness scenarios.

Uses the existing 1,000-row scored dataset as ground truth.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

# Feature groups for document-level missingness simulation
DOCUMENT_GROUPS = {
    "bank_statement": [
        "food_expense", "rent_expense", "education_expense", "healthcare_expense",
        "transport_expense", "utility_expense", "discretionary_expense",
        "monthly_savings", "savings_balance", "upi_spending", "upi_transaction_count",
        "cash_flow_mean", "cash_flow_std", "cash_flow_min", "cash_flow_negative_months",
        "synthetic_total_expense", "synthetic_total_emi", "available_surplus",
        "savings_rate", "synthetic_spending_ratio", "digital_payment_ratio",
    ],
    "credit_report": [
        "bureau_account_count", "active_credit_count", "closed_credit_count",
        "bureau_credit_amount", "bureau_debt_amount", "bureau_credit_limit",
        "bureau_overdue_amount", "bureau_overdue_days", "bureau_overdue_account_count",
        "credit_prolongation_count", "total_installments", "total_amount_due",
        "total_amount_paid", "total_late_payments", "total_on_time_payments",
        "average_payment_delay", "total_payment_delay_days", "payment_difference",
        "on_time_payment_ratio", "payment_coverage_ratio", "previous_application_count",
        "previous_approved_count", "previous_refused_count", "previous_credit_amount",
        "previous_avg_credit", "previous_avg_annuity", "previous_avg_down_payment",
        "avg_credit_card_balance", "max_credit_card_balance", "avg_credit_limit",
        "total_card_drawings", "total_card_payments", "avg_minimum_payment",
        "avg_credit_utilisation", "max_card_dpd", "max_card_dpd_default",
        "pos_account_records", "avg_pos_installments", "avg_future_installments",
        "pos_dpd_count", "max_pos_dpd", "max_pos_dpd_default",
        "current_dti", "bureau_dti", "previous_approval_ratio", "bureau_overdue_ratio",
    ],
    "loan_document": [
        "current_credit_amount", "current_loan_annuity", "goods_price",
    ],
    "insurance_document": [
        "health_insurance", "life_insurance", "insurance_premium", "insurance_payment_consistency",
    ],
    "investment_statement": [
        "fd_amount", "rd_contribution", "sip_contribution", "mutual_fund_balance",
        "ppf_contribution", "nps_contribution",
    ],
    "salary_income_proof": [
        "monthly_income", "employment_years",
    ],
}

# Scenarios: which document groups are missing
SCENARIOS = {
    "A": {"bank_statement"},
    "B": {"credit_report"},
    "C": {"insurance_document"},
    "D": {"investment_statement"},
    "E": {"bank_statement", "insurance_document"},
    "F": {"bank_statement", "investment_statement"},
    "G": {"credit_report", "insurance_document", "investment_statement"},
    "H": {"random_10"},  # 10% random features missing
    "I": {"random_20"},  # 20% random features missing
    "J": {"random_30"},  # 30% random features missing
    "K": {"random_40"},  # 40% random features missing
}


@dataclass
class ExperimentResult:
    scenario: str
    features_available: int
    mae: float
    rmse: float
    r2: float
    model_type: str


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    """Load the scored 1000-row dataset."""
    df = pd.read_csv(r"D:\frie\Model Train\frie_scored_1000_calibrated.csv")
    
    # Features from the model contract
    with open(r"D:\frie\Frontend\Frie\backend\models\frie_model_config_v2.json") as f:
        config = json.load(f)
    
    numeric_features = config["numeric_features"]
    categorical_features = config["categorical_features"]
    feature_names = numeric_features + categorical_features
    
    # Ensure all features exist
    missing = set(feature_names) - set(df.columns)
    if missing:
        raise ValueError(f"Missing features in dataset: {missing}")
    
    X = df[feature_names].copy()
    y = df["frie_score"].copy()
    
    return X, y


def apply_document_missingness(X: pd.DataFrame, missing_groups: set[str], random_pct: float = 0) -> pd.DataFrame:
    """Apply document-level missingness to features.
    
    For document groups, set all features in that group to NaN.
    For random missingness, set random percentage of all features to NaN.
    """
    X_missing = X.copy()
    feature_names = set(X.columns)
    
    # Document-level missingness
    for group in missing_groups:
        if group in DOCUMENT_GROUPS:
            for feat in DOCUMENT_GROUPS[group]:
                if feat in feature_names:
                    X_missing[feat] = np.nan
        elif group.startswith("random_"):
            pass  # handled below
    
    # Random feature-level missingness
    if random_pct > 0:
        n_features = len(feature_names)
        n_missing = int(n_features * random_pct)
        # For each row, randomly select features to mask
        for idx in X_missing.index:
            missing_features = np.random.choice(list(feature_names), size=n_missing, replace=False)
            X_missing.loc[idx, missing_features] = np.nan
    
    return X_missing


def train_full_model(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    """Train the full-data XGBoost model (baseline)."""
    # Use the same preprocessing as the saved model
    numeric_features = X_train.select_dtypes(include=[np.number]).columns.tolist()
    categorical_features = X_train.select_dtypes(exclude=[np.number]).columns.tolist()
    
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric_features),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), categorical_features),
        ],
        remainder="drop",
    )
    
    model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", XGBRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            objective="reg:squarederror",
            enable_categorical=False,
        )),
    ])
    
    model.fit(X_train, y_train)
    return model


def train_missing_aware_model(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    """Train XGBoost with native missing value handling."""
    numeric_features = X_train.select_dtypes(include=[np.number]).columns.tolist()
    categorical_features = X_train.select_dtypes(exclude=[np.number]).columns.tolist()
    
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    
    # For missing-aware, we don't impute - let XGBoost handle NaN
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
        ],
        remainder="drop",
    )
    
    model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", XGBRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            objective="reg:squarederror",
            missing=np.nan,  # XGBoost native missing handling
            enable_categorical=False,
        )),
    ])
    
    model.fit(X_train, y_train)
    return model


def _add_missing_indicators(X: pd.DataFrame) -> pd.DataFrame:
    """Add missing indicator columns for numeric features."""
    X_enhanced = X.copy()
    numeric_features = X.select_dtypes(include=[np.number]).columns.tolist()
    
    for feat in numeric_features:
        X_enhanced[f"{feat}_was_missing"] = X[feat].isna().astype(int)
    
    return X_enhanced


def train_missing_indicator_model(X_train: pd.DataFrame, y_train: pd.Series) -> tuple:
    """Train model with explicit missingness indicators."""
    X_train_enhanced = _add_missing_indicators(X_train)
    categorical_features = X_train_enhanced.select_dtypes(exclude=[np.number]).columns.tolist()
    numeric_features_enhanced = X_train_enhanced.select_dtypes(include=[np.number]).columns.tolist()
    
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric_features_enhanced),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), categorical_features),
        ],
        remainder="drop",
    )
    
    model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", XGBRegressor(
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            objective="reg:squarederror",
        )),
    ])
    
    model.fit(X_train_enhanced, y_train)
    return model, numeric_features_enhanced, categorical_features


def _prepare_test_for_missing_indicator(model, X_test: pd.DataFrame) -> pd.DataFrame:
    """Prepare test data with missing indicators matching training columns."""
    X_test_enhanced = _add_missing_indicators(X_test)
    
    # Get expected columns from the model's preprocessor
    expected_num = model.named_steps['preprocessor'].named_transformers_['num'].feature_names_in_
    expected_cat = model.named_steps['preprocessor'].named_transformers_['cat'].feature_names_in_
    expected_cols = list(expected_num) + list(expected_cat)
    
    # Add missing columns with 0
    for col in expected_cols:
        if col not in X_test_enhanced.columns:
            X_test_enhanced[col] = 0
    
    # Reorder columns
    X_test_enhanced = X_test_enhanced[expected_cols]
    
    return X_test_enhanced


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series, model_type: str) -> dict[str, float]:
    """Evaluate model and return metrics."""
    preds = model.predict(X_test)
    return {
        "mae": mean_absolute_error(y_test, preds),
        "rmse": np.sqrt(mean_squared_error(y_test, preds)),
        "r2": r2_score(y_test, preds),
    }


def run_experiment() -> list[ExperimentResult]:
    """Run the complete missing-feature experiment."""
    print("Loading data...")
    X, y = load_data()
    print(f"Dataset shape: {X.shape}")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
    
    # Train baseline full-data model
    print("\nTraining full-data model...")
    full_model = train_full_model(X_train, y_train)
    full_metrics = evaluate_model(full_model, X_test, y_test, "full")
    print(f"Full model: MAE={full_metrics['mae']:.4f}, RMSE={full_metrics['rmse']:.4f}, R²={full_metrics['r2']:.4f}")
    
    # Train missing-aware model
    print("\nTraining missing-aware model...")
    missing_aware_model = train_missing_aware_model(X_train, y_train)
    
    # Train missing-indicator model
    print("\nTraining missing-indicator model...")
    missing_indicator_model, num_feats, cat_feats = train_missing_indicator_model(X_train, y_train)
    
    results = []
    
    # Evaluate on full test data first
    for name, model in [
        ("full", full_model),
        ("missing_aware", missing_aware_model),
    ]:
        metrics = evaluate_model(model, X_test, y_test, name)
        results.append(ExperimentResult(
            scenario="FULL_DATA",
            features_available=98,
            model_type=name,
            mae=metrics["mae"],
            rmse=metrics["rmse"],
            r2=metrics["r2"],
        ))
        print(f"{name}: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, R²={metrics['r2']:.4f}")
    
    # Missing-indicator model needs special test prep
    X_test_enhanced = _prepare_test_for_missing_indicator(missing_indicator_model, X_test)
    metrics = evaluate_model(missing_indicator_model, X_test_enhanced, y_test, "missing_indicator")
    results.append(ExperimentResult(
        scenario="FULL_DATA",
        features_available=98,
        model_type="missing_indicator",
        mae=metrics["mae"],
        rmse=metrics["rmse"],
        r2=metrics["r2"],
    ))
    print(f"missing_indicator: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, R²={metrics['r2']:.4f}")
    
    # Test each scenario
    print("\nTesting missingness scenarios...")
    for scenario_name, missing_config in SCENARIOS.items():
        random_pct = 0
        missing_groups = set()
        
        if "random_10" in missing_config:
            random_pct = 0.10
        elif "random_20" in missing_config:
            random_pct = 0.20
        elif "random_30" in missing_config:
            random_pct = 0.30
        elif "random_40" in missing_config:
            random_pct = 0.40
        else:
            missing_groups = missing_config
        
        X_test_missing = apply_document_missingness(X_test, missing_groups, random_pct)
        n_available = int((~X_test_missing.isna()).sum().sum() / len(X_test_missing))
        
        # Full model (will fail or impute with median)
        try:
            full_metrics = evaluate_model(full_model, X_test_missing, y_test, "full")
        except Exception as e:
            full_metrics = {"mae": np.nan, "rmse": np.nan, "r2": np.nan}
        
        # Missing-aware model
        try:
            ma_metrics = evaluate_model(missing_aware_model, X_test_missing, y_test, "missing_aware")
        except Exception as e:
            ma_metrics = {"mae": np.nan, "rmse": np.nan, "r2": np.nan}
        
        # Missing-indicator model (prepare test data)
        X_test_enhanced = _prepare_test_for_missing_indicator(missing_indicator_model, X_test_missing)
        
        try:
            mi_metrics = evaluate_model(missing_indicator_model, X_test_enhanced, y_test, "missing_indicator")
        except Exception as e:
            mi_metrics = {"mae": np.nan, "rmse": np.nan, "r2": np.nan}
        
        print(f"\nScenario {scenario_name}: {n_available} features available")
        print(f"  Full:         MAE={full_metrics['mae']:.4f}, RMSE={full_metrics['rmse']:.4f}, R²={full_metrics['r2']:.4f}")
        print(f"  Missing-aware: MAE={ma_metrics['mae']:.4f}, RMSE={ma_metrics['rmse']:.4f}, R²={ma_metrics['r2']:.4f}")
        print(f"  Missing-ind:   MAE={mi_metrics['mae']:.4f}, RMSE={mi_metrics['rmse']:.4f}, R²={mi_metrics['r2']:.4f}")
        
        for model_type, metrics in [
            ("full", full_metrics),
            ("missing_aware", ma_metrics),
            ("missing_indicator", mi_metrics),
        ]:
            if not np.isnan(metrics["mae"]):
                results.append(ExperimentResult(
                    scenario=scenario_name,
                    features_available=n_available,
                    model_type=model_type,
                    mae=metrics["mae"],
                    rmse=metrics["rmse"],
                    r2=metrics["r2"],
                ))
    
    return results


def print_results_table(results: list[ExperimentResult]) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 100)
    print(f"{'Scenario':<12} {'Features':>10} {'Model Type':<20} {'MAE':>8} {'RMSE':>8} {'R²':>8}")
    print("-" * 100)
    
    for r in results:
        print(f"{r.scenario:<12} {r.features_available:>10} {r.model_type:<20} {r.mae:>8.4f} {r.rmse:>8.4f} {r.r2:>8.4f}")


def save_results(results: list[ExperimentResult], output_path: str) -> None:
    """Save results to JSON."""
    data = [
        {
            "scenario": r.scenario,
            "features_available": r.features_available,
            "model_type": r.model_type,
            "mae": r.mae,
            "rmse": r.rmse,
            "r2": r.r2,
        }
        for r in results
    ]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    np.random.seed(42)
    results = run_experiment()
    print_results_table(results)
    save_results(results, r"D:\frie\Frontend\Frie\backend\missing_feature_experiment_results.json")
    
    # Save models
    # (In production, save the missing_aware_model as frie_xgboost_missing_aware_model.joblib)
    print("\nExperiment complete.")
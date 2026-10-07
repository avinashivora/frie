"""Feature-contract and deterministic FRIE API-service tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.feature_contract import get_feature_contract
from app.schemas.prediction import PredictionResponse
from app.services.feature_service import FeatureInputError, FeatureService
from app.services.prediction_service import PredictionService
from tests.test_frie6d_scoring import FEATURES


def test_feature_contract_matches_the_configured_source_contract() -> None:
    contract = get_feature_contract()
    config = json.loads(get_settings().model_config_path.read_text(encoding="utf-8"))
    assert contract.feature_count == 98
    assert contract.numeric_features == tuple(config["numeric_features"])
    assert contract.categorical_features == tuple(config["categorical_features"])
    assert len(contract.numeric_features) == 86
    assert len(contract.categorical_features) == 12


def test_feature_service_rejects_missing_and_unexpected_features() -> None:
    contract = get_feature_contract()
    service = FeatureService(contract)
    with pytest.raises(FeatureInputError, match="Missing required features"):
        service.build_model_input({}, contract.feature_names)
    invalid = {name: 1 for name in contract.feature_names}
    invalid["unexpected_field"] = "not permitted"
    with pytest.raises(FeatureInputError, match="Unexpected features"):
        service.build_model_input(invalid, contract.feature_names)


def test_deterministic_service_matches_public_prediction_schema() -> None:
    result = PredictionService(get_settings()).predict(FEATURES)
    PredictionResponse.model_validate(result)
    assert result["algorithm_version"] == "FRIE-6D-v1.0"
    assert result["frie_score"]["maximum"] == 600.0
    assert set(result["dimensions"]) == {
        "credit_behaviour", "affordability", "cashflow_stability",
        "financial_resilience", "commitment_adherence", "spending_behaviour",
    }


def test_partial_service_does_not_impute_and_reports_coverage() -> None:
    result = PredictionService(get_settings()).predict_with_partial_data(
        {"monthly_income": 75000.0, "synthetic_total_expense": 25000.0},
        profile="neutral",
    )
    assert result["frie_score"]["maximum"] == 600.0
    assert result["data_coverage"] < 1.0
    assert result["available_features"] == 2
    assert result["dimensions"]["credit_behaviour"]["score"] is None
    assert result["dimensions"]["credit_behaviour"]["status"] == "NOT_ESTABLISHED"


def test_legacy_model_assets_are_not_needed_by_authoritative_service() -> None:
    service = PredictionService(get_settings())
    service.load_model()
    assert service.is_loaded
    assert service.load_error is None

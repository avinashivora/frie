"""The single authoritative FRIE feature contract, read from the model configuration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json

from app.core.config import get_settings


class FeatureContractError(ValueError):
    """Raised when the saved model configuration is not a valid API contract."""


@dataclass(frozen=True)
class FeatureContract:
    """Names and types required by the saved FRIE pipeline."""

    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self.numeric_features + self.categorical_features

    @property
    def feature_count(self) -> int:
        return len(self.feature_names)


@lru_cache(maxsize=1)
def get_feature_contract() -> FeatureContract:
    """Read the exact feature contract from the supplied JSON configuration once."""

    config_path = get_settings().model_config_path
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        numeric_features = tuple(config["numeric_features"])
        categorical_features = tuple(config["categorical_features"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise FeatureContractError("Unable to read the FRIE model feature configuration.") from exc

    contract = FeatureContract(numeric_features, categorical_features)
    if config.get("target") != "frie_score":
        raise FeatureContractError("FRIE model configuration has an unexpected target name.")
    if config.get("total_input_features") != contract.feature_count:
        raise FeatureContractError("FRIE model configuration has an inconsistent feature count.")
    if contract.feature_count != 98 or len(set(contract.feature_names)) != contract.feature_count:
        raise FeatureContractError("FRIE model configuration must define 98 unique input features.")
    if set(contract.numeric_features) & set(contract.categorical_features):
        raise FeatureContractError("FRIE numeric and categorical feature groups must not overlap.")
    return contract

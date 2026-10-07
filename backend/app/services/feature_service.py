"""Convert validated customer feature data into the saved pipeline's exact dataframe."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from app.core.feature_contract import FeatureContract


class FeatureInputError(ValueError):
    """Raised when source-normalized customer data cannot form a model input row."""


class FeatureService:
    """Boundary between customer data and the saved model's named input dataframe.

    This service deliberately does not invent or infer financial facts. Future document and
    data-source integrations must derive values with documented, source-backed rules before
    handing the complete normalized mapping to this service.
    """

    def __init__(self, contract: FeatureContract) -> None:
        self._contract = contract

    def build_model_input(
        self,
        customer_features: Mapping[str, Any],
        pipeline_feature_order: Sequence[str],
        *,
        allow_missing: bool = False,
    ) -> pd.DataFrame:
        """Validate a full normalized feature mapping and return one ordered dataframe row."""

        expected = set(self._contract.feature_names)
        received = set(customer_features)
        missing = sorted(expected - received)
        unexpected = sorted(received - expected)
        if missing or unexpected:
            message_parts: list[str] = []
            if missing:
                message_parts.append(f"Missing required features: {', '.join(missing)}.")
            if unexpected:
                message_parts.append(f"Unexpected features: {', '.join(unexpected)}.")
            raise FeatureInputError(" ".join(message_parts))

        if tuple(sorted(pipeline_feature_order)) != tuple(sorted(self._contract.feature_names)):
            raise FeatureInputError("Saved pipeline feature names do not match the FRIE contract.")

        self._validate_value_types(customer_features, allow_missing=allow_missing)
        ordered_values = {
            name: (np.nan if customer_features[name] is None else customer_features[name])
            for name in pipeline_feature_order
        }
        return pd.DataFrame([ordered_values], columns=list(pipeline_feature_order))

    def _validate_value_types(self, customer_features: Mapping[str, Any], *, allow_missing: bool = False) -> None:
        for name in self._contract.numeric_features:
            value = customer_features[name]
            if allow_missing and value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
                raise FeatureInputError(f"Numeric feature '{name}' must be a finite JSON number.")
        for name in self._contract.categorical_features:
            value = customer_features[name]
            if allow_missing and value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise FeatureInputError(f"Categorical feature '{name}' must be a non-empty string.")

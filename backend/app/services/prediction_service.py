"""Application service for the deterministic FRIE six-dimension scoring engine.

The authoritative FRIE score is calculated by the deterministic scoring
modules under app.services.scoring.

The legacy XGBoost pipeline is intentionally retained only for compatibility
and future/experimental ML use. It is NOT used to calculate the authoritative
FRIE score.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.core.feature_contract import FeatureContract, get_feature_contract
from app.services.feature_service import FeatureService
from app.services.scoring.frie_score import calculate_frie_score
from app.services.scoring.profiles import calculate_profile

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when a legacy ML model operation is requested but unavailable."""


class InsufficientDataError(RuntimeError):
    """Raised when no usable financial information is available."""

    def __init__(
        self,
        available: int,
        required: int,
        missing_groups: list[str] | None = None,
    ) -> None:
        self.available = available
        self.required = required
        self.missing_groups = missing_groups or []

        super().__init__(
            f"Insufficient data: {available}/{required} features available. "
            f"Missing groups: {self.missing_groups}"
        )


class PredictionService:
    """Application-facing service for FRIE scoring."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._contract: FeatureContract = get_feature_contract()
        self._feature_service = FeatureService(self._contract)

    @property
    def is_loaded(self) -> bool:
        """The deterministic scoring engine is always available once imported."""
        return True

    @property
    def load_error(self) -> str | None:
        """The deterministic scoring engine has no external model-load error."""
        return None

    def load_model(self) -> None:
        """Compatibility method for the existing application startup flow.

        The authoritative FRIE scoring engine is deterministic and therefore
        does not require a serialized model artifact.
        """
        logger.info(
            "FRIE deterministic scoring engine ready: six-dimension methodology."
        )

    def assess(
        self,
        features: dict[str, Any],
        *,
        profile: str = "neutral",
    ) -> dict[str, Any]:
        """Calculate the authoritative FRIE score.

        Parameters
        ----------
        features:
            Source-normalized FRIE customer features.

        profile:
            Scoring profile. Supported values are:
            - neutral
            - loan
            - insurance

        Returns
        -------
        dict
            Structured six-dimension FRIE result containing:
            - algorithm version
            - FRIE base score /600
            - six dimension results
            - selected purpose-specific profile score
        """

        if not isinstance(features, dict):
            raise TypeError("features must be a dictionary.")

        if profile not in {"neutral", "loan", "insurance"}:
            raise ValueError("profile must be one of: neutral, loan, insurance.")

        if not features:
            raise InsufficientDataError(
                available=0,
                required=1,
                missing_groups=[],
            )

        # The deterministic FRIE engine calculates all six dimensions once.
        frie_result = calculate_frie_score(features)

        # Calculate the selected purpose-specific profile from the same
        # dimension results. This does not recalculate the dimensions.
        profile_result = calculate_profile(
            features,
            profile=profile,
        )

        return {
            "algorithm_version": frie_result["algorithm_version"],
            "frie_score": frie_result["frie_score"],
            "dimensions": frie_result["dimensions"],
            "profile": profile_result,
        }

    def predict(
        self,
        features: dict[str, Any],
        *,
        profile: str = "neutral",
    ) -> dict[str, Any]:
        """Backward-compatible alias for assess()."""

        return self.assess(
            features,
            profile=profile,
        )

    def predict_with_partial_data(
        self,
        features: dict[str, Any],
        *,
        profile: str = "neutral",
    ) -> dict[str, Any]:
        """Score available data without ML imputation.

        Missing information is handled by the six deterministic scoring
        modules through their coverage/status/confidence logic.
        """

        if not isinstance(features, dict):
            raise TypeError("features must be a dictionary.")

        available_features = {
            name
            for name, value in features.items()
            if name in self._contract.feature_names and value is not None
        }

        if not available_features:
            raise InsufficientDataError(
                available=0,
                required=1,
                missing_groups=self._identify_missing_groups(
                    set(self._contract.feature_names)
                ),
            )

        result = self.assess(
            features,
            profile=profile,
        )

        coverage = len(available_features) / self._contract.feature_count

        result["data_coverage"] = round(coverage, 3)
        result["available_features"] = len(available_features)
        result["total_features"] = self._contract.feature_count
        result["missing_groups"] = self._identify_missing_groups(
            set(self._contract.feature_names) - available_features
        )

        return result

    def explain(
        self,
        features: dict[str, Any],
        *,
        profile: str = "neutral",
    ) -> dict[str, Any]:
        """Return deterministic FRIE score explanation.

        This replaces TreeSHAP as the explanation for the authoritative
        six-dimension FRIE score.

        The explanation is derived directly from the scoring methodology:
        dimension scores, indicators, and effective weights.
        """

        result = self.assess(
            features,
            profile=profile,
        )

        dimensions = result["dimensions"]

        dimension_contributions = []

        for name, dimension in dimensions.items():
            score = dimension.get("score")

            if score is None:
                continue

            dimension_contributions.append(
                {
                    "dimension": name,
                    "score": score,
                    "coverage": dimension.get("coverage"),
                    "status": dimension.get("status"),
                    "confidence": dimension.get("confidence"),
                    "indicators": dimension.get("indicators", {}),
                    "effective_weights": dimension.get(
                        "effective_weights",
                        {},
                    ),
                }
            )

        dimension_contributions.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return {
            "method": "Deterministic FRIE scoring methodology",
            "scope": "LOCAL",
            "algorithm_version": result["algorithm_version"],
            "frie_score": result["frie_score"],
            "profile": result["profile"],
            "dimensions": dimension_contributions,
        }

    def _identify_missing_groups(
        self,
        missing_features: set[str],
    ) -> list[str]:
        """Identify document/data groups affected by missing features."""

        groups = {
            "bank_statement": [
                "food_expense",
                "rent_expense",
                "education_expense",
                "healthcare_expense",
                "transport_expense",
                "utility_expense",
                "discretionary_expense",
                "monthly_savings",
                "savings_balance",
                "upi_spending",
                "upi_transaction_count",
                "cash_flow_mean",
                "cash_flow_std",
                "cash_flow_min",
                "cash_flow_negative_months",
            ],
            "credit_report": [
                "bureau_account_count",
                "active_credit_count",
                "closed_credit_count",
                "bureau_credit_amount",
                "bureau_debt_amount",
                "bureau_credit_limit",
                "bureau_overdue_amount",
                "bureau_overdue_days",
                "bureau_overdue_account_count",
                "credit_prolongation_count",
                "total_installments",
                "total_amount_due",
                "total_amount_paid",
                "total_late_payments",
                "total_on_time_payments",
                "average_payment_delay",
                "total_payment_delay_days",
                "payment_difference",
                "on_time_payment_ratio",
                "payment_coverage_ratio",
                "previous_application_count",
                "previous_approved_count",
                "previous_refused_count",
                "previous_credit_amount",
                "previous_avg_credit",
                "previous_avg_annuity",
                "previous_avg_down_payment",
                "avg_credit_card_balance",
                "max_credit_card_balance",
                "avg_credit_limit",
                "total_card_drawings",
                "total_card_payments",
                "avg_minimum_payment",
                "avg_credit_utilisation",
                "max_card_dpd",
                "max_card_dpd_default",
                "pos_account_records",
                "avg_pos_installments",
                "avg_future_installments",
                "pos_dpd_count",
                "max_pos_dpd",
                "max_pos_dpd_default",
                "current_dti",
                "bureau_dti",
                "previous_approval_ratio",
                "bureau_overdue_ratio",
            ],
            "insurance": [
                "health_insurance",
                "life_insurance",
                "insurance_premium",
                "insurance_payment_consistency",
            ],
            "investment": [
                "fd_amount",
                "rd_contribution",
                "sip_contribution",
                "mutual_fund_balance",
                "ppf_contribution",
                "nps_contribution",
            ],
            "loan": [
                "current_credit_amount",
                "current_loan_annuity",
                "goods_price",
            ],
        }

        missing_groups: list[str] = []

        for group, group_features in groups.items():
            if any(feature in missing_features for feature in group_features):
                missing_groups.append(group)

        return missing_groups

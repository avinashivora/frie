"""FRIE saved-pipeline prediction endpoint."""

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.prediction import (
    PartialPredictionRequest,
    PartialPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.services.feature_service import FeatureInputError
from app.services.prediction_service import InsufficientDataError, ModelUnavailableError

router = APIRouter(tags=["prediction"])


def reliability_level(
    score: float,
    *,
    maximum: float = 600.0,
) -> str:
    """Temporary display category for the six-dimension FRIE score."""

    if maximum <= 0:
        raise ValueError("maximum must be greater than zero.")

    normalized = (score / maximum) * 100.0

    if normalized < 40:
        return "Poor"
    if normalized < 55:
        return "Average"
    if normalized < 70:
        return "Good"

    return "Excellent"


@router.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Generate a deterministic FRIE six-dimension assessment",
    description=(
        "Requires the configured FRIE feature set. The authoritative FRIE "
        "score is calculated by the deterministic six-dimension methodology."
    ),
)
def predict(
    payload: PredictionRequest,
    request: Request,
) -> PredictionResponse:
    service = request.app.state.prediction_service

    try:
        result = service.predict(
            payload.features.model_dump(),
            profile="neutral",
        )
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRIE scoring service is temporarily unavailable.",
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PredictionResponse(
        algorithm_version=result["algorithm_version"],
        frie_score=result["frie_score"],
        dimensions=result["dimensions"],
        profile=result["profile"],
        profiles=result["profiles"],
    )


@router.post(
    "/predict/partial",
    response_model=PartialPredictionResponse,
    summary="Generate a deterministic FRIE assessment with partial data",
    description=(
        "Available information is scored directly by the six FRIE "
        "dimensions. Missing information is represented through "
        "dimension coverage and status rather than model imputation."
    ),
)
def predict_partial(
    payload: PartialPredictionRequest,
    request: Request,
) -> PartialPredictionResponse:
    service = request.app.state.prediction_service

    try:
        result = service.predict_with_partial_data(
            payload.features.model_dump(exclude_none=True),
            profile="neutral",
        )
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRIE scoring service is temporarily unavailable.",
        ) from exc
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "Insufficient financial information for a FRIE assessment."
                ),
                "available_features": exc.available,
                "required_features": exc.required,
                "missing_groups": exc.missing_groups,
            },
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return PartialPredictionResponse(
        algorithm_version=result["algorithm_version"],
        frie_score=result["frie_score"],
        dimensions=result["dimensions"],
        profile=result["profile"],
        profiles=result["profiles"],
        data_coverage=result["data_coverage"],
        available_features=result["available_features"],
        total_features=result["total_features"],
        missing_groups=result["missing_groups"],
    )

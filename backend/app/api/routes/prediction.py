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


def reliability_level(score: float, maximum: float = 600.0) -> str:
    """Temporary display category for the six-dimension FRIE score."""

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
    summary="Generate a prototype FRIE score using the saved XGBoost pipeline",
    description=(
        "Requires every configured FRIE feature. This is a prototype/research score and is "
        "not a regulatory, universal, or externally validated financial-reliability assessment."
    ),
)
def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
    service = request.app.state.prediction_service
    try:
        score = service.predict(payload.features.model_dump())
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRIE prediction service is temporarily unavailable.",
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return PredictionResponse(
        frie_score=round(score, 2), reliability_level=reliability_level(score)
    )


@router.post(
    "/predict/partial",
    response_model=PartialPredictionResponse,
    summary="Generate a prototype FRIE score with partial feature data",
    description=(
        "Internal research capability for incomplete feature data. Uses the existing V2 "
        "pipeline and its fitted preprocessing. Authenticated assessments additionally enforce source eligibility."
    ),
)
def predict_partial(
    payload: PartialPredictionRequest, request: Request
) -> PartialPredictionResponse:
    service = request.app.state.prediction_service
    try:
        score, metadata = service.predict_with_partial_data(
            payload.features.model_dump(exclude_none=True)
        )
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRIE prediction service is temporarily unavailable.",
        ) from exc
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Insufficient financial information for a reliable FRIE analysis.",
                "available_features": exc.available,
                "required_features": exc.required,
                "missing_groups": exc.missing_groups,
            },
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return PartialPredictionResponse(
        frie_score=round(score, 2),
        reliability_level=reliability_level(score),
        data_coverage=metadata["data_coverage"],
        available_features=metadata["available_features"],
        total_features=metadata["total_features"],
        missing_groups=metadata["missing_groups"],
        model_used=metadata["model_used"],
        warning=metadata.get("warning"),
    )

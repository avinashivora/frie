"""Health endpoint for API and model-readiness checks."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check deterministic FRIE scoring readiness")
def health(request: Request) -> JSONResponse:
    service = request.app.state.prediction_service
    if service.is_loaded:
        return JSONResponse(
            {
                "status": "ok",
                "scoring_engine": "deterministic-six-dimension",
                "algorithm_version": "FRIE-6D-v1.0",
            }
        )
    return JSONResponse(
        {"status": "degraded", "scoring_engine": "unavailable"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

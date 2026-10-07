"""Health endpoint for API and model-readiness checks."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check API and saved-model readiness")
def health(request: Request) -> JSONResponse:
    service = request.app.state.prediction_service
    if service.is_loaded:
        return JSONResponse({"status": "ok", "model_loaded": True, "model": "FRIE XGBoost"})
    return JSONResponse(
        {"status": "degraded", "model_loaded": False, "model": "FRIE XGBoost"},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

"""FastAPI entry point for the backend-only FRIE prototype service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from math import isfinite
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status

from app.api.routes.analysis import router as analysis_router
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.features import router as features_router
from app.api.routes.health import router as health_router
from app.api.routes.prediction import router as prediction_router
from app.api.routes.profile import router as profile_router
from app.core.config import get_settings
from app.db.seed import ensure_demo_user
from app.db.session import SessionLocal, init_db
from app.services.prediction_service import PredictionService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    service = PredictionService(get_settings())
    service.load_model()
    app.state.prediction_service = service
    if get_settings().seed_demo_user:
        db = SessionLocal()
        try:
            settings = get_settings()
            ensure_demo_user(
                db, email=settings.demo_email, password=settings.demo_password
            )
            db.commit()
        finally:
            db.close()
    yield


settings = get_settings()
app = FastAPI(
    title="FRIE Prototype API",
    version="0.1.0",
    description=(
        "Backend for the deterministic FRIE six-dimension financial intelligence "
        "prototype. Legacy ML artifacts are not used for authoritative scoring."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(health_router)
app.include_router(prediction_router)
app.include_router(analysis_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(documents_router)
app.include_router(features_router)


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats so validation errors always serialize as JSON."""

    if isinstance(value, float) and not isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 for invalid payloads, including NaN/Infinity inputs."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _json_safe(jsonable_encoder(exc.errors()))},
    )

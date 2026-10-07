"""Shared FastAPI dependencies. Keeps authentication logic out of every route."""

from __future__ import annotations

from fastapi import Depends, Request, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import auth_service

_UNAUTHORIZED = {
    "status_code": status.HTTP_401_UNAUTHORIZED,
    "detail": "Invalid or expired credentials.",
    "headers": {"WWW-Authenticate": "Bearer"},
}


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the bearer token to its user for protected routes."""

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(**_UNAUTHORIZED)
    user = auth_service.authenticate_token(db, token=token.strip())
    if user is None:
        raise HTTPException(**_UNAUTHORIZED)
    return user

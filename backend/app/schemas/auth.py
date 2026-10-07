"""Authentication request/response schemas. Hashes and passwords never leave the service layer."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _validate_email(value: str) -> str:
    address = value.strip().lower()
    if len(address) > 254 or not _EMAIL_PATTERN.match(address):
        raise ValueError("must be a valid email address")
    return address


class RegisterRequest(BaseModel):
    """New account credentials."""

    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _validate_email(value)


class LoginRequest(BaseModel):
    """Existing account credentials."""

    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _validate_email(value)


class UserRead(BaseModel):
    """Safe public user record. Never includes password material."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """One-time bearer token with the authenticated user."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead

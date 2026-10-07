"""Registration, password hashing, and opaque session-token handling.

Passwords use PBKDF2-HMAC-SHA256 from the standard library (per-user salt,
600,000 iterations, constant-time comparison). Only salted hashes reach the
database. Login sessions use random opaque tokens; only their SHA-256 hash
is stored, so a database read never yields a usable token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import Session as UserSession
from app.db.models import User

_HASH_ALGORITHM = "pbkdf2_sha256"
_HASH_ITERATIONS = 600_000
_SALT_BYTES = 16


class EmailAlreadyExistsError(ValueError):
    """Raised when registering an email that is already taken."""


class InvalidCredentialsError(ValueError):
    """Raised when login credentials do not match. Message stays generic."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """Hash a password for storage. The plaintext never leaves this call."""

    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS)
    return f"{_HASH_ALGORITHM}${_HASH_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time password check against a stored hash."""

    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored_hash.split("$")
        if algorithm != _HASH_ALGORITHM:
            return False
        iterations = int(iterations_raw)
        expected = base64.b64decode(digest_raw.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_raw.encode("ascii")), iterations
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def normalize_email(email: str) -> str:
    """Trim and lowercase an email address for storage and lookup."""

    return email.strip().lower()


def create_user(db: Session, *, email: str, password: str) -> User:
    """Register a user with a hashed password. Raises on duplicate email."""

    address = normalize_email(email)
    if db.query(User).filter(User.email == address).first() is not None:
        raise EmailAlreadyExistsError("An account with this email already exists.")
    user = User(email=address, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    """Validate credentials. Same error for unknown email and wrong password."""

    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password.")
    return user


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session_token(db: Session, *, user: User, lifetime_days: int) -> tuple[str, UserSession]:
    """Create a login session and return the one-time raw token with its row."""

    token = secrets.token_urlsafe(32)
    session = UserSession(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=lifetime_days),
    )
    db.add(session)
    db.flush()
    return token, session


def authenticate_token(db: Session, *, token: str) -> User | None:
    """Resolve a bearer token to its user, or None when unknown/expired."""

    if not token:
        return None
    row = db.query(UserSession).filter(UserSession.token_hash == _hash_token(token)).first()
    if row is None:
        return None
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None
    return db.get(User, row.user_id)

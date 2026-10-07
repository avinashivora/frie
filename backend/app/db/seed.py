"""Demo seed: idempotent creation of the documented prototype demo user."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import User
from app.services import auth_service

logger = logging.getLogger(__name__)


def ensure_demo_user(db: Session, email: str, password: str) -> tuple[User, bool]:
    """Create the demo user only when absent. The password is hashed immediately."""

    existing = db.query(User).filter(User.email == email).first()
    if existing is not None:
        return existing, False
    user = auth_service.create_user(db, email=email, password=password)
    logger.info("Demo user ready: %s", email)
    return user, True

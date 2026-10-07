"""Availability declarations: confirmed NONE vs UNKNOWN vs never-answered."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import FinancialStatus, User

STATUS_FIELDS = (
    "has_loan",
    "insurance_status",
    "inv_fd",
    "inv_rd",
    "inv_sip",
    "inv_mutual_fund",
    "inv_ppf",
    "inv_nps",
)


def get_status(db: Session, *, user: User) -> FinancialStatus | None:
    """Return the authenticated user's declaration row, if any."""

    return db.query(FinancialStatus).filter(FinancialStatus.user_id == user.id).first()


def upsert_status(db: Session, *, user: User, values: dict[str, Any]) -> FinancialStatus:
    """Create or update the authenticated user's declaration row."""

    row = get_status(db, user=user)
    if row is None:
        row = FinancialStatus(user_id=user.id)
        db.add(row)
    for name in STATUS_FIELDS:
        if name in values:
            setattr(row, name, values[name])
    db.flush()
    return row

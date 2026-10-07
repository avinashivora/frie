"""Authenticated customer-profile endpoints. Raw inputs only; no feature computation."""

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.financial_status import FinancialStatusRead, FinancialStatusUpdate
from app.schemas.profile import CompletenessRead, ProfileEnvelope, ProfileRead, ProfileUpdate, ReadinessRead
from app.services import availability_service, profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


def _envelope(user: User, db: Session) -> ProfileEnvelope:
    profile = profile_service.get_profile(db, user=user)
    return ProfileEnvelope(
        profile=ProfileRead.model_validate(profile) if profile is not None else None,
        completeness=CompletenessRead(**profile_service.compute_completeness(profile)),
        readiness=ReadinessRead(**profile_service.profile_readiness(profile)),
    )


@router.get("", response_model=ProfileEnvelope)
def read_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileEnvelope:
    return _envelope(user, db)


@router.put("", response_model=ProfileEnvelope)
def write_profile(
    payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProfileEnvelope:
    profile_service.upsert_profile(db, user=user, values=payload.model_dump(exclude_unset=True))
    return _envelope(user, db)


@router.get("/financial-status", response_model=FinancialStatusRead)
def read_financial_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FinancialStatusRead:
    row = availability_service.get_status(db, user=user)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial status not found.")
    return FinancialStatusRead.model_validate(row)


@router.put("/financial-status", response_model=FinancialStatusRead)
def write_financial_status(
    payload: FinancialStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FinancialStatusRead:
    row = availability_service.upsert_status(db, user=user, values=payload.model_dump(exclude_unset=True))
    return FinancialStatusRead.model_validate(row)

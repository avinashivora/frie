"""Feature build, inspection, and readiness endpoints. No prediction happens here."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.feature_contract import get_feature_contract
from app.db.models import FinancialFeature, User
from app.db.session import get_db
from app.schemas.features import BuildSummary, CompletenessRead, FeatureRead, ReadinessRead
from app.services import feature_engineering

router = APIRouter(prefix="/features", tags=["features"])


@router.post("/build", response_model=BuildSummary)
def build_own_features(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BuildSummary:
    return BuildSummary(**feature_engineering.build_features(db, user))


@router.get("", response_model=list[FeatureRead])
def list_own_features(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[FeatureRead]:
    rows = (
        db.query(FinancialFeature)
        .filter(FinancialFeature.user_id == user.id)
        .order_by(FinancialFeature.feature_name)
        .all()
    )
    return [FeatureRead.model_validate(row) for row in rows]


@router.get("/readiness", response_model=ReadinessRead)
def read_own_readiness(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReadinessRead:
    assembly = feature_engineering.assemble(db, user)
    report = feature_engineering.readiness_report(assembly, get_feature_contract())
    return ReadinessRead(**report)


@router.get("/completeness", response_model=CompletenessRead)
def read_own_completeness(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CompletenessRead:
    report = feature_engineering.get_user_completeness(db, user)
    return CompletenessRead(**report)
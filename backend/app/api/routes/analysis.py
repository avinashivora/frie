"""Authenticated assessment history and local model explanations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.feature_contract import get_feature_contract
from app.db.models import (
    CustomerProfile,
    Document,
    Explanation,
    Extraction,
    FinancialStatus,
    Prediction,
    User,
)
from app.db.session import get_db
from app.services import feature_engineering, profile_service
from app.services.assessment_persisitence import (
    deserialize_assessment,
    persist_assessment,
)
from app.services.feature_service import FeatureInputError
from app.services.indicator_service import calculate_indicator_details
from app.services.prediction_service import InsufficientDataError, ModelUnavailableError
from app.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/analysis", tags=["analysis"])
INDICATOR_EXPLANATION_TYPE = "FRIE_INDICATOR"
RECOMMENDATION_EXPLANATION_TYPE = "FRIE_RECOMMENDATION"
ASSESSMENT_METADATA_TYPE = "ASSESSMENT_METADATA"


def _source_readiness(
    db: Session, user: User, assembly, readiness: dict[str, Any]
) -> dict[str, Any]:
    profile = profile_service.get_profile(db, user=user)
    profile_complete = profile_service.profile_readiness(profile)["profile_ready"]
    income_complete = bool(
        profile
        and profile.monthly_income is not None
        and profile.monthly_income > 0
        and profile.employment_start is not None
        and profile.income_type
        and profile.occupation
        and profile.organization_type
        and profile.contract_type
    )
    declarations = (
        db.query(FinancialStatus).filter(FinancialStatus.user_id == user.id).first()
    )
    declared_loan = declarations.has_loan if declarations else None
    insurance = declarations.insurance_status if declarations else None
    investments = [
        getattr(declarations, key) if declarations else None
        for key in (
            "inv_fd",
            "inv_rd",
            "inv_sip",
            "inv_mutual_fund",
            "inv_ppf",
            "inv_nps",
        )
    ]
    reviewed = feature_engineering._reviewed_extractions(db, user)
    # A reviewed but empty/failed extraction is not meaningful financial data.
    supported_document_ids = set(assembly.sources.values())
    document_types = {
        kind
        for kind, (document, _) in reviewed.items()
        if document.id in supported_document_ids
    }
    missing_source_blocks = {item["block"] for item in assembly.missing}
    bank_complete = (
        bool(document_types & {"bank_statement", "bank_import"})
        and "bank_statement" not in missing_source_blocks
    )
    credit_complete = (
        "credit_report" in document_types
        and "credit_report" not in missing_source_blocks
    )
    loan_complete = (
        "loan_document" in document_types
        and "loan_document" not in missing_source_blocks
    ) or declared_loan == "no"
    insurance_complete = (
        "insurance_document" in document_types
        and "insurance_document" not in missing_source_blocks
    ) or insurance == "none"
    investments_complete = all(
        name in assembly.values
        for name in (
            "fd_amount",
            "rd_contribution",
            "sip_contribution",
            "mutual_fund_balance",
            "ppf_contribution",
            "nps_contribution",
        )
    )
    financial_source = bool(
        document_types
        & {
            "bank_statement",
            "bank_import",
            "credit_report",
            "loan_document",
            "insurance_document",
            "investment_statement",
        }
        or declared_loan == "no"
        or insurance == "none"
        or all(value == "no" for value in investments)
    )
    complete_model = readiness["status"] == "READY"
    can_assess = complete_model or (
        profile_complete and income_complete and financial_source
    )
    state = (
        "complete" if complete_model else "estimated" if can_assess else "insufficient"
    )
    no_financial_source = not financial_source
    sources = [
        {
            "key": "profile",
            "title": "Profile",
            "status": "complete" if profile_complete else "required",
            "description": "Complete your basic, household, housing, and employment details.",
        },
        {
            "key": "income",
            "title": "Income & Employment",
            "status": "complete" if income_complete else "required",
            "description": "Add your income and employment details.",
        },
        {
            "key": "bank",
            "title": "Bank Statement",
            "status": "complete"
            if bank_complete
            else "required"
            if no_financial_source
            else "recommended",
            "description": "Upload a recent bank statement or supported CSV/Excel transaction file so FRIE can analyse income, expenses, savings and cash-flow behaviour.",
        },
        {
            "key": "credit",
            "title": "Credit Report",
            "status": "complete" if credit_complete else "recommended",
            "description": "Add your credit report to improve credit-history and repayment assessment.",
        },
        {
            "key": "insurance",
            "title": "Insurance Details",
            "status": "complete"
            if insurance_complete
            else "required"
            if insurance in {"health", "life", "both"}
            else "unknown",
            "description": "Add your insurance information to include protection and commitment behaviour, or confirm that you have none.",
        },
        {
            "key": "investments",
            "title": "Investment Details",
            "status": "complete"
            if investments_complete
            else "required"
            if "yes" in investments
            else "unknown",
            "description": "Add your investment information to improve financial resilience assessment, or confirm which products you do not hold.",
        },
        {
            "key": "loans",
            "title": "Loan Details",
            "status": "complete"
            if loan_complete
            else "required"
            if declared_loan == "yes"
            else "unknown",
            "description": "Add loan information to improve debt-burden assessment, or confirm that you have no loan.",
        },
    ]
    if complete_model:
        for source in sources:
            source["status"] = "complete"
    if state == "insufficient":
        message = "Complete your profile and income details, then add financial information from at least one source to begin your FRIE assessment."
    elif state == "estimated":
        message = "Your FRIE assessment is available based on the financial information currently provided."
    else:
        message = "Your financial information is complete. You’re ready to generate your FRIE Score."
    return {
        "assessment_state": state,
        "can_assess": can_assess,
        "sources": sources,
        "message": message,
    }


def _stored_assessment_details(db: Session, prediction_id: int) -> dict[str, Any]:
    rows = (
        db.query(Explanation)
        .filter(
            Explanation.prediction_id == prediction_id,
            Explanation.explanation_type.in_(
                (
                    INDICATOR_EXPLANATION_TYPE,
                    RECOMMENDATION_EXPLANATION_TYPE,
                    ASSESSMENT_METADATA_TYPE,
                )
            ),
        )
        .order_by(Explanation.id)
        .all()
    )
    details: dict[str, dict[str, Any]] = {}
    recommendations: list[dict[str, Any]] = []
    assessment_state = "complete"
    for item in rows:
        try:
            value = json.loads(item.feature_value or "null")
        except (TypeError, json.JSONDecodeError):
            continue
        if item.explanation_type == INDICATOR_EXPLANATION_TYPE and isinstance(
            value, dict
        ):
            details[item.feature_name] = value
        elif item.explanation_type == RECOMMENDATION_EXPLANATION_TYPE and isinstance(
            value, dict
        ):
            recommendations.append(value)
        elif (
            item.explanation_type == ASSESSMENT_METADATA_TYPE
            and item.feature_name == "assessment_state"
        ):
            assessment_state = (
                str(value) if value in {"complete", "estimated"} else "complete"
            )
    return {
        "indicators": {key: value.get("score") for key, value in details.items()},
        "indicator_details": details,
        "recommendations": recommendations,
        "assessment_state": assessment_state,
    }


def _source_fingerprint(db: Session, user: User) -> str:
    profile = (
        db.query(CustomerProfile).filter(CustomerProfile.user_id == user.id).first()
    )
    declarations = (
        db.query(FinancialStatus).filter(FinancialStatus.user_id == user.id).first()
    )
    docs = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.id)
        .all()
    )
    sources = []
    for document in docs:
        extraction = (
            db.query(Extraction).filter(Extraction.document_id == document.id).first()
        )
        sources.append(
            {
                "id": document.id,
                "type": document.document_type,
                "updated_at": document.updated_at.isoformat()
                if document.updated_at
                else None,
                "review": document.review_status,
                "extraction": extraction.structured_data if extraction else None,
                "extraction_updated_at": extraction.updated_at.isoformat()
                if extraction and extraction.updated_at
                else None,
            }
        )
    payload = {
        "profile": {
            column.name: str(getattr(profile, column.name))
            for column in profile.__table__.columns
            if column.name not in ("id", "user_id", "created_at", "updated_at")
        }
        if profile
        else None,
        "declarations": {
            column.name: getattr(declarations, column.name)
            for column in declarations.__table__.columns
            if column.name not in ("id", "user_id", "created_at", "updated_at")
        }
        if declarations
        else None,
        "documents": sources,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ready_assembly(db: Session, user: User):
    assembly = feature_engineering.assemble(db, user)
    readiness = feature_engineering.readiness_report(assembly, get_feature_contract())
    if readiness["status"] != "READY":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A full assessment requires all model features.",
                "status": readiness["status"],
                "available": readiness["available"],
                "required": readiness["total_required"],
                "missing": readiness["missing"],
            },
        )
    return assembly, readiness


@router.get("/status")
def assessment_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """User-facing readiness without model feature names or technical counts."""
    assembly = feature_engineering.assemble(db, user)
    readiness = feature_engineering.readiness_report(assembly, get_feature_contract())
    return _source_readiness(db, user, assembly, readiness)


def _predict(
    request: Request,
    features: dict[str, Any],
    *,
    profile: str = "neutral",
) -> tuple[dict[str, Any], str]:
    from app.api.routes.prediction import reliability_level

    service = request.app.state.prediction_service

    try:
        result = service.predict(
            features,
            profile=profile,
        )
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="FRIE scoring service is temporarily unavailable.",
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    score = float(
        result["frie_score"].get(
            "value",
            result["frie_score"].get("score"),
        )
    )

    return result, reliability_level(score)


def _shap(request: Request, features: dict[str, Any]) -> dict[str, Any]:
    try:
        return request.app.state.prediction_service.explain(features)
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="FRIE explanation service is temporarily unavailable.",
        ) from exc
    except (FeatureInputError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assess")
def create_assessment(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a complete or available-data FRIE assessment from source-backed inputs."""
    assembly = feature_engineering.assemble(db, user)
    readiness = feature_engineering.readiness_report(assembly, get_feature_contract())
    source_status = _source_readiness(db, user, assembly, readiness)
    if not source_status["can_assess"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": source_status["message"],
                "assessment_state": "insufficient",
                "sources": source_status["sources"],
            },
        )
    features = assembly.values
    complete = source_status["assessment_state"] == "complete"
    service = request.app.state.prediction_service
    try:
        if complete:
            score, level = _predict(request, features)
            model_features = features
            explanation = _shap(request, model_features)
        else:
            model_features = {
                name: features.get(name)
                for name in get_feature_contract().feature_names
            }
            score, _metadata = service.predict_with_partial_data(features)
            from app.api.routes.prediction import reliability_level

            level = reliability_level(score)
            explanation = service.explain(model_features, allow_missing=True)
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="FRIE prediction service is temporarily unavailable.",
        ) from exc
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": source_status["message"],
                "assessment_state": "insufficient",
                "sources": source_status["sources"],
            },
        ) from exc
    except FeatureInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    indicator_details = calculate_indicator_details(features)
    indicators = {key: detail["score"] for key, detail in indicator_details.items()}
    incomplete_sources = [
        source["key"]
        for source in source_status["sources"]
        if source["status"] in {"required", "recommended", "unknown"}
    ]
    recommendations = generate_recommendations(
        indicators, missing_sources=incomplete_sources if not complete else []
    )
    result, level = _predict(
        request,
        features,
        profile="neutral",
    )

    row = persist_assessment(
        db,
        user_id=user.id,
        profile_id=user.profile.id if user.profile else None,
        result=result,
        reliability_level=level,
    )
    db.add(row)
    db.flush()
    # Store the exact source vector with the assessment. It supports truthful
    # stale-result detection and makes local explanation rows auditable.
    for name, value in features.items():
        db.add(
            Explanation(
                prediction_id=row.id,
                feature_name=name,
                feature_value=json.dumps(value, ensure_ascii=False, sort_keys=True),
                contribution=None,
                explanation_type="feature_snapshot",
            )
        )
    db.add(
        Explanation(
            prediction_id=row.id,
            feature_name="__source_fingerprint__",
            feature_value=_source_fingerprint(db, user),
            contribution=None,
            explanation_type="source_snapshot",
        )
    )
    for item in explanation["top_features"]:
        db.add(
            Explanation(
                prediction_id=row.id,
                feature_name=item["feature"],
                feature_value=json.dumps(item["value"], ensure_ascii=False),
                contribution=item["contribution"],
                explanation_type="SHAP_LOCAL",
            )
        )
    db.add(
        Explanation(
            prediction_id=row.id,
            feature_name="assessment_state",
            feature_value=json.dumps(source_status["assessment_state"]),
            contribution=None,
            explanation_type=ASSESSMENT_METADATA_TYPE,
        )
    )
    for key, detail in indicator_details.items():
        db.add(
            Explanation(
                prediction_id=row.id,
                feature_name=key,
                feature_value=json.dumps(detail, ensure_ascii=False, sort_keys=True),
                contribution=None,
                explanation_type=INDICATOR_EXPLANATION_TYPE,
            )
        )
    for index, recommendation in enumerate(recommendations):
        db.add(
            Explanation(
                prediction_id=row.id,
                feature_name=f"recommendation_{index + 1}",
                feature_value=json.dumps(
                    recommendation, ensure_ascii=False, sort_keys=True
                ),
                contribution=None,
                explanation_type=RECOMMENDATION_EXPLANATION_TYPE,
            )
        )
    db.flush()
    return {
        "id": row.id,
        "frie_score": round(score, 2),
        "reliability_level": level,
        "model_version": row.model_version,
        "created_at": row.created_at,
        "readiness": readiness,
        "source_readiness": source_status["sources"],
        "assessment_state": source_status["assessment_state"],
        "stale": False,
        "indicators": indicators,
        "indicator_details": indicator_details,
        "recommendations": recommendations,
        "explanation": explanation,
    }


@router.get("/latest")
def latest_assessment(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any] | None:
    row = (
        db.query(Prediction)
        .filter(Prediction.user_id == user.id)
        .order_by(Prediction.id.desc())
        .first()
    )
    if row is None:
        return None
    assembly = feature_engineering.assemble(db, user)
    readiness = feature_engineering.readiness_report(assembly, get_feature_contract())
    snapshots = (
        db.query(Explanation)
        .filter(
            Explanation.prediction_id == row.id,
            Explanation.explanation_type == "feature_snapshot",
        )
        .all()
    )
    previous = {item.feature_name: item.feature_value for item in snapshots}
    current = {
        name: json.dumps(value, ensure_ascii=False, sort_keys=True)
        for name, value in assembly.values.items()
    }
    source_snapshot = (
        db.query(Explanation)
        .filter(
            Explanation.prediction_id == row.id,
            Explanation.explanation_type == "source_snapshot",
        )
        .first()
    )
    persisted = _stored_assessment_details(db, row.id)
    stale = (
        (persisted["assessment_state"] == "complete" and readiness["status"] != "READY")
        or previous != current
        or source_snapshot is None
        or source_snapshot.feature_value != _source_fingerprint(db, user)
    )
    return {
        "id": row.id,
        "frie_score": row.predicted_frie_score,
        "reliability_level": row.reliability_level,
        "model_version": row.model_version,
        "created_at": row.created_at,
        "readiness": readiness,
        "source_readiness": _source_readiness(db, user, assembly, readiness)["sources"],
        "stale": stale,
        **persisted,
    }


@router.get("/history")
def assessment_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:

    rows = (
        db.query(Prediction)
        .filter(Prediction.user_id == user.id)
        .order_by(Prediction.id.desc())
        .all()
    )

    return [deserialize_assessment(row) for row in rows]


@router.get("/explanation")
def local_explanation(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    assembly = feature_engineering.assemble(db, user)
    readiness = feature_engineering.readiness_report(assembly, get_feature_contract())
    source_status = _source_readiness(db, user, assembly, readiness)
    if not source_status["can_assess"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": source_status["message"],
                "assessment_state": "insufficient",
                "sources": source_status["sources"],
            },
        )
    complete = source_status["assessment_state"] == "complete"
    service = request.app.state.prediction_service
    try:
        if complete:
            score = service.predict(assembly.values)
            model_features = assembly.values
        else:
            model_features = {
                name: assembly.values.get(name)
                for name in get_feature_contract().feature_names
            }
            score, _metadata = service.predict_with_partial_data(assembly.values)
        from app.api.routes.prediction import reliability_level

        level = reliability_level(score)
        explanation = service.explain(model_features, allow_missing=not complete)
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="FRIE explanation service is temporarily unavailable.",
        ) from exc
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": source_status["message"],
                "assessment_state": "insufficient",
                "sources": source_status["sources"],
            },
        ) from exc
    except (FeatureInputError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "score": round(score, 2),
        "reliability_level": level,
        "assessment_state": source_status["assessment_state"],
        "readiness": {
            "assessment_state": source_status["assessment_state"],
            "sources": source_status["sources"],
        },
        **explanation,
        "disclaimer": "SHAP values describe local model contributions, not causal effects.",
    }

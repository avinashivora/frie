"""Persistence helpers for FRIE six-dimension assessments."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Prediction

ALGORITHM_VERSION = "FRIE-6D-v1.0"
FRIE_MAXIMUM = 600.0


def _extract_overall_coverage(result: dict[str, Any]) -> float | None:
    """Read overall coverage from the deterministic scoring result."""

    frie_score = result.get("frie_score") or {}

    coverage = frie_score.get("coverage")

    if coverage is None:
        coverage = result.get("coverage")

    if coverage is None:
        return None

    return float(coverage)


def _extract_overall_confidence(result: dict[str, Any]) -> float | None:
    """Read overall confidence from the deterministic scoring result."""

    frie_score = result.get("frie_score") or {}

    confidence = frie_score.get("confidence")

    if confidence is None:
        confidence = result.get("confidence")

    # The scoring engine may eventually expose confidence as a
    # qualitative label. Do not force that into a numeric database field.
    if isinstance(confidence, (int, float)):
        return float(confidence)

    return None


def persist_assessment(
    db: Session,
    *,
    user_id: int,
    profile_id: int | None,
    result: dict[str, Any],
    reliability_level: str,
) -> Prediction:
    """Persist one deterministic FRIE assessment.

    The complete dimension result is stored as JSON text so that the exact
    assessment output remains available for historical/audit purposes.
    """

    frie_score = result.get("frie_score") or {}

    score = frie_score.get("value")

    if score is None:
        score = frie_score.get("score")

    if score is None:
        raise ValueError("FRIE result does not contain a score value.")

    maximum = frie_score.get(
        "maximum",
        FRIE_MAXIMUM,
    )

    algorithm_version = result.get(
        "algorithm_version",
        ALGORITHM_VERSION,
    )

    scoring_profile = (
        result.get("profile", {}).get("profile")
        if isinstance(result.get("profile"), dict)
        else None
    )

    if not scoring_profile:
        scoring_profile = "neutral"

    dimensions = result.get("dimensions", {})

    row = Prediction(
        user_id=user_id,
        profile_id=profile_id,
        # Existing compatibility fields.
        predicted_frie_score=round(float(score), 2),
        reliability_level=reliability_level,
        model_version=algorithm_version,
        # New deterministic FRIE fields.
        algorithm_version=algorithm_version,
        frie_maximum=float(maximum),
        scoring_profile=scoring_profile,
        dimensions_json=json.dumps(
            dimensions,
            ensure_ascii=False,
            sort_keys=True,
        ),
        overall_coverage=_extract_overall_coverage(result),
        overall_confidence=_extract_overall_confidence(result),
    )

    db.add(row)
    db.flush()

    return row


def deserialize_assessment(row: Prediction) -> dict[str, Any]:
    """Reconstruct the persisted deterministic FRIE result."""

    try:
        dimensions = json.loads(row.dimensions_json or "{}")
    except (TypeError, json.JSONDecodeError):
        dimensions = {}

    return {
        "id": row.id,
        "frie_score": {
            "value": row.predicted_frie_score,
            "maximum": row.frie_maximum,
        },
        "algorithm_version": row.algorithm_version,
        "profile": row.scoring_profile,
        "coverage": row.overall_coverage,
        "confidence": row.overall_confidence,
        "dimensions": dimensions,
        "reliability_level": row.reliability_level,
        "created_at": row.created_at,
    }

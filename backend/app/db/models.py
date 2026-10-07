"""FRIE persistence models: users, sessions, profiles, documents, features, predictions, explanations."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

DOCUMENT_TYPES = (
    "salary_income_proof",
    "bank_statement",
    "bank_import",
    "credit_report",
    "loan_document",
    "insurance_document",
    "investment_statement",
)

PROCESSING_STATUSES = ("UPLOADED", "PROCESSING", "EXTRACTED", "FAILED")
EXTRACTION_STATUSES = ("PENDING", "EXTRACTED", "FAILED")
REVIEW_STATUSES = ("PENDING", "REVIEW_REQUIRED", "APPROVED", "FAILED")

FEATURE_PROVENANCE = ("USER", "DOCUMENT", "DERIVED", "VERIFIED", "USER_CONFIRMED")
FEATURE_STATUSES = ("DRAFT", "REVIEWED", "READY", "UNKNOWN")


class User(TimestampMixin, Base):
    """Registered FRIE user. Only a salted hash is stored, never a password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["CustomerProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(TimestampMixin, Base):
    """Opaque login session. Only the token hash is stored, never the token."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class CustomerProfile(TimestampMixin, Base):
    """Raw user-provided profile inputs for the Phase 1.5 USER layer.

    Stores inputs only (dates, city, occupation); age, employment years,
    tiers, bands, and household size are derived from these in a later
    phase. No feature-engineering logic lives here or in the database.
    """

    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    gender: Mapped[str | None] = mapped_column(String(32))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    children_count: Mapped[int | None] = mapped_column(Integer)
    family_size: Mapped[int | None] = mapped_column(Integer)
    family_status: Mapped[str | None] = mapped_column(String(64))
    education_level: Mapped[str | None] = mapped_column(String(64))
    housing_type: Mapped[str | None] = mapped_column(String(64))
    owns_car: Mapped[str | None] = mapped_column(String(8))
    owns_property: Mapped[str | None] = mapped_column(String(8))
    income_type: Mapped[str | None] = mapped_column(String(64))
    occupation: Mapped[str | None] = mapped_column(String(64))
    organization_type: Mapped[str | None] = mapped_column(String(64))
    contract_type: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(128))
    monthly_income: Mapped[float | None] = mapped_column(Float)
    employment_start: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="profile")


class Document(TimestampMixin, Base):
    """Document metadata only. Phase 2 performs no OCR or extraction."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(32))
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_reference: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processing_status: Mapped[str] = mapped_column(String(32), default="UPLOADED")
    extraction_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    source_type: Mapped[str] = mapped_column(String(64), default="manual_upload")
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING")

    user: Mapped[User] = relationship(back_populates="documents")


class FinancialFeature(TimestampMixin, Base):
    """One stored model feature value with its Phase 1.5 provenance.

    Normalized per-feature rows (not a JSON blob) so provenance and review
    status stay queryable per feature. Nothing is imputed or fabricated:
    absent values simply have no row, and READY status requires a complete
    validated vector assembled by a later phase.
    """

    __tablename__ = "financial_features"
    __table_args__ = (
        UniqueConstraint("user_id", "feature_name", name="uq_features_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    feature_name: Mapped[str] = mapped_column(String(128), index=True)
    feature_type: Mapped[str] = mapped_column(String(16))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    confidence: Mapped[float | None] = mapped_column(Float)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(backref="financial_features")


class Prediction(TimestampMixin, Base):
    """Stored FRIE assessment result.

    The deterministic six-dimension FRIE methodology is the authoritative
    scoring system. Historical assessments retain the methodology version
    and full dimension result so they remain auditable if the methodology
    changes later.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="SET NULL")
    )

    # Legacy/general display fields retained for compatibility.
    predicted_frie_score: Mapped[float] = mapped_column(Float)
    reliability_level: Mapped[str] = mapped_column(String(16))
    model_version: Mapped[str] = mapped_column(String(64))

    # ------------------------------------------------------------------
    # FRIE six-dimension methodology persistence
    # ------------------------------------------------------------------

    algorithm_version: Mapped[str] = mapped_column(
        String(64),
        default="FRIE-6D-v1.0",
        index=True,
    )

    frie_maximum: Mapped[float] = mapped_column(
        Float,
        default=600.0,
    )

    scoring_profile: Mapped[str] = mapped_column(
        String(16),
        default="neutral",
        index=True,
    )

    # JSON serialized as TEXT for SQLite/RDBMS portability.
    dimensions_json: Mapped[str] = mapped_column(
        Text,
        default="{}",
    )

    overall_coverage: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    overall_confidence: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="predictions")

    explanations: Mapped[list["Explanation"]] = relationship(
        back_populates="prediction",
        cascade="all, delete-orphan",
    )


class Explanation(TimestampMixin, Base):
    """Per-feature explanation contributions (e.g. future SHAP values)."""

    __tablename__ = "explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), index=True
    )
    feature_name: Mapped[str] = mapped_column(String(128))
    feature_value: Mapped[str | None] = mapped_column(Text)
    contribution: Mapped[float | None] = mapped_column(Float)
    explanation_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prediction: Mapped[Prediction] = relationship(back_populates="explanations")


class Extraction(TimestampMixin, Base):
    """Raw extraction output for one document. One row per document (upserted on re-run).

    Holds OCR/text output and structured raw fields only. Never holds model
    features, scores, or verified values; verification happens in later phases.
    """

    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structured_data: Mapped[str] = mapped_column(Text, default="{}")
    extraction_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    engine: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(backref="extraction", uselist=False)


class FinancialStatus(TimestampMixin, Base):
    """User-declared product availability. Distinguishes confirmed NONE from UNKNOWN.

    One row per user. Null means never answered. These declarations tell
    feature engineering which absences are legitimate states versus gaps;
    they never invent financial values themselves.
    """

    __tablename__ = "financial_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    has_loan: Mapped[str | None] = mapped_column(String(16))
    insurance_status: Mapped[str | None] = mapped_column(String(16))
    inv_fd: Mapped[str | None] = mapped_column(String(16))
    inv_rd: Mapped[str | None] = mapped_column(String(16))
    inv_sip: Mapped[str | None] = mapped_column(String(16))
    inv_mutual_fund: Mapped[str | None] = mapped_column(String(16))
    inv_ppf: Mapped[str | None] = mapped_column(String(16))
    inv_nps: Mapped[str | None] = mapped_column(String(16))

    user: Mapped[User] = relationship(backref="financial_status", uselist=False)

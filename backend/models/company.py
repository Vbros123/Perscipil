"""Company search, saved company, and report models."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanySearch(Base):
    __tablename__ = "company_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String(180), index=True, nullable=True)
    private_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    query_type: Mapped[str] = mapped_column(String(30), default="score", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user = relationship("User", back_populates="searches")


class SavedCompany(Base):
    __tablename__ = "saved_companies"
    __table_args__ = (UniqueConstraint("user_id", "normalized_name", name="uq_saved_user_company"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False)
    private_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str | None] = mapped_column(String(60), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scoring_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="saved_companies")


class CompanyReport(Base):
    __tablename__ = "company_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String(180), index=True, nullable=True)
    private_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str] = mapped_column(String(60), nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    scoring_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_snapshot_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    user = relationship("User", back_populates="reports")

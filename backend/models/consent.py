from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class ProviderConsent(Base):
    __tablename__ = "provider_consents"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "connection_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))
    connection_id: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ConsentPayload(Base):
    __tablename__ = "consent_payloads"
    __table_args__ = (UniqueConstraint("consent_id", "cache_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    consent_id: Mapped[int] = mapped_column(
        ForeignKey("provider_consents.id", ondelete="CASCADE"), index=True
    )
    cache_key: Mapped[str] = mapped_column(String(64))
    encrypted_payload: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

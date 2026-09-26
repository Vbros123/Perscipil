from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class MfaCredential(Base):
    __tablename__ = "mfa_credentials"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_secret: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_counter: Mapped[int] = mapped_column(Integer, default=-1)
    recovery_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    recovery_hashes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

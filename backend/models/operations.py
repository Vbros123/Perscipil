from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

class OperationLease(Base):
    __tablename__ = 'operation_leases'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class DeletionMarker(Base):
    __tablename__ = 'deletion_markers'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

"""Durable, account-owned pilot workflows. No implied multi-user organization support."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

def now():
    return datetime.now(timezone.utc)

class Batch(Base):
    __tablename__ = 'batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class BatchItem(Base):
    __tablename__ = 'batch_items'
    __table_args__ = (UniqueConstraint('batch_id', 'position'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    identity: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(160), nullable=True)

class Correction(Base):
    __tablename__ = 'corrections'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True, nullable=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey('company_reports.id', ondelete='SET NULL'), nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(String(60))
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    review_history: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ApiKey(Base):
    __tablename__ = 'customer_api_keys'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    key_hash: Mapped[str] = mapped_column(String(80), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    revoked: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Subscription(Base):
    __tablename__ = 'monitor_subscriptions'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    identity: Mapped[dict] = mapped_column(JSON)
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    previous: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class MonitorEvent(Base):
    __tablename__ = 'monitor_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('monitor_subscriptions.id', ondelete='CASCADE'))
    payload: Mapped[dict] = mapped_column(JSON)
    delivery_status: Mapped[str] = mapped_column(String(30), default='in_app')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class PolicyAcceptance(Base):
    __tablename__ = 'policy_acceptances'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    terms_version: Mapped[str] = mapped_column(String(40))
    privacy_version: Mapped[str] = mapped_column(String(40))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class PilotReview(Base):
    __tablename__ = 'pilot_reviews'
    __table_args__ = (UniqueConstraint('user_id', 'report_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('company_reports.id', ondelete='CASCADE'))
    measurements: Mapped[dict] = mapped_column(JSON)

class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer)

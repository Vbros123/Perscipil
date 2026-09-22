"""Configurable technical retention; periods require operator/legal approval."""

from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import delete, select, update
from core.config import get_settings
from core.database import SessionLocal
from models.user import AuthAuditEvent
from models.organizations import (
    OrganizationAudit,
    OrganizationResource,
    Delivery,
    WorkJob,
)
from models.consent import ConsentPayload, ProviderConsent


# No expiry of control history unless explicitly configured. Report content uses
# the existing research-retention default, which is not a legal conclusion.
def purge_extended():
    settings = get_settings()
    periods = json.loads(settings.RETENTION_PERIODS_JSON)
    now = datetime.now(timezone.utc)
    counts = {}
    with SessionLocal.begin() as db:
        for label, model, column in [
            ("auth_events", AuthAuditEvent, AuthAuditEvent.created_at),
            ("audit_events", OrganizationAudit, OrganizationAudit.created_at),
            ("deliveries", Delivery, Delivery.delivered_at),
            ("jobs", WorkJob, WorkJob.completed_at),
        ]:
            days = periods.get(label)
            if days is None:
                continue
            if not isinstance(days, int) or days < 1:
                raise ValueError("Retention days must be positive integers")
            counts[label] = db.execute(
                delete(model).where(column < now - timedelta(days=days))
            ).rowcount
        counts["expired_provider_payloads"] = db.execute(
            delete(ConsentPayload).where(ConsentPayload.expires_at <= now)
        ).rowcount
        expired = select(ProviderConsent.id).where(
            (ProviderConsent.expires_at <= now) | (ProviderConsent.state != "active")
        )
        counts["revoked_provider_payloads"] = db.execute(
            delete(ConsentPayload).where(ConsentPayload.consent_id.in_(expired))
        ).rowcount
        days = periods.get("reports", settings.REPORT_RETENTION_DAYS)
        if not isinstance(days, int) or days < 1:
            raise ValueError("Report retention days must be positive")
        # Keep shells referenced by jobs, purge payloads. No orphaning event/report IDs.
        rows = db.scalars(
            select(OrganizationResource).where(
                OrganizationResource.kind.in_(["report", "monitor_event"]),
                OrganizationResource.created_at < now - timedelta(days=days),
            )
        )
        counts["report_payloads"] = 0
        for row in rows:
            if row.payload.get("status") != "expired":
                row.payload = {"status": "expired", "reason": "retention_policy"}
                counts["report_payloads"] += 1
    return counts

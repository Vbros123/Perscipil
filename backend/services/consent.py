"""Consent-bound storage interface. Does not activate a provider or grant legal rights."""

import hashlib, json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from fastapi import HTTPException
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet, InvalidToken
from core.config import get_settings

def cipher():
    key = get_settings().CONSENT_ENCRYPTION_KEY
    if not key:
        raise HTTPException(503, "Consent encryption key is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Consent encryption configuration unavailable")
from models.consent import ProviderConsent, ConsentPayload


class Permissions(BaseModel):
    can_score: bool = False
    can_display_raw: bool = False
    can_display_derived: bool = False
    can_retain: bool = False
    retention_days: int = Field(default=0, ge=0, le=3650)
    can_monitor: bool = False
    can_use_historically: bool = False
    can_use_for_model_training: bool = False
    can_redistribute_via_api: bool = False


def active_consent(db, org_id, consent_id, purpose):
    row = db.scalar(
        select(ProviderConsent)
        .where(
            ProviderConsent.id == consent_id, ProviderConsent.organization_id == org_id
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Consent not found")
    expires = (
        row.expires_at.replace(tzinfo=timezone.utc)
        if row.expires_at.tzinfo is None
        else row.expires_at
    )
    permissions = Permissions(**row.permissions)
    if (
        row.state != "active"
        or row.revoked_at
        or expires <= datetime.now(timezone.utc)
        or purpose not in {name for name in Permissions.model_fields if name.startswith("can_")}
        or not getattr(permissions, purpose, False)
    ):
        raise HTTPException(403, "Consent or permitted purpose unavailable")
    return row, permissions


def put(db, org_id, consent_id, identity, payload):
    row, p = active_consent(db, org_id, consent_id, "can_retain")
    if p.retention_days <= 0:
        raise HTTPException(403, "Retention duration not approved")
    key = hashlib.sha256(
        json.dumps(
            [org_id, consent_id, row.connection_id, row.subject_id, identity],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    expiry = min(
        row.expires_at.replace(tzinfo=timezone.utc),
        datetime.now(timezone.utc) + timedelta(days=p.retention_days),
    )
    cached = db.scalar(
        select(ConsentPayload).where(
            ConsentPayload.consent_id == row.id, ConsentPayload.cache_key == key
        )
    )
    if not cached:
        cached = ConsentPayload(consent_id=row.id, cache_key=key)
        db.add(cached)
    cached.encrypted_payload = cipher().encrypt(json.dumps(payload).encode()).decode()
    cached.expires_at = expiry
    db.flush()
    return key


def get(db, org_id, consent_id, key, purpose="can_score"):
    active_consent(db, org_id, consent_id, purpose)
    row = db.scalar(
        select(ConsentPayload).where(
            ConsentPayload.consent_id == consent_id,
            ConsentPayload.cache_key == key,
            ConsentPayload.expires_at > datetime.now(timezone.utc),
        )
    )
    try:
        return json.loads(cipher().decrypt(row.encrypted_payload.encode())) if row else None
    except InvalidToken:
        raise HTTPException(503, "Consent payload unavailable; contact the operator")


def revoke(db, org_id, consent_id):
    row = db.scalar(
        select(ProviderConsent)
        .where(
            ProviderConsent.id == consent_id, ProviderConsent.organization_id == org_id
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Consent not found")
    row.state = "revoked"
    row.revoked_at = datetime.now(timezone.utc)
    db.execute(delete(ConsentPayload).where(ConsentPayload.consent_id == consent_id))
    db.flush()


def limited_view(raw, derived, permissions, via_api=False):
    p = Permissions(**permissions)
    if via_api and not p.can_redistribute_via_api:
        return {"status": "withheld", "reason": "redistribution_not_permitted"}
    result = {
        "status": "limited",
        "raw": raw if p.can_display_raw else None,
        "derived": derived if p.can_display_derived else None,
    }
    return result

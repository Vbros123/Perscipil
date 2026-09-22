"""Workspace membership and tenant-bound public-evidence research."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_user, hash_security_token
from core.tenancy import authorize, locked_organization, resource, audit
from models.user import User
from models.organizations import (
    Organization,
    Membership,
    Invitation,
    OrganizationKey,
    OrganizationResource,
)
from services.evidence import CompanyIdentity

router = APIRouter(prefix="/api/organizations", tags=["Workspaces"])


class CreateOrganization(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.post("", status_code=201)
def create(
    payload: CreateOrganization,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(select(User).where(User.id == user.id).with_for_update())
    if (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == user.id, Membership.role == "owner")
        )
        >= 5
    ):
        raise HTTPException(409, "Workspace ownership limit reached")
    row = Organization(name=payload.name.strip())
    db.add(row)
    db.flush()
    db.add(Membership(organization_id=row.id, user_id=user.id, role="owner"))
    audit(db, row.id, user.id, "workspace_created")
    db.commit()
    return {"id": row.id, "name": row.name, "role": "owner"}


@router.get("")
def list_organizations(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {"id": o.id, "name": o.name, "role": m.role, "require_mfa": o.require_mfa}
        for o, m in db.execute(
            select(Organization, Membership)
            .join(Membership)
            .where(Membership.user_id == user.id, Membership.active.is_(True))
        )
    ]


class Invite(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


@router.post("/{organization_id}/invitations", status_code=201)
def invite(
    organization_id: int,
    payload: Invite,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    member = authorize(db, organization_id, user, "members")
    if payload.role == "admin" and member.role != "owner":
        raise HTTPException(403, "Only the owner can invite administrators")
    count = db.scalar(
        select(func.count())
        .select_from(Invitation)
        .where(
            Invitation.organization_id == organization_id,
            Invitation.used.is_(False),
            Invitation.expires_at > datetime.now(timezone.utc),
        )
    )
    if count >= 100:
        raise HTTPException(409, "Too many pending invitations")
    token = secrets.token_urlsafe(32)
    row = Invitation(
        organization_id=organization_id,
        email=str(payload.email).lower(),
        role=payload.role,
        token_hash=hash_security_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(row)
    audit(db, organization_id, user.id, "invitation_created")
    db.commit()
    return {
        "invitation_token": token,
        "expires_at": row.expires_at,
        "delivery": "Share privately with the invited verified email owner.",
    }


class Accept(BaseModel):
    token: str = Field(min_length=20, max_length=200)


@router.post("/invitations/accept")
def accept(
    payload: Accept, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    row = db.scalar(
        select(Invitation).where(
            Invitation.token_hash == hash_security_token(payload.token)
        )
    )
    if not row or row.email != user.email.lower() or not user.email_verified:
        raise HTTPException(403, "A matching verified email is required")
    locked_organization(db, row.organization_id)
    claimed = db.execute(
        update(Invitation)
        .where(
            Invitation.id == row.id,
            Invitation.used.is_(False),
            Invitation.expires_at > datetime.now(timezone.utc),
        )
        .values(used=True)
        .execution_options(synchronize_session=False)
    )
    if not claimed.rowcount:
        raise HTTPException(409, "Invitation expired or consumed")
    member = db.get(Membership, (row.organization_id, user.id))
    if member and member.active:
        raise HTTPException(409, "Already a member")
    if member:
        member.active = True
        member.role = row.role
    else:
        db.add(
            Membership(
                organization_id=row.organization_id, user_id=user.id, role=row.role
            )
        )
    audit(db, row.organization_id, user.id, "invitation_accepted")
    db.commit()
    return {"organization_id": row.organization_id}


@router.get("/{organization_id}/members")
def members(
    organization_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    authorize(db, organization_id, user)
    return [
        {"user_id": m.user_id, "email": u.email, "role": m.role, "active": m.active}
        for m, u in db.execute(
            select(Membership, User)
            .join(User)
            .where(Membership.organization_id == organization_id)
        )
    ]


class RoleChange(BaseModel):
    role: Literal["admin", "member"]


@router.patch("/{organization_id}/members/{user_id}")
def change_role(
    organization_id: int,
    user_id: int,
    payload: RoleChange,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "owner")
    member = db.get(Membership, (organization_id, user_id))
    if not member or not member.active:
        raise HTTPException(404, "Member not found")
    if member.role == "owner":
        raise HTTPException(
            409, "Transfer ownership explicitly before changing the owner"
        )
    member.role = payload.role
    audit(db, organization_id, user.id, "member_role_changed", user_id)
    db.commit()
    return {"updated": True}


@router.delete("/{organization_id}/members/{user_id}")
def remove(
    organization_id: int,
    user_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    actor = authorize(db, organization_id, user, "members")
    member = db.get(Membership, (organization_id, user_id))
    if not member:
        raise HTTPException(404, "Member not found")
    if member.role == "owner" or (member.role == "admin" and actor.role != "owner"):
        raise HTTPException(
            403, "Only the owner can remove administrators; owner cannot be removed"
        )
    member.active = False
    audit(db, organization_id, user.id, "member_revoked", user_id)
    db.commit()
    return {"revoked": True}


class KeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    scopes: list[Literal["score:read", "reports:read"]] = Field(
        default=["score:read"], min_length=1, max_length=2
    )


@router.post("/{organization_id}/keys", status_code=201)
def create_key(
    organization_id: int,
    payload: KeyCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "keys")
    if (
        db.scalar(
            select(func.count())
            .select_from(OrganizationKey)
            .where(
                OrganizationKey.organization_id == organization_id,
                OrganizationKey.revoked.is_(False),
            )
        )
        >= 10
    ):
        raise HTTPException(409, "Ten active keys maximum")
    secret = "plo_" + secrets.token_urlsafe(32)
    key = OrganizationKey(
        organization_id=organization_id,
        label=payload.label,
        scopes=sorted(set(payload.scopes)),
        key_hash=hash_security_token(secret),
    )
    db.add(key)
    db.flush()
    audit(db, organization_id, user.id, "key_created", key.id)
    db.commit()
    return {"id": key.id, "key": secret, "scopes": key.scopes}


@router.get("/{organization_id}/keys")
def keys(
    organization_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    authorize(db, organization_id, user, "keys")
    return [
        {
            "id": k.id,
            "label": k.label,
            "scopes": k.scopes,
            "revoked": k.revoked,
            "calls": k.calls,
        }
        for k in db.scalars(
            select(OrganizationKey).where(
                OrganizationKey.organization_id == organization_id
            )
        )
    ]


@router.delete("/{organization_id}/keys/{key_id}")
def revoke(
    organization_id: int,
    key_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "keys")
    key = db.scalar(
        select(OrganizationKey).where(
            OrganizationKey.organization_id == organization_id,
            OrganizationKey.id == key_id,
        )
    )
    if not key:
        raise HTTPException(404, "Key not found")
    key.revoked = True
    audit(db, organization_id, user.id, "key_revoked", key.id)
    db.commit()
    return {"revoked": True}


@router.get("/{organization_id}/resources")
def resources(
    organization_id: int,
    kind: Literal["watchlist", "report", "correction"] = "watchlist",
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    authorize(db, organization_id, user)
    rows = list(
        db.scalars(
            select(OrganizationResource)
            .where(
                OrganizationResource.organization_id == organization_id,
                OrganizationResource.kind == kind,
                OrganizationResource.id > after,
            )
            .order_by(OrganizationResource.id)
            .limit(limit)
        )
    )
    return {
        "items": [
            {
                "id": r.id,
                "kind": r.kind,
                "payload": r.payload,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "next_cursor": rows[-1].id if len(rows) == limit else None,
    }


@router.post("/{organization_id}/watchlist", status_code=201)
def save(
    organization_id: int,
    identity: CompanyIdentity,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    import hashlib

    key = hashlib.sha256(identity.cache_key().encode()).hexdigest()
    existing = db.scalar(
        select(OrganizationResource).where(
            OrganizationResource.organization_id == organization_id,
            OrganizationResource.kind == "watchlist",
            OrganizationResource.dedupe_key == key,
        )
    )
    if existing:
        return {"id": existing.id}
    row = OrganizationResource(
        organization_id=organization_id,
        kind="watchlist",
        dedupe_key=key,
        payload=identity.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()
    audit(db, organization_id, user.id, "company_saved", row.id)
    db.commit()
    return {"id": row.id}


@router.delete("/{organization_id}/resources/{resource_id}")
def remove_resource(
    organization_id: int,
    resource_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    row = resource(db, organization_id, resource_id)
    if row.kind != "watchlist":
        raise HTTPException(403, "Only saved-company removal is supported here")
    db.delete(row)
    audit(db, organization_id, user.id, "company_removed", resource_id)
    db.commit()
    return {"deleted": True}


class ScoreRequest(BaseModel):
    identity: CompanyIdentity
    idempotency_key: str = Field(
        min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$"
    )


@router.post("/{organization_id}/scores", status_code=202)
def queue_score(
    organization_id: int,
    payload: ScoreRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from services.jobs import enqueue

    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    job = enqueue(
        db,
        organization_id,
        "score",
        payload.identity.model_dump(mode="json"),
        payload.idempotency_key,
    )
    audit(db, organization_id, user.id, "score_queued", job.id)
    db.commit()
    return {"job_id": job.id, "state": job.state}


@router.get("/{organization_id}/jobs")
def jobs(
    organization_id: int,
    after: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from models.organizations import WorkJob

    authorize(db, organization_id, user)
    rows = list(
        db.scalars(
            select(WorkJob)
            .where(WorkJob.organization_id == organization_id, WorkJob.id > after)
            .order_by(WorkJob.id)
            .limit(limit)
        )
    )
    return {
        "items": [
            {
                "id": r.id,
                "company": r.payload.get("legal_name"),
                "state": r.state,
                "attempts": r.attempts,
                "error_code": r.error_code,
                "report_id": r.result_id,
                "batch_key": r.batch_key,
            }
            for r in rows
        ],
        "next_cursor": rows[-1].id if len(rows) == limit else None,
    }


@router.post("/{organization_id}/jobs/{job_id}/cancel")
def cancel(
    organization_id: int,
    job_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from models.organizations import WorkJob

    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    row = db.scalar(
        select(WorkJob).where(
            WorkJob.organization_id == organization_id, WorkJob.id == job_id
        )
    )
    if not row:
        raise HTTPException(404, "Job not found")
    db.execute(
        update(WorkJob)
        .where(WorkJob.id == job_id, WorkJob.state.in_(["queued", "retry", "running"]))
        .values(state="cancelled", claim_token=None)
    )
    audit(db, organization_id, user.id, "job_cancelled", job_id)
    db.commit()
    return {"cancelled": True}


class BulkRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=524288)
    idempotency_key: str = Field(
        min_length=8, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )


@router.post("/{organization_id}/batches", status_code=202)
def bulk(
    organization_id: int,
    payload: BulkRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import csv, io
    from services.jobs import enqueue, digest

    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    if len(payload.csv_text.encode()) > 524288 or "\0" in payload.csv_text:
        raise HTTPException(422, "Invalid CSV or exceeds 512 KiB")
    try:
        reader = csv.DictReader(
            io.StringIO(payload.csv_text.lstrip("\ufeff")), strict=True
        )
        if (
            not reader.fieldnames
            or "company" not in reader.fieldnames
            or len(set(reader.fieldnames)) != len(reader.fieldnames)
        ):
            raise ValueError("A unique company column is required")
        identities = {}
        count = 0
        for row in reader:
            count += 1
            if count > 1000 or None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV or exceeds 1000 rows")
            identity = CompanyIdentity(
                legal_name=row["company"],
                country_code=row.get("country_code") or "US",
                registration_number=row.get("registration_number") or None,
                postal_code=row.get("postal_code") or None,
            )
            identities[identity.cache_key()] = identity.model_dump(mode="json")
        if not identities:
            raise ValueError("No company rows")
    except (ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc)[:200]) from exc
    # Persist a request fingerprint so a shortened retry cannot partially reuse a batch key.
    fingerprint = digest(list(identities.values()))
    existing = db.scalar(
        select(OrganizationResource).where(
            OrganizationResource.organization_id == organization_id,
            OrganizationResource.kind == "batch",
            OrganizationResource.dedupe_key == payload.idempotency_key,
        )
    )
    if existing and existing.payload["fingerprint"] != fingerprint:
        raise HTTPException(409, "Batch idempotency key conflicts")
    if not existing:
        db.add(
            OrganizationResource(
                organization_id=organization_id,
                kind="batch",
                dedupe_key=payload.idempotency_key,
                payload={"fingerprint": fingerprint, "rows": len(identities)},
            )
        )
    ids = [
        enqueue(
            db,
            organization_id,
            "score",
            identity,
            f"{payload.idempotency_key}:{i}",
            payload.idempotency_key,
        ).id
        for i, identity in enumerate(identities.values())
    ]
    db.commit()
    return {
        "batch_key": payload.idempotency_key,
        "job_ids": ids,
        "duplicates_removed": count - len(ids),
    }


@router.get("/{organization_id}/batches/{batch_key}/export")
def export(
    organization_id: int,
    batch_key: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import csv, io
    from fastapi.responses import PlainTextResponse
    from models.organizations import WorkJob
    from routers.workflows import csv_safe

    authorize(db, organization_id, user)
    rows = list(
        db.scalars(
            select(WorkJob)
            .where(
                WorkJob.organization_id == organization_id,
                WorkJob.batch_key == batch_key,
            )
            .order_by(WorkJob.id)
            .limit(1000)
        )
    )
    if not rows:
        raise HTTPException(404, "Batch not found")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["company", "state", "research_score", "error_code"])
    for row in rows:
        report = (
            resource(db, organization_id, row.result_id, "report")
            if row.result_id
            else None
        )
        writer.writerow(
            [
                csv_safe(v)
                for v in [
                    row.payload["legal_name"],
                    row.state,
                    report.payload.get("private_score") if report else None,
                    row.error_code,
                ]
            ]
        )
    return PlainTextResponse(
        out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="workspace-screening.csv"'
        },
    )


class Transfer(BaseModel):
    user_id: int


@router.post("/{organization_id}/ownership")
def transfer(
    organization_id: int,
    payload: Transfer,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    current = authorize(db, organization_id, user, "owner")
    target = db.get(Membership, (organization_id, payload.user_id))
    if not target or not target.active or target.user_id == user.id:
        raise HTTPException(422, "Choose another active member")
    target.role = "owner"
    current.role = "admin"
    audit(db, organization_id, user.id, "ownership_transferred", target.user_id)
    db.commit()
    return {"transferred": True}


@router.post("/{organization_id}/monitoring", status_code=201)
def monitor(
    organization_id: int,
    identity: CompanyIdentity,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from models.organizations import Monitor

    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    if (
        db.scalar(
            select(func.count())
            .select_from(Monitor)
            .where(Monitor.organization_id == organization_id, Monitor.active.is_(True))
        )
        >= 100
    ):
        raise HTTPException(409, "Workspace monitoring limit: 100")
    row = Monitor(
        organization_id=organization_id, identity=identity.model_dump(mode="json")
    )
    db.add(row)
    db.flush()
    audit(db, organization_id, user.id, "monitor_created", row.id)
    db.commit()
    return {"id": row.id, "schedule": "weekly", "activation": "requires worker"}


@router.get("/{organization_id}/monitoring")
def monitors(
    organization_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    from models.organizations import Monitor

    authorize(db, organization_id, user)
    return [
        {
            "id": r.id,
            "identity": r.identity,
            "active": r.active,
            "next_run": r.next_run,
            "last_job_id": r.last_job_id,
        }
        for r in db.scalars(
            select(Monitor).where(Monitor.organization_id == organization_id).limit(100)
        )
    ]


@router.delete("/{organization_id}/monitoring/{monitor_id}")
def disable_monitor(
    organization_id: int,
    monitor_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from models.organizations import Monitor, WorkJob

    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    row = db.scalar(
        select(Monitor).where(
            Monitor.organization_id == organization_id, Monitor.id == monitor_id
        )
    )
    if not row:
        raise HTTPException(404, "Monitor not found")
    row.active = False
    if row.last_job_id:
        db.execute(
            update(WorkJob)
            .where(
                WorkJob.id == row.last_job_id,
                WorkJob.state.in_(["queued", "running", "retry"]),
            )
            .values(state="cancelled", claim_token=None)
        )
    db.commit()
    return {"disabled": True}


@router.get("/{organization_id}/notifications")
def notifications(
    organization_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    from models.organizations import Delivery

    authorize(db, organization_id, user)
    return [
        {
            "id": r.id,
            "event_id": r.event_id,
            "channel": r.channel,
            "state": r.state,
            "attempts": r.attempts,
            "last_attempt_at": r.last_attempt_at,
            "delivered_at": r.delivered_at,
            "error_code": r.error_code,
        }
        for r in db.scalars(
            select(Delivery)
            .where(Delivery.organization_id == organization_id)
            .order_by(Delivery.id.desc())
            .limit(100)
        )
    ]


class Dispute(BaseModel):
    report_id: int
    reason: str = Field(min_length=10, max_length=4000)


@router.post("/{organization_id}/corrections", status_code=201)
def dispute(
    organization_id: int,
    payload: Dispute,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    locked_organization(db, organization_id)
    authorize(db, organization_id, user, "write")
    resource(db, organization_id, payload.report_id, "report")
    row = OrganizationResource(
        organization_id=organization_id,
        kind="correction",
        dedupe_key=secrets.token_hex(24),
        payload={
            "report_id": payload.report_id,
            "reason": payload.reason,
            "status": "pending",
            "review_history": [],
        },
    )
    db.add(row)
    db.flush()
    audit(db, organization_id, user.id, "correction_submitted", row.id)
    db.commit()
    return {"id": row.id, "status": "pending"}


class MfaPolicy(BaseModel):
    require_mfa: bool
    password: str = Field(min_length=1, max_length=128)


@router.patch("/{organization_id}/security")
async def security_policy(organization_id: int, payload: MfaPolicy, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from routers.mfa import reauthenticate
    from models.mfa import MfaCredential
    await reauthenticate(db, user, payload.password)
    organization = locked_organization(db, organization_id)
    authorize(db, organization_id, user, "owner")
    credential = db.get(MfaCredential, user.id)
    if payload.require_mfa and not (credential and credential.enabled):
        raise HTTPException(409, "Enroll in MFA before enabling workspace enforcement")
    organization.require_mfa = payload.require_mfa
    audit(db, organization_id, user.id, "mfa_policy_updated")
    db.commit()
    return {"require_mfa": organization.require_mfa}

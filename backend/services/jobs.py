"""Durable at-least-once queue with fenced completions and bounded retries."""

import asyncio
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update, or_, func
from core.database import SessionLocal
from core.tenancy import locked_organization
from models.organizations import WorkJob, OrganizationResource
from services.evidence import CompanyIdentity
from services.reports import score_company

MAX_ATTEMPTS = 4


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def enqueue(db, organization_id, kind, payload, key, batch_key=None):
    locked_organization(db, organization_id)
    fingerprint = digest({"kind": kind, "payload": payload})
    existing = db.scalar(
        select(WorkJob).where(
            WorkJob.organization_id == organization_id, WorkJob.idempotency_key == key
        )
    )
    if existing:
        if existing.payload_hash != fingerprint:
            raise HTTPException(409, "Idempotency key was used for a different request")
        return existing
    if (
        db.scalar(
            select(func.count())
            .select_from(WorkJob)
            .where(
                WorkJob.organization_id == organization_id,
                WorkJob.state.in_(["queued", "running", "retry"]),
            )
        )
        >= 2000
    ):
        raise HTTPException(429, "Workspace queue capacity reached")
    job = WorkJob(
        organization_id=organization_id,
        kind=kind,
        payload=payload,
        payload_hash=fingerprint,
        idempotency_key=key,
        batch_key=batch_key,
    )
    db.add(job)
    db.flush()
    return job


def claim(organization_id):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        locked_organization(db, organization_id)
        db.execute(
            update(WorkJob)
            .where(
                WorkJob.organization_id == organization_id,
                WorkJob.state == "running",
                WorkJob.lease_until < now,
            )
            .values(state="retry", claim_token=None, error_code="LEASE_EXPIRED")
        )
        db.execute(
            update(WorkJob)
            .where(
                WorkJob.organization_id == organization_id,
                WorkJob.state == "retry",
                WorkJob.attempts >= MAX_ATTEMPTS,
            )
            .values(state="failed", error_code="RETRY_EXHAUSTED")
        )
        # At most one in-flight job per workspace, across all cooperating workers.
        if db.scalar(
            select(WorkJob.id)
            .where(
                WorkJob.organization_id == organization_id, WorkJob.state == "running"
            )
            .limit(1)
        ):
            db.commit()
            return None
        row = db.scalar(
            select(WorkJob)
            .where(
                WorkJob.organization_id == organization_id,
                WorkJob.state.in_(["queued", "retry"]),
                WorkJob.available_at <= now,
                WorkJob.attempts < MAX_ATTEMPTS,
            )
            .order_by(WorkJob.available_at, WorkJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if not row:
            db.commit()
            return None
        token = secrets.token_hex(24)
        changed = db.execute(
            update(WorkJob)
            .where(WorkJob.id == row.id, WorkJob.state.in_(["queued", "retry"]))
            .values(
                state="running",
                claim_token=token,
                lease_until=now + timedelta(minutes=3),
                attempts=WorkJob.attempts + 1,
                last_attempt_at=now,
            )
        )
        db.commit()
        if not changed.rowcount:
            return None
        return {
            "id": row.id,
            "organization_id": organization_id,
            "kind": row.kind,
            "payload": row.payload,
            "token": token,
        }


def finish(claimed, result=None, error=None):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        row = db.scalar(
            select(WorkJob)
            .where(
                WorkJob.id == claimed["id"],
                WorkJob.state == "running",
                WorkJob.claim_token == claimed["token"],
            )
            .with_for_update()
        )
        if not row:
            return False
        # CAS fences both cancelled jobs and completions from expired worker leases.
        state = (
            "failed"
            if error and row.attempts >= MAX_ATTEMPTS
            else "retry"
            if error
            else "complete"
        )
        changed = db.execute(
            update(WorkJob)
            .where(
                WorkJob.id == row.id,
                WorkJob.state == "running",
                WorkJob.claim_token == claimed["token"],
            )
            .values(
                state=state,
                claim_token=None,
                lease_until=None,
                error_code=error,
                available_at=now + timedelta(seconds=min(3600, 30 * 2**row.attempts)),
                completed_at=now if state in ("failed", "complete") else None,
            )
        )
        if not changed.rowcount:
            db.rollback()
            return False
        if result is not None and not error:
            report = OrganizationResource(
                organization_id=row.organization_id,
                kind="report",
                dedupe_key="job:" + str(row.id),
                payload=result,
            )
            db.add(report)
            db.flush()
            row.result_id = report.id
        db.commit()
        return True


async def run_one(organization_id, scorer=None):
    claimed = claim(organization_id)
    if not claimed:
        return False
    try:
        from services.licensed_data import enabled

        if enabled():
            raise PermissionError(
                "Tenant worker supports public evidence only until consent integration is activated"
            )
        identity = CompanyIdentity(**claimed["payload"])
        result = await asyncio.wait_for(
            (scorer or score_company)(identity.legal_name, identity=identity),
            timeout=90,
        )
        finish(claimed, result=result)
    except PermissionError:
        finish(claimed, error="PROVIDER_PERMISSION_DENIED")
    except (TimeoutError, asyncio.TimeoutError):
        finish(claimed, error="PROVIDER_TIMEOUT")
    except Exception:
        finish(claimed, error="COLLECTION_FAILED")
    return True


async def run_cycle(concurrency=2, scorer=None):
    concurrency = max(1, min(concurrency, 4))
    with SessionLocal() as db:
        # Oldest workspace first, only one job per workspace per cycle.
        ids = list(
            db.scalars(
                select(WorkJob.organization_id)
                .where(
                    or_(
                        WorkJob.state.in_(["queued", "retry"]),
                        WorkJob.state == "running",
                    )
                )
                .group_by(WorkJob.organization_id)
                .order_by(func.min(WorkJob.available_at))
                .limit(100)
            )
        )
    sem = asyncio.Semaphore(concurrency)

    async def bounded(org):
        async with sem:
            return await run_one(org, scorer)

    return sum(await asyncio.gather(*(bounded(org) for org in ids)))

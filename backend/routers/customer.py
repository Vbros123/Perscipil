"""Versioned, scoped workspace API; keys never authenticate application routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import hash_security_token
from core.tenancy import locked_organization, resource, audit
from models.organizations import Organization, OrganizationKey, OrganizationResource
from routers.organizations import ScoreRequest
from services.jobs import enqueue

router = APIRouter(prefix="/api/v1/workspace", tags=["Customer API v1"])


def key_context(request, db, scope):
    token = request.headers.get("x-api-key", "")
    if not token.startswith("plo_") or len(token) > 200:
        raise HTTPException(401, "Invalid workspace API key")
    key = db.scalar(
        select(OrganizationKey).where(
            OrganizationKey.key_hash == hash_security_token(token),
            OrganizationKey.revoked.is_(False),
        )
    )
    if not key:
        raise HTTPException(401, "Invalid workspace API key")
    if scope not in key.scopes:
        raise HTTPException(403, "API key scope required: " + scope)
    from core.limiter import DatabaseLimiter
    allowed, retry = DatabaseLimiter(120, 60, "workspace-api").check(str(key.organization_id))
    if not allowed:
        raise HTTPException(429, "Workspace API rate limit reached", headers={"Retry-After": str(retry)})
    return key


@router.post("/scores", status_code=202)
def score(payload: ScoreRequest, request: Request, db: Session = Depends(get_db)):
    key = key_context(request, db, "score:read")
    locked_organization(db, key.organization_id)
    from models.organizations import WorkJob

    # Existing requests do not consume the quota twice.
    previous = db.scalar(
        select(WorkJob).where(
            WorkJob.organization_id == key.organization_id,
            WorkJob.idempotency_key == payload.idempotency_key,
        )
    )
    if previous is None:
        used = db.execute(
            update(Organization)
            .where(Organization.id == key.organization_id, Organization.calls < 10000)
            .values(calls=Organization.calls + 1)
        )
        if not used.rowcount:
            raise HTTPException(429, "Workspace pilot quota exhausted")
        active = db.execute(
            update(OrganizationKey)
            .where(OrganizationKey.id == key.id, OrganizationKey.revoked.is_(False))
            .values(calls=OrganizationKey.calls + 1)
        )
        if not active.rowcount:
            raise HTTPException(401, "API key revoked")
    job = enqueue(
        db,
        key.organization_id,
        "score",
        payload.identity.model_dump(mode="json"),
        payload.idempotency_key,
    )
    audit(db, key.organization_id, None, "customer_score_queued", job.id)
    db.commit()
    return {"job_id": job.id, "state": job.state, "api_version": "v1"}


@router.get("/reports")
def reports(
    request: Request,
    after: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    key = key_context(request, db, "reports:read")
    rows = list(
        db.scalars(
            select(OrganizationResource)
            .where(
                OrganizationResource.organization_id == key.organization_id,
                OrganizationResource.kind == "report",
                OrganizationResource.id > after,
            )
            .order_by(OrganizationResource.id)
            .limit(limit)
        )
    )
    return {
        "items": [{"id": r.id, "report": r.payload} for r in rows],
        "next_cursor": rows[-1].id if len(rows) == limit else None,
        "api_version": "v1",
    }


@router.get("/jobs/{job_id}")
def job_status(job_id: int, request: Request, db: Session = Depends(get_db)):
    from models.organizations import WorkJob

    key = key_context(request, db, "score:read")
    row = db.scalar(
        select(WorkJob).where(
            WorkJob.id == job_id, WorkJob.organization_id == key.organization_id
        )
    )
    if not row:
        raise HTTPException(404, "Job not found")
    return {
        "id": row.id,
        "state": row.state,
        "error_code": row.error_code,
        "report_id": row.result_id,
        "api_version": "v1",
    }

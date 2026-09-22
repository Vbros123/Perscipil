"""Scheduled workspace reevaluation shares the durable scoring queue."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from core.database import SessionLocal
from core.tenancy import locked_organization
from models.organizations import Monitor, WorkJob, OrganizationResource, Delivery
from services.jobs import enqueue, digest
from services.monitoring import changes


def tick(limit=100):
    now = datetime.now(timezone.utc)
    scheduled = 0
    with SessionLocal() as db:
        ids = list(
            db.scalars(
                select(Monitor.id)
                .where(Monitor.active.is_(True))
                .order_by(Monitor.next_run)
                .limit(limit)
            )
        )
    for mid in ids:
        with SessionLocal() as db:
            monitor = db.get(Monitor, mid)
            if not monitor:
                continue
            locked_organization(db, monitor.organization_id)
            db.refresh(monitor)
            if not monitor.active:
                continue
            previous_job = (
                db.get(WorkJob, monitor.last_job_id) if monitor.last_job_id else None
            )
            if previous_job and previous_job.state in ("queued", "running", "retry"):
                continue
            if (
                previous_job
                and previous_job.state == "complete"
                and previous_job.result_id
            ):
                report = db.get(OrganizationResource, previous_job.result_id)
                current = {
                    k: report.payload.get(k)
                    for k in ("private_score", "scoring_status", "risk_flags")
                }
                reasons = changes(monitor.previous, current)
                event_key = "monitor:" + str(mid) + ":job:" + str(previous_job.id)
                existing = db.scalar(
                    select(OrganizationResource.id).where(
                        OrganizationResource.organization_id == monitor.organization_id,
                        OrganizationResource.kind == "monitor_event",
                        OrganizationResource.dedupe_key == event_key,
                    )
                )
                if reasons and not existing:
                    event = OrganizationResource(
                        organization_id=monitor.organization_id,
                        kind="monitor_event",
                        dedupe_key=event_key,
                        payload={
                            "monitor_id": mid,
                            "report_id": report.id,
                            "reasons": reasons,
                            "previous": monitor.previous,
                            "current": current,
                        },
                    )
                    db.add(event)
                    db.flush()
                    from services.notifications import enqueue_configured

                    enqueue_configured(db, event)
                    db.add(
                        Delivery(
                            organization_id=monitor.organization_id,
                            event_id=event.id,
                            channel="in_app",
                            destination="workspace",
                            state="delivered",
                            delivered_at=now,
                        )
                    )
                monitor.previous = current
                monitor.last_job_id = None
            elif previous_job:
                # Leave failed job visible; reschedule only at the next weekly interval.
                monitor.last_job_id = None
            due = (
                monitor.next_run.replace(tzinfo=timezone.utc)
                if monitor.next_run.tzinfo is None
                else monitor.next_run
            )
            if due <= now:
                job = enqueue(
                    db,
                    monitor.organization_id,
                    "score",
                    monitor.identity,
                    "monitor:" + str(mid) + ":" + digest(due.isoformat())[:32],
                )
                monitor.last_job_id = job.id
                monitor.next_run = now + timedelta(days=7)
                scheduled += 1
            db.commit()
    return scheduled

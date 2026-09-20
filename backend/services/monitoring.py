"""Scheduled reevaluation; timestamps alone are never a material change."""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from core.database import SessionLocal
from models.workflows import Subscription, MonitorEvent
from services.evidence import CompanyIdentity
from services.reports import score_company
from services.licensed_data import enabled
from services.permissions import allowed_providers, permission
from core.limiter import rate_limiter

def changes(previous, current):
    if previous is None:return []
    result=[]
    old,new=previous.get('private_score'),current.get('private_score')
    if old is not None and new is not None and abs(new-old)>=50:result.append('SCORE_CHANGE_50')
    if previous.get('scoring_status')!=current.get('scoring_status'):result.append('EVIDENCE_STATUS_CHANGED')
    if set(previous.get('risk_flags',[]))!=set(current.get('risk_flags',[])):result.append('RESEARCH_FLAGS_CHANGED')
    return result

async def run_due(limit=20):
    processed=0
    with SessionLocal() as db:
        ids=list(db.scalars(select(Subscription.id).where(Subscription.next_run<=datetime.now(timezone.utc)).limit(limit)))
    for sub_id in ids:
        with SessionLocal() as db:
            row=db.get(Subscription,sub_id)
            if not row:continue
            now=datetime.now(timezone.utc); lease=now+timedelta(minutes=5)
            claim=db.execute(update(Subscription).where(Subscription.id==sub_id,Subscription.next_run<=now).values(next_run=lease))
            db.commit()
            if not claim.rowcount:continue
            allowed,_=await rate_limiter.is_allowed(f'workflow:{row.user_id}')
            if not allowed:continue
            if enabled() and any(not permission(p).may_use_for_monitoring for p in allowed_providers()):continue
            try:
                identity=CompanyIdentity(**row.identity)
                current=await asyncio.wait_for(score_company(identity.legal_name,identity=identity,refresh=True),90)
                reasons=changes(row.previous,current)
                # Store only fields used for change rules; source snapshots live in reports.
                snapshot={k:current.get(k) for k in ('private_score','scoring_status','risk_flags','meta')}
                update_result=db.execute(update(Subscription).where(Subscription.id==sub_id,Subscription.next_run==lease).values(previous=snapshot,next_run=now+timedelta(days=7)))
                if update_result.rowcount and reasons:
                    db.add(MonitorEvent(user_id=row.user_id,subscription_id=sub_id,payload={'reasons':reasons,'previous':row.previous,'current':snapshot}))
                db.commit();processed+=1
            except Exception:
                db.rollback()  # Lease permits retry; no fabricated event on provider failure.
    return processed

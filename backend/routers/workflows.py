"""Account-owned pilot features; customer API keys never authenticate web routes."""
import asyncio
import csv
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_user, hash_security_token, verify_password
from core.limiter import rate_limiter
from models.user import User, AuthAuditEvent
from models.company import CompanyReport
from models.workflows import Batch, BatchItem, Correction, ApiKey, Subscription, MonitorEvent, PolicyAcceptance, PilotReview
from services.evidence import CompanyIdentity
from services.reports import score_company
from services.history import store_company_event

router = APIRouter(prefix='/api', tags=['Pilot workflows'])

def owned(db, model, item_id, user):
    row = db.scalar(select(model).where(model.id == item_id, model.user_id == user.id))
    if row is None:
        raise HTTPException(404, 'Not found')
    return row

async def quota(user, cost=1):
    allowed, retry = await rate_limiter.is_allowed(f'workflow:{user.id}', cost=cost)
    if not allowed:
        raise HTTPException(429, 'Quota exceeded', headers={'Retry-After': str(retry)})

class CsvInput(BaseModel):
    csv_text: str = Field(min_length=1, max_length=262144)
    name_column: str = Field(default='company', max_length=80)
    country_column: str = Field(default='country_code', max_length=80)

@router.post('/batches', status_code=201)
async def create_batch(payload: CsvInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    await quota(user)
    if len(payload.csv_text.encode('utf-8')) > 262144 or '\0' in payload.csv_text:
        raise HTTPException(422, 'CSV exceeds 256 KiB or contains NUL bytes')
    try:
        reader = csv.DictReader(io.StringIO(payload.csv_text.lstrip('\ufeff')), strict=True)
        if not reader.fieldnames or payload.name_column not in reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Choose a unique company-name column')
        identities, seen = [], set()
        for index, row in enumerate(reader):
            if index >= 100:
                raise ValueError('Maximum 100 input rows')
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Malformed CSV row')
            identity = CompanyIdentity(legal_name=row[payload.name_column], country_code=row.get(payload.country_column) or 'US',
                                       registration_number=row.get('registration_number') or None, postal_code=row.get('postal_code') or None)
            key = identity.cache_key()
            if key not in seen:
                identities.append(identity.model_dump(mode='json'))
                seen.add(key)
        if not identities:
            raise ValueError('CSV contains no companies')
    except (ValueError, csv.Error) as exc:
        raise HTTPException(422, str(exc)[:240]) from exc
    # Lock the account while enforcing durable backlog limits across concurrent uploads.
    db.execute(select(User).where(User.id == user.id).with_for_update())
    pending = db.scalar(select(BatchItem.id).join(Batch).where(Batch.user_id == user.id, BatchItem.status.in_(['queued', 'running'])).limit(1))
    if pending is not None:
        raise HTTPException(409, 'Finish the active batch before uploading another')
    batch = Batch(user_id=user.id)
    db.add(batch); db.flush()
    db.add_all([BatchItem(batch_id=batch.id, position=i, identity=v) for i,v in enumerate(identities)])
    db.commit()
    return {'id': batch.id, 'rows': len(identities), 'duplicates_removed': index + 1 - len(identities)}

@router.get('/batches')
def batches(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{'id': b.id, 'created_at': b.created_at} for b in db.scalars(select(Batch).where(Batch.user_id == user.id).order_by(Batch.id.desc()).limit(100))]

@router.get('/batches/{batch_id}')
def batch_status(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, Batch, batch_id, user)
    rows = list(db.scalars(select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.position)))
    return {'id': batch_id, 'total': len(rows), 'completed': sum(r.status in {'complete','failed','needs_review'} for r in rows),
            'rows': [{'id': r.id, 'company': r.identity['legal_name'], 'status': r.status, 'attempts': r.attempts, 'error': r.error,
                      'score': (r.result or {}).get('private_score')} for r in rows]}

@router.post('/batches/{batch_id}/step')
async def batch_step(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, Batch, batch_id, user)
    await quota(user)
    now = datetime.now(timezone.utc)
    # Recover jobs interrupted by process loss. Claim token (attempt count) fences stale completions.
    db.execute(update(BatchItem).where(BatchItem.batch_id == batch_id, BatchItem.status == 'running', BatchItem.started_at < now - timedelta(minutes=5)).values(status='queued'))
    db.execute(select(User).where(User.id == user.id).with_for_update())
    db.execute(update(BatchItem).where(BatchItem.batch_id == batch_id, BatchItem.status == 'queued', BatchItem.attempts >= 3).values(status='failed', error='Retry limit reached'))
    if db.scalar(select(BatchItem.id).where(BatchItem.batch_id == batch_id, BatchItem.status == 'running').limit(1)):
        db.commit()
        raise HTTPException(409, 'A company is already processing; retry shortly')
    candidate = db.scalar(select(BatchItem).where(BatchItem.batch_id == batch_id, BatchItem.status == 'queued').order_by(BatchItem.position).limit(1))
    if candidate is None:
        db.commit()
        return batch_status(batch_id, user, db)
    claimed = db.execute(update(BatchItem).where(BatchItem.id == candidate.id, BatchItem.status == 'queued').values(status='running', attempts=BatchItem.attempts+1, started_at=now))
    db.commit()
    if not claimed.rowcount:
        return batch_status(batch_id, user, db)
    db.refresh(candidate)
    attempt = candidate.attempts
    try:
        identity = CompanyIdentity(**candidate.identity)
        result = await asyncio.wait_for(score_company(identity.legal_name, identity=identity), timeout=90)
        status = 'needs_review' if result.get('scoring_status') == 'needs_disambiguation' else 'complete'
        error = None
    except Exception:
        result, status, error = None, 'failed', 'Collection failed; retry available (maximum three attempts).'
    completed = db.execute(update(BatchItem).where(BatchItem.id == candidate.id, BatchItem.status == 'running', BatchItem.attempts == attempt).values(result=result, status=status, error=error))
    db.commit()
    if completed.rowcount and result and status == 'complete':
        store_company_event(db, user, result, query_type='batch')
    return batch_status(batch_id, user, db)

@router.post('/batches/{batch_id}/retry')
def retry_batch(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, Batch, batch_id, user)
    db.execute(update(BatchItem).where(BatchItem.batch_id == batch_id, BatchItem.status == 'failed', BatchItem.attempts < 3).values(status='queued', error=None))
    db.commit()
    return batch_status(batch_id, user, db)

def csv_safe(value):
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value

@router.get('/batches/{batch_id}/export', response_class=PlainTextResponse)
def export_batch(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, Batch, batch_id, user)
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['company','status','research_score','coverage','confidence','model_version','snapshot_hash','error'])
    for row in db.scalars(select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.position)):
        result = row.result or {}; meta = result.get('meta', {})
        writer.writerow([csv_safe(v) for v in [row.identity['legal_name'],row.status,result.get('private_score'),meta.get('evidence_coverage'),meta.get('confidence'),meta.get('model_version'),meta.get('input_snapshot_hash'),row.error]])
    return PlainTextResponse(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="batch-{batch_id}.csv"'})

class CorrectionInput(BaseModel):
    report_id: int
    reason: Literal['wrong_entity','incorrect_address','incorrect_information','wrong_legal_event','stale_evidence','incorrect_source','other']
    details: str = Field(min_length=10, max_length=4000)

@router.post('/corrections', status_code=201)
def correction(payload: CorrectionInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned(db, CompanyReport, payload.report_id, user)
    row = Correction(user_id=user.id, snapshot_hash=report.input_snapshot_hash, **payload.model_dump())
    db.add(row); db.commit()
    return {'id': row.id, 'status': row.status}

@router.get('/corrections')
def corrections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{'id': r.id, 'report_id': r.report_id, 'reason': r.reason, 'status': r.status, 'review_history': r.review_history} for r in db.scalars(select(Correction).where(Correction.user_id == user.id).limit(100))]

class KeyInput(BaseModel):
    label: str = Field(min_length=1,max_length=80)

@router.post('/keys', status_code=201)
def create_key(payload: KeyInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(list(db.scalars(select(ApiKey.id).where(ApiKey.user_id == user.id, ApiKey.revoked == 0)))) >= 5:
        raise HTTPException(409, 'Maximum five active keys')
    secret = 'pl_' + secrets.token_urlsafe(32)
    key = ApiKey(user_id=user.id, label=payload.label, key_hash=hash_security_token(secret))
    db.add(key); db.add(AuthAuditEvent(user_id=user.id,event_type='api_key_created')); db.commit()
    return {'id': key.id, 'key': secret, 'scopes': ['score:read'], 'lifetime_quota': 1000}

@router.get('/keys')
def keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{'id': k.id,'label': k.label,'revoked': bool(k.revoked),'calls': k.calls,'scopes':['score:read']} for k in db.scalars(select(ApiKey).where(ApiKey.user_id == user.id))]

@router.delete('/keys/{key_id}')
def revoke_key(key_id:int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    key=owned(db, ApiKey,key_id,user);key.revoked=1
    db.add(AuthAuditEvent(user_id=user.id,event_type='api_key_revoked'));db.commit()
    return {'revoked':True}

@router.post('/v1/score')
async def customer_score(identity: CompanyIdentity, request: Request, db: Session = Depends(get_db)):
    token = request.headers.get('x-api-key','')
    if len(token)>200:
        raise HTTPException(401,'Invalid API key')
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash==hash_security_token(token),ApiKey.revoked==0))
    user = db.get(User,key.user_id) if key else None
    if not user or not user.is_active:
        raise HTTPException(401,'Invalid API key')
    await quota(user)
    changed = db.execute(update(ApiKey).where(ApiKey.id==key.id,ApiKey.revoked==0,ApiKey.calls<1000).values(calls=ApiKey.calls+1))
    db.commit()
    if not changed.rowcount:
        raise HTTPException(429,'Pilot key lifetime quota exhausted')
    # Public-only customer API until explicit redistribution permission enforcement is implemented.
    from services.licensed_data import enabled
    if enabled():
        raise HTTPException(403,'Licensed report redistribution is not enabled for customer API')
    return await score_company(identity.legal_name,identity=identity)

@router.post('/monitoring', status_code=201)
def subscribe(identity: CompanyIdentity,user: User = Depends(get_current_user),db: Session=Depends(get_db)):
    if len(list(db.scalars(select(Subscription.id).where(Subscription.user_id==user.id))))>=20:
        raise HTTPException(409,'Pilot limit: 20 subscriptions')
    row=Subscription(user_id=user.id,identity=identity.model_dump(mode='json'));db.add(row);db.commit()
    return {'id':row.id,'status':'scheduled_requires_worker'}

@router.get('/monitoring/events')
def events(user: User = Depends(get_current_user),db: Session=Depends(get_db)):
    return [{'id':r.id,'created_at':r.created_at,'payload':r.payload} for r in db.scalars(select(MonitorEvent).where(MonitorEvent.user_id==user.id).order_by(MonitorEvent.id.desc()).limit(100))]

@router.delete('/monitoring/{subscription_id}')
def unsubscribe(subscription_id:int,user: User = Depends(get_current_user),db: Session=Depends(get_db)):
    db.delete(owned(db,Subscription,subscription_id,user));db.commit();return {'deleted':True}

class Acceptance(BaseModel):
    terms_version: str = Field(max_length=40)
    privacy_version: str = Field(max_length=40)

@router.post('/policies/accept')
def accept_policy(payload:Acceptance,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from core.config import get_settings
    settings=get_settings()
    if not settings.POLICIES_PUBLISHED or payload.terms_version!=settings.TERMS_VERSION or payload.privacy_version!=settings.PRIVACY_VERSION:
        raise HTTPException(409,'Published policy versions do not match; draft policies cannot be accepted')
    db.add(PolicyAcceptance(user_id=user.id,**payload.model_dump()));db.commit();return {'accepted':True}

class Review(BaseModel):
    report_id:int
    usefulness:int=Field(ge=1,le=5)
    escalated:bool
    manual_minutes:float=Field(ge=0,le=100000)
    review_minutes:float=Field(ge=0,le=100000)
    outcome:str|None=Field(default=None,max_length=500)

@router.post('/pilot/reviews')
def review(payload:Review,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    owned(db,CompanyReport,payload.report_id,user)
    row=db.scalar(select(PilotReview).where(PilotReview.user_id==user.id,PilotReview.report_id==payload.report_id))
    if row is None:row=PilotReview(user_id=user.id,report_id=payload.report_id)
    row.measurements=payload.model_dump(exclude={'report_id'});db.add(row);db.commit();return {'saved':True}

@router.get('/pilot/metrics')
def pilot_metrics(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    rows=list(db.scalars(select(PilotReview).where(PilotReview.user_id==user.id)))
    return {'reviewed_companies':len(rows),'self_reported_hours_avoided_per_100':sum(r.measurements['manual_minutes']-r.measurements['review_minutes'] for r in rows)/len(rows)*100/60 if rows else None,'note':'Self-reported paired estimates; not independently measured ROI.'}

class DeleteAccount(BaseModel):
    password:str=Field(min_length=1,max_length=128)
    confirmation:Literal['DELETE MY ACCOUNT']

@router.get('/users/me/export')
def export_account(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    def serialize(row):
        return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in {'password_hash','key_hash'}}
    from models.company import SavedCompany,CompanySearch
    from models.settings import UserSettings
    data={'profile':{'id':user.id,'email':user.email,'first_name':user.first_name,'last_name':user.last_name,'company':user.company}}
    for model in [SavedCompany,CompanySearch,CompanyReport,UserSettings,Batch,Correction,Subscription,MonitorEvent,PolicyAcceptance,PilotReview]:
        data[model.__tablename__]=[serialize(row) for row in db.scalars(select(model).where(model.user_id==user.id))]
    data['batch_items']=[serialize(row) for row in db.scalars(select(BatchItem).join(Batch).where(Batch.user_id==user.id))]
    return data

@router.delete('/users/me')
def delete_account(payload:DeleteAccount,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    if not verify_password(payload.password,user.password_hash):raise HTTPException(403,'Password incorrect')
    from sqlalchemy import delete
    # Retain de-identified control history; remove free-text dispute content on deletion.
    db.execute(update(AuthAuditEvent).where(AuthAuditEvent.user_id==user.id).values(email=None,ip_address=None,user_agent=None))
    db.execute(update(Correction).where(Correction.user_id==user.id).values(details='[removed on account deletion]',review_history=[]))
    db.delete(user);db.commit()
    return {'deleted':True,'retained':'De-identified security, acceptance, and correction control records'}

@router.get('/reports')
def reports(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [{'id':r.id,'company_name':r.company_name,'created_at':r.created_at} for r in db.scalars(select(CompanyReport).where(CompanyReport.user_id==user.id).order_by(CompanyReport.id.desc()).limit(100))]

@router.get('/monitoring')
def subscriptions(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return [{'id':r.id,'identity':r.identity,'next_run':r.next_run} for r in db.scalars(select(Subscription).where(Subscription.user_id==user.id))]

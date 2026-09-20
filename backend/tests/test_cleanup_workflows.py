import asyncio
import uuid
import pytest
from sqlalchemy import select
from core.database import SessionLocal
from core.config import get_settings
from core.security import create_access_token
from models.workflows import ApiKey, Batch, BatchItem, PolicyAcceptance
from models.user import User
from services.monitoring import changes
from services.permissions import permission, allowed_providers
from routers.workflows import csv_safe

@pytest.fixture(autouse=True)
def reset_limits():
    from core.limiter import auth_limiter, rate_limiter
    for limiter in [auth_limiter,rate_limiter]:
        if hasattr(limiter,'_requests'):limiter._requests.clear()

def register(api):
    response=api.post('/api/auth/signup',json={'email':f'{uuid.uuid4().hex}@example.com','password':'Password123!Secure'})
    assert response.status_code==201,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']},response.json()['user']['id']

async def fake_score(name,**kwargs):
    return {'company_name':name,'normalized_name':name.lower(),'private_score':None,'rating':'Unrated','color':'#64748B','scoring_status':'insufficient_data','report':{},'meta':{'model_version':'test','input_snapshot_hash':'a'*64},'risk_flags':[]}

def test_batch_ownership_dedup_progress_export_and_delete(api,monkeypatch):
    monkeypatch.setattr('routers.workflows.score_company',fake_score)
    h,uid=register(api);other,_=register(api)
    created=api.post('/api/batches',headers=h,json={'csv_text':'company,country_code\nAcme,US\nAcme,US\n=EVIL,US'})
    assert created.status_code==201,created.text
    bid=created.json()['id'];assert created.json()['rows']==2
    assert api.get(f'/api/batches/{bid}',headers=other).status_code==404
    assert api.post(f'/api/batches/{bid}/step',headers=other).status_code==404
    assert api.get(f'/api/batches/{bid}/export',headers=other).status_code==404
    assert api.post(f'/api/batches/{bid}/step',headers=h).json()['completed']==1
    assert api.post(f'/api/batches/{bid}/step',headers=h).json()['completed']==2
    assert "'=EVIL" in api.get(f'/api/batches/{bid}/export',headers=h).text
    export=api.get('/api/users/me/export',headers=h);assert len(export.json()['batch_items'])==2
    assert 'password_hash' not in export.text
    key=api.post('/api/keys',headers=h,json={'label':'test'}).json()['key']
    deleted=api.request('DELETE','/api/users/me',headers=h,json={'password':'Password123!Secure','confirmation':'DELETE MY ACCOUNT'})
    assert deleted.status_code==200,deleted.text
    assert api.get('/api/auth/me',headers=h).status_code==401
    assert api.post('/api/v1/score',headers={'x-api-key':key},json={'legal_name':'Acme'}).status_code==401
    with SessionLocal() as db:
        assert db.get(User,uid) is None
        assert db.get(Batch,bid) is None
        assert db.scalar(select(BatchItem).where(BatchItem.batch_id==bid)) is None

@pytest.mark.parametrize('text',['other\nAcme','company,country_code\nAcme,XX','company,company\nAcme,Acme','company\n'+ 'Acme\n'*101,'company\n"unterminated'])
def test_csv_rejects_bad_data(api,text):
    h,_=register(api)
    assert api.post('/api/batches',headers=h,json={'csv_text':text}).status_code==422

def test_key_scope_revocation_and_quota(api,monkeypatch):
    monkeypatch.setattr('routers.workflows.score_company',fake_score)
    h,_=register(api);other,_=register(api)
    created=api.post('/api/keys',headers=h,json={'label':'integration'}).json()
    secret=created['key'];kid=created['id']
    assert secret not in api.get('/api/keys',headers=h).text
    assert api.get('/api/auth/me',headers={'Authorization':f'Bearer {secret}'}).status_code==401
    assert api.delete(f'/api/keys/{kid}',headers=other).status_code==404
    assert api.post('/api/v1/score',headers={'x-api-key':secret},json={'legal_name':'Acme'}).status_code==200
    with SessionLocal.begin() as db:db.get(ApiKey,kid).calls=1000
    assert api.post('/api/v1/score',headers={'x-api-key':secret},json={'legal_name':'Acme'}).status_code==429
    assert api.delete(f'/api/keys/{kid}',headers=h).status_code==200
    assert api.post('/api/v1/score',headers={'x-api-key':secret},json={'legal_name':'Acme'}).status_code==401

def test_cookie_csrf_and_logout(api,monkeypatch):
    settings=get_settings();monkeypatch.setattr(settings,'COOKIE_AUTH',True)
    monkeypatch.setattr(settings,'ALLOWED_ORIGINS','http://localhost:5173')
    h,_=register(api)
    assert 'httponly' in api.cookies.get(settings.SESSION_COOKIE_NAME,'').lower() or api.cookies.get(settings.SESSION_COOKIE_NAME)
    assert api.get('/api/auth/me').status_code==200
    assert api.post('/api/auth/logout',headers={'Origin':'https://evil.example'}).status_code==403
    assert api.post('/api/auth/logout').status_code==403
    assert api.post('/api/auth/logout',headers={'Origin':'http://localhost:5173'}).status_code==200
    assert api.get('/api/auth/me',headers=h).status_code==401

def test_production_diagnostics_health_and_request_id(api,monkeypatch):
    settings=get_settings();monkeypatch.setattr(settings,'ENVIRONMENT','production')
    for path in ['/api/cache/stats','/api/providers','/api/compliance/status']:
        assert api.get(path).status_code==404
    response=api.get('/api/health',headers={'X-Request-ID':'attacker'})
    assert response.json()=={'status':'ok'}
    assert response.headers['x-request-id']!='attacker'

def test_dispute_and_policy_ownership(api,monkeypatch):
    from models.company import CompanyReport
    h,uid=register(api);other,_=register(api)
    with SessionLocal.begin() as db:
        r=CompanyReport(user_id=uid,company_name='Acme',normalized_name='acme',rating='Unrated',report_json={});db.add(r);db.flush();rid=r.id
    payload={'report_id':rid,'reason':'wrong_entity','details':'This is another business.'}
    assert api.post('/api/corrections',headers=other,json=payload).status_code==404
    assert api.post('/api/corrections',headers=h,json=payload).status_code==201
    assert api.get('/api/corrections',headers=other).json()==[]
    assert api.post('/api/policies/accept',headers=h,json={'terms_version':'old','privacy_version':'old'}).status_code==409
    settings=get_settings();monkeypatch.setattr(settings,'POLICIES_PUBLISHED',True)
    assert api.post('/api/policies/accept',headers=h,json={'terms_version':settings.TERMS_VERSION,'privacy_version':settings.PRIVACY_VERSION}).status_code==200
    with SessionLocal() as db:assert db.scalar(select(PolicyAcceptance).where(PolicyAcceptance.user_id==uid))

def test_permission_fail_closed(monkeypatch):
    settings=get_settings();monkeypatch.setattr(settings,'PROVIDER_PERMISSIONS_JSON','{}')
    assert not permission('creditsafe').may_score
    assert allowed_providers()==[]
    monkeypatch.setattr(settings,'PROVIDER_PERMISSIONS_JSON','invalid');assert allowed_providers()==[]

def test_monitoring_diff_and_csv_injection():
    a={'private_score':400,'scoring_status':'limited','risk_flags':[],'meta':{'computed_at':'old'}}
    assert changes(a,{**a,'meta':{'computed_at':'new'}})==[]
    assert changes(a,{**a,'private_score':451})==['SCORE_CHANGE_50']
    assert changes(None,a)==[]
    for value in ['=1','+1','-1','@SUM(A1)','  =1']:
        assert csv_safe(value).startswith("'")

def test_shared_limiter_atomic(api):
    from core.limiter import DatabaseLimiter
    a=DatabaseLimiter(2,60,'test'+uuid.uuid4().hex)
    b=DatabaseLimiter(2,60,a.namespace)
    assert asyncio.run(a.is_allowed('client'))[0]
    assert asyncio.run(b.is_allowed('client'))[0]
    assert not asyncio.run(a.is_allowed('client'))[0]

def test_body_limit_and_anonymous_history(api):
    assert api.post('/api/batches',content=b'x'*(1048576+1)).status_code==413
    from services.history import history_store
    history_store.add('Private anonymous query',None,'Unrated','#64748B')
    assert api.get('/api/history').json()=={'history':[]}

def test_batch_failure_retry_ceiling(api,monkeypatch):
    async def fail(*a,**k):raise RuntimeError('secret upstream payload')
    monkeypatch.setattr('routers.workflows.score_company',fail)
    h,_=register(api)
    bid=api.post('/api/batches',headers=h,json={'csv_text':'company\nAcme'}).json()['id']
    for attempt in range(3):
        response=api.post(f'/api/batches/{bid}/step',headers=h)
        assert response.status_code==200,response.text
        assert response.json()['rows'][0]['status']=='failed'
        assert 'secret upstream payload' not in response.text
        api.post(f'/api/batches/{bid}/retry',headers=h)
    row=api.get(f'/api/batches/{bid}',headers=h).json()['rows'][0]
    assert row['status']=='failed' and row['attempts']==3

def test_validation_rejects_temporal_leakage_and_reused_entities():
    from scripts.validate_dated_cohort import check
    from datetime import datetime,timezone
    row={'company_id':'a','distress_probability':0.2,'distress_within_12m':0,'evidence_coverage':0.8,'feature_at':'2024-01-01T00:00:00+00:00','outcome_end':'2025-02-01T00:00:00+00:00','split':'train'}
    result=check([row],datetime(2025,1,1,tzinfo=timezone.utc))
    assert not result['eligible_for_metric_evaluation']
    assert any('cutoff' in e['error'] for e in result['errors'])

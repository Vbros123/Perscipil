from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from core.database import SessionLocal
from core.mfa import consume
from core.security import hash_security_token
from models.mfa import MfaCredential
from models.organizations import OrganizationResource, Membership
from models.consent import ProviderConsent
from services.consent import active_consent
from tests.test_organizations import account, org


def test_concurrent_recovery_code_only_once(api):
    _, uid = account(api)
    with SessionLocal.begin() as db:
        db.add(MfaCredential(user_id=uid, encrypted_secret='fixture', enabled=True,
            recovery_hashes=[hash_security_token('fixture-recovery')], expires_at=datetime.now(timezone.utc)))
    def attempt(_):
        with SessionLocal.begin() as db:
            return consume(db, uid, 'fixture-recovery')
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 1


def test_consent_duration_cannot_be_used_as_permission(api):
    h,_=account(api); oid=org(api,h)
    with SessionLocal.begin() as db:
        row=ProviderConsent(organization_id=oid,subject_id='fixture',provider='fixture',connection_id='fixture',state='active',permissions={'retention_days':20},expires_at=datetime.now(timezone.utc)+timedelta(days=1))
        db.add(row);db.flush()
        with pytest.raises(HTTPException) as exc:
            active_consent(db,oid,row.id,'retention_days')
        assert exc.value.status_code==403


def test_correction_review_is_tenant_bound_and_final(api):
    h,uid=account(api); outsider,_=account(api); oid=org(api,h)
    with SessionLocal.begin() as db:
        report=OrganizationResource(organization_id=oid,kind='report',dedupe_key='review-fixture',payload={})
        db.add(report);db.flush();rid=report.id
    root=f'/api/organizations/{oid}'
    cid=api.post(root+'/corrections',headers=h,json={'report_id':rid,'reason':'Fixture source correction'}).json()['id']
    payload={'status':'accepted','note':'Reviewed evidence in fixture'}
    assert api.patch(root+f'/corrections/{cid}',headers=outsider,json=payload).status_code==404
    assert api.patch(root+f'/corrections/{cid}',headers=h,json=payload).status_code==200
    assert api.patch(root+f'/corrections/{cid}',headers=h,json=payload).status_code==409


def test_ownership_transfer_requires_password(api):
    h,uid=account(api); other,other_id=account(api);oid=org(api,h)
    with SessionLocal.begin() as db:
        db.add(Membership(organization_id=oid,user_id=other_id,role='member'))
    path=f'/api/organizations/{oid}/ownership'
    assert api.post(path,headers=h,json={'user_id':other_id,'password':'incorrect'}).status_code==403
    assert api.post(path,headers=h,json={'user_id':other_id,'password':'Password123!Secure'}).status_code==200


def test_deletion_replay_removes_restored_user_and_is_idempotent(api):
    from models.user import User
    from services.deletions import identity_key, replay
    _,uid=account(api)
    with SessionLocal.begin() as db:
        key=identity_key(db.get(User,uid))
        assert replay(db,{key})==1
    with SessionLocal.begin() as db:
        assert db.get(User,uid) is None
        assert replay(db,{key})==0


def test_provider_capacity_released_after_failure(api,monkeypatch):
    import asyncio, httpx
    from core.config import get_settings
    from core.provider_budget import ProviderClient
    monkeypatch.setattr(get_settings(),'PROVIDER_BUDGETS_ENABLED',True)
    async def run():
        active=0;peak=0
        async def handler(request):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.05)
            active-=1
            raise httpx.ConnectError('fixture',request=request)
        async with ProviderClient(transport=httpx.MockTransport(handler)) as client:
            result=await asyncio.gather(*(client.get('https://capacity-fixture.example') for _ in range(8)),return_exceptions=True)
            assert peak<=2
            assert all(isinstance(r,(httpx.ConnectError,httpx.HTTPStatusError)) for r in result)
            with pytest.raises(httpx.ConnectError):await client.get('https://capacity-fixture.example')
    asyncio.run(run())

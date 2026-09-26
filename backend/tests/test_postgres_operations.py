"""Real PostgreSQL integration tests, isolated by the CI database service."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select, update
from core.database import engine, SessionLocal
from core.limiter import DatabaseLimiter
from models.organizations import Organization, WorkJob
from services.jobs import enqueue, claim, finish

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires isolated PostgreSQL')


def test_concurrent_enqueue_claim_and_fenced_completion(api):
    with SessionLocal.begin() as db:
        org = Organization(name='Concurrent fixture')
        db.add(org)
        db.flush()
        oid = org.id
    def submit(_):
        with SessionLocal.begin() as db:
            return enqueue(db, oid, 'score', {'legal_name':'Fixture'}, 'concurrent-fixture').id
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(submit, range(24)))
        claims = list(pool.map(lambda _: claim(oid), range(16)))
    assert len(set(ids)) == 1
    active = [c for c in claims if c]
    assert len(active) == 1
    first = active[0]
    with SessionLocal.begin() as db:
        db.execute(update(WorkJob).where(WorkJob.id == first['id']).values(lease_until=datetime.now(timezone.utc)-timedelta(seconds=1)))
    second = claim(oid)
    assert second and second['token'] != first['token']
    assert not finish(first, result={'private_score':123})
    assert finish(second, result={'private_score':None, 'scoring_status':'insufficient_data'})
    assert not finish(second, result={'private_score':123})


def test_concurrent_budget_never_exceeds_limit(api):
    limiter = DatabaseLimiter(10, 3600, 'pg-fixture')
    identifier = uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(lambda _: limiter.check(identifier)[0], range(50)))
    assert sum(outcomes) == 10


def test_thousand_completed_jobs_across_workspaces(api):
    from sqlalchemy import func
    from services.jobs import run_cycle
    with SessionLocal.begin() as db:
        orgs=[Organization(name=f'Load fixture {i}') for i in range(20)]
        db.add_all(orgs);db.flush();oids=[o.id for o in orgs]
        for i in range(1000):
            enqueue(db,oids[i%20],'score',{'legal_name':f'Fixture {i}'},f'load-fixture-{i}')
    async def scorer(name,**kwargs):
        return {'company_name':name,'private_score':None,'scoring_status':'insufficient_data'}
    async def drain():
        for _ in range(80):
            await run_cycle(concurrency=4,scorer=scorer)
            with SessionLocal() as db:
                remaining=db.scalar(select(func.count()).select_from(WorkJob).where(WorkJob.organization_id.in_(oids),WorkJob.state!='complete'))
            if not remaining:return
        raise AssertionError('Fixture queue did not drain within bounded cycles')
    asyncio.run(drain())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WorkJob).where(WorkJob.organization_id.in_(oids),WorkJob.state=='complete'))==1000
        assert all(db.scalars(select(WorkJob.result_id).where(WorkJob.organization_id.in_(oids))))

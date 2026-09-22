import asyncio
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from fastapi import HTTPException
import pytest
from sqlalchemy import select
from core.database import SessionLocal
from core.config import get_settings
from models.organizations import Delivery, OrganizationResource, WorkJob, Monitor
from models.consent import ProviderConsent
from services.jobs import run_cycle
from services.workspace_monitoring import tick
from services.notifications import (
    signature,
    verify_signature,
    deliver_due,
    TestDeliveryProvider as FixtureDelivery,
)
from services.consent import put, get, revoke, limited_view
from tests.test_organizations import account, org


async def scorer(name, **kwargs):
    return {
        "company_name": name,
        "private_score": 500,
        "scoring_status": "scored",
        "risk_flags": [],
    }


def test_customer_api_scopes_and_cross_tenant(api):
    a, _ = account(api)
    b, _ = account(api)
    oa = org(api, a)
    ob = org(api, b)

    def key(o, h, scopes):
        return api.post(
            f"/api/organizations/{o}/keys",
            headers=h,
            json={"label": "test", "scopes": scopes},
        ).json()

    ka = key(oa, a, ["score:read", "reports:read"])
    kb = key(ob, b, ["score:read"])
    ha = {"x-api-key": ka["key"]}
    hb = {"x-api-key": kb["key"]}
    job = api.post(
        "/api/v1/workspace/scores",
        headers=ha,
        json={"identity": {"legal_name": "Acme"}, "idempotency_key": "api-score-test"},
    ).json()["job_id"]
    assert api.get(f"/api/v1/workspace/jobs/{job}", headers=hb).status_code == 404
    assert api.get("/api/v1/workspace/reports", headers=hb).status_code == 403
    asyncio.run(run_cycle(scorer=scorer))
    assert len(api.get("/api/v1/workspace/reports", headers=ha).json()["items"]) == 1
    api.delete(f"/api/organizations/{oa}/keys/{ka['id']}", headers=a)
    assert api.get("/api/v1/workspace/reports", headers=ha).status_code == 401


def test_monitor_events_and_deliveries(api):
    h, _ = account(api)
    oid = org(api, h)
    mid = api.post(
        f"/api/organizations/{oid}/monitoring", headers=h, json={"legal_name": "Acme"}
    ).json()["id"]
    tick()
    asyncio.run(run_cycle(scorer=scorer))
    tick()
    with SessionLocal() as db:
        m = db.get(Monitor, mid)
        m.next_run = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    async def changed(name, **kwargs):
        return {
            "company_name": name,
            "private_score": 300,
            "scoring_status": "scored",
            "risk_flags": [],
        }

    tick()
    asyncio.run(run_cycle(scorer=changed))
    tick()
    tick()
    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(OrganizationResource).where(
                    OrganizationResource.organization_id == oid,
                    OrganizationResource.kind == "monitor_event",
                )
            )
        )
        assert len(events) == 1
        db.add(
            Delivery(
                organization_id=oid,
                event_id=events[0].id,
                channel="webhook",
                destination="fixture",
            )
        )
        db.commit()
    provider = FixtureDelivery()
    asyncio.run(deliver_due(provider=provider))
    asyncio.run(deliver_due(provider=provider))
    assert len(provider.events) == 1


def test_webhook_tampering_and_timestamp():
    sig = signature("x" * 32, "1000", "event-1", b"{}")
    assert verify_signature("x" * 32, "1000", "event-1", b"{}", sig, now=1001)
    assert not verify_signature("x" * 32, "1000", "event-1", b"changed", sig, now=1001)
    assert not verify_signature("x" * 32, "1000", "event-1", b"{}", sig, now=1400)


def test_consent_tenant_revocation_and_redaction(api, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    h, _ = account(api)
    a = org(api, h)
    b = org(api, h)
    with SessionLocal() as db:
        c = ProviderConsent(
            organization_id=a,
            subject_id="company-1",
            provider="codat",
            connection_id="connection-1",
            state="active",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            permissions={"can_retain": True, "can_score": True, "retention_days": 1},
        )
        db.add(c)
        db.commit()
        key = put(db, a, c.id, "Acme", {"cash": 10})
        db.commit()
        assert get(db, a, c.id, key) == {"cash": 10}
        with pytest.raises(HTTPException):
            get(db, b, c.id, key)
        revoke(db, a, c.id)
        db.commit()
        with pytest.raises(HTTPException):
            get(db, a, c.id, key)
    assert limited_view({"cash": 10}, {"score": 4}, {})["raw"] is None
    assert limited_view({}, {}, {}, via_api=True)["status"] == "withheld"


def test_thousand_row_fixture_queue_and_failure(api):
    h, _ = account(api)
    oid = org(api, h)
    csv = "company\n" + "\n".join("Fixture " + str(i) for i in range(1000))
    r = api.post(
        f"/api/organizations/{oid}/batches",
        headers=h,
        json={"csv_text": csv, "idempotency_key": "thousand-row-fixture"},
    )
    assert r.status_code == 202, r.text
    assert len(r.json()["job_ids"]) == 1000

    async def broken(name, **kwargs):
        raise TimeoutError()

    # Exercise one failure, then make it retryable immediately; no network calls.
    asyncio.run(run_cycle(scorer=broken))
    with SessionLocal() as db:
        failed = db.scalar(
            select(WorkJob).where(
                WorkJob.organization_id == oid, WorkJob.state == "retry"
            )
        )
        assert failed and failed.error_code == "PROVIDER_TIMEOUT"
        failed.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    asyncio.run(run_cycle(scorer=scorer))
    assert (
        len(
            api.get(
                f"/api/organizations/{oid}/resources?kind=report", headers=h
            ).json()["items"]
        )
        == 1
    )


def test_shared_provider_budget(api, monkeypatch):
    import httpx
    from core.provider_budget import before_request

    monkeypatch.setattr(get_settings(), "PROVIDER_BUDGETS_ENABLED", True)

    async def request_many():
        statuses = []
        for _ in range(3):
            try:
                await before_request(
                    httpx.Request("GET", "https://fixture-budget.example/path")
                )
                statuses.append("ok")
            except httpx.HTTPStatusError:
                statuses.append("blocked")
        return statuses

    import core.limiter

    monkeypatch.setattr(core.limiter.time, "time", lambda: 2000000000)
    assert asyncio.run(request_many()) == ["ok", "ok", "blocked"]

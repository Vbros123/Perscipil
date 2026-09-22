import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from core.database import SessionLocal
from models.user import User
from models.organizations import WorkJob, Membership, OrganizationResource
from services.jobs import claim, finish, run_cycle


def account(api):
    r = api.post(
        "/api/auth/signup",
        json={
            "email": f"{uuid.uuid4().hex}@example.com",
            "password": "Password123!Secure",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return {"Authorization": "Bearer " + data["access_token"]}, data["user"]["id"]


def org(api, h):
    r = api.post("/api/organizations", headers=h, json={"name": "Research team"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_tenant_boundaries_and_revocation(api):
    a, aid = account(api)
    b, bid = account(api)
    c, cid = account(api)
    oa = org(api, a)
    ob = org(api, b)
    path = f"/api/organizations/{oa}"
    saved = api.post(path + "/watchlist", headers=a, json={"legal_name": "Acme"})
    assert saved.status_code == 201, saved.text
    rid = saved.json()["id"]
    assert api.get(path + "/resources", headers=b).status_code == 404
    assert api.delete(path + f"/resources/{rid}", headers=b).status_code == 404
    assert (
        api.delete(f"/api/organizations/{ob}/resources/{rid}", headers=b).status_code
        == 404
    )
    with SessionLocal() as db:
        email = db.get(User, cid).email
        db.get(User, cid).email_verified = True
        db.commit()
    inv = api.post(path + "/invitations", headers=a, json={"email": email}).json()
    assert (
        api.post(
            "/api/organizations/invitations/accept",
            headers=b,
            json={"token": inv["invitation_token"]},
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/api/organizations/invitations/accept",
            headers=c,
            json={"token": inv["invitation_token"]},
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/api/organizations/invitations/accept",
            headers=c,
            json={"token": inv["invitation_token"]},
        ).status_code
        == 409
    )
    assert api.get(path + "/resources", headers=c).status_code == 200
    assert (
        api.post(path + "/keys", headers=c, json={"label": "forbidden"}).status_code
        == 403
    )
    assert api.delete(path + f"/members/{aid}", headers=c).status_code == 403
    assert api.delete(path + f"/members/{cid}", headers=a).status_code == 200
    assert api.get(path + "/resources", headers=c).status_code == 404


def test_queue_idempotency_and_fencing(api):
    h, uid = account(api)
    oid = org(api, h)
    path = f"/api/organizations/{oid}"
    payload = {"identity": {"legal_name": "Acme"}, "idempotency_key": "repeatable-test"}
    r = api.post(path + "/scores", headers=h, json=payload)
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    assert api.post(path + "/scores", headers=h, json=payload).json()["job_id"] == jid
    assert (
        api.post(
            path + "/scores",
            headers=h,
            json={**payload, "identity": {"legal_name": "Other"}},
        ).status_code
        == 409
    )
    first = claim(oid)
    assert first and claim(oid) is None
    with SessionLocal() as db:
        db.get(WorkJob, jid).lease_until = datetime.now(timezone.utc) - timedelta(
            seconds=1
        )
        db.commit()
    second = claim(oid)
    assert second and second["token"] != first["token"]
    assert not finish(first, result={"private_score": 100})
    assert finish(second, result={"private_score": 500})
    assert not finish(second, result={"private_score": 600})
    with SessionLocal() as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(OrganizationResource).where(
                            OrganizationResource.organization_id == oid,
                            OrganizationResource.kind == "report",
                        )
                    )
                )
            )
            == 1
        )
    assert (
        api.post(
            path + "/scores",
            headers=h,
            json={**payload, "idempotency_key": "cancel-this-job"},
        ).status_code
        == 202
    )
    running = claim(oid)
    assert (
        api.post(path + f"/jobs/{running['id']}/cancel", headers=h).status_code == 200
    )
    assert not finish(running, result={"private_score": 999})


def test_bulk_limits_dedup_and_export(api):
    h, _ = account(api)
    oid = org(api, h)
    path = f"/api/organizations/{oid}"
    p = {"csv_text": "company\nAcme\nAcme\n=FORMULA", "idempotency_key": "bulk-fixture"}
    r = api.post(path + "/batches", headers=h, json=p)
    assert r.status_code == 202, r.text
    assert len(r.json()["job_ids"]) == 2
    assert (
        api.post(
            path + "/batches", headers=h, json={**p, "csv_text": "company\nOther"}
        ).status_code
        == 409
    )
    assert "'=FORMULA" in api.get(path + "/batches/bulk-fixture/export", headers=h).text
    assert (
        api.post(
            path + "/batches",
            headers=h,
            json={
                "csv_text": "company\n" + "Name\n" * 1001,
                "idempotency_key": "too-many-rows",
            },
        ).status_code
        == 422
    )

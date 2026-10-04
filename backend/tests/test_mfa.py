import time
from cryptography.fernet import Fernet
from core.config import get_settings
from core.mfa import totp
from tests.test_organizations import account
from core.database import SessionLocal
from models.user import User


def test_rfc6238_vector():
    assert totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 1) == "287082"


def test_enrollment_login_replay_and_recovery(api, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "MFA_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )
    h, uid = account(api)
    proof = {"password": "Password123!Secure"}
    setup = api.post("/api/auth/mfa/enroll", headers=h, json=proof)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = totp(secret, int(time.time() // 30))
    confirmed = api.post(
        "/api/auth/mfa/confirm", headers=h, json={**proof, "code": code}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert api.get("/api/auth/me", headers=h).status_code == 401
    with SessionLocal() as db:
        email = db.get(User, uid).email
    login = {"email": email, **proof}
    assert api.post("/api/auth/login", json=login).status_code == 401
    assert (
        api.post("/api/auth/login", json={**login, "mfa_code": code}).status_code == 401
    )
    backup = confirmed.json()["recovery_codes"][0]
    valid = api.post("/api/auth/login", json={**login, "mfa_code": backup})
    assert valid.status_code == 200, valid.text
    assert (
        api.post("/api/auth/login", json={**login, "mfa_code": backup}).status_code
        == 401
    )
    assert (
        "secret"
        not in api.get(
            "/api/auth/mfa",
            headers={"Authorization": "Bearer " + valid.json()["access_token"]},
        ).text
    )

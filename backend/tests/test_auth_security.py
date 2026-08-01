import time

from conftest import strong_password


def test_signup_login_password_reset_and_email_verification(api):
    email = f"security-{int(time.time() * 1000)}@example.com"
    password = strong_password()

    signup = api.post("/api/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = api.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["email_verified"] is False

    wrong_current_password = api.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword!2026", "new_password": strong_password("Changed")},
    )
    assert wrong_current_password.status_code == 400
    assert api.get("/api/auth/me", headers=headers).status_code == 200

    verify_issue = api.post("/api/auth/request-email-verification", headers=headers)
    assert verify_issue.status_code == 200
    verification_token = verify_issue.json()["verification_token"]
    assert verification_token

    verified = api.post("/api/auth/verify-email", json={"token": verification_token})
    assert verified.status_code == 200

    reset_issue = api.post("/api/auth/request-password-reset", json={"email": email})
    assert reset_issue.status_code == 200
    reset_token = reset_issue.json()["reset_token"]
    assert reset_token

    new_password = strong_password("NewPassword")
    reset = api.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "new_password": new_password},
    )
    assert reset.status_code == 200

    old_login = api.post("/api/auth/login", json={"email": email, "password": password})
    assert old_login.status_code == 401

    new_login = api.post("/api/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


def test_failed_login_lockout(api):
    email = f"lockout-{int(time.time() * 1000)}@example.com"
    password = strong_password()

    signup = api.post("/api/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201

    for _ in range(5):
        failed = api.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        assert failed.status_code == 401

    locked = api.post("/api/auth/login", json={"email": email, "password": password})
    assert locked.status_code == 423

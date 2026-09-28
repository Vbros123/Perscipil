import base64, secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.brand import NAME
from core.database import get_db
from core.security import get_current_user, verify_password, hash_security_token
from core.mfa import cipher, consume
from core.limiter import rate_limiter
from models.mfa import MfaCredential
from models.user import User, AuthAuditEvent

router = APIRouter(prefix="/api/auth/mfa", tags=["MFA"])


class Proof(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(default="", max_length=80)


async def reauthenticate(db, user, password):
    allowed, retry = await rate_limiter.is_allowed(f"mfa:{user.id}")
    if not allowed:
        raise HTTPException(
            429, "Too many MFA attempts", headers={"Retry-After": str(retry)}
        )
    # Lock the account to serialize enrollment/disable and concurrent password checks.
    db.execute(select(User).where(User.id == user.id).with_for_update())
    if not verify_password(password, user.password_hash):
        raise HTTPException(403, "Password incorrect")


@router.get("")
def status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(MfaCredential, user.id)
    return {
        "enabled": bool(row and row.enabled),
        "recovery_codes_remaining": len(row.recovery_hashes)
        if row and row.enabled
        else 0,
    }


@router.post("/enroll")
async def enroll(
    payload: Proof, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    await reauthenticate(db, user, payload.password)
    row = db.get(MfaCredential, user.id)
    if row and row.enabled:
        raise HTTPException(409, "MFA already enabled")
    secret = base64.b32encode(secrets.token_bytes(20)).decode()
    encrypted = cipher().encrypt(secret.encode()).decode()
    if row:
        row.encrypted_secret = encrypted
        row.last_counter = -1
        row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    else:
        db.add(
            MfaCredential(
                user_id=user.id,
                encrypted_secret=encrypted,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
    db.commit()
    uri = (
        "otpauth://totp/"
        + quote(NAME + ":" + user.email, safe="")
        + "?"
        + urlencode(
            {
                "secret": secret,
                "issuer": NAME,
                "algorithm": "SHA1",
                "digits": 6,
                "period": 30,
            }
        )
    )
    return {"secret": secret, "otpauth_uri": uri, "expires_in_seconds": 600}


@router.post("/confirm")
async def confirm(
    payload: Proof, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    await reauthenticate(db, user, payload.password)
    row = db.get(MfaCredential, user.id)
    if not row or row.enabled:
        raise HTTPException(409, "Start enrollment first")
    if not consume(db, user.id, payload.code, allow_pending=True):
        raise HTTPException(403, "Invalid, expired or already used code")
    codes = [secrets.token_hex(12) for _ in range(10)]
    row.enabled = True
    row.recovery_hashes = [hash_security_token(code) for code in codes]
    user.token_version += 1
    db.add(AuthAuditEvent(user_id=user.id, event_type="mfa_enabled"))
    db.commit()
    return {
        "enabled": True,
        "recovery_codes": codes,
        "message": "Save codes securely. Sign in again.",
    }


@router.post("/disable")
async def disable(
    payload: Proof, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    await reauthenticate(db, user, payload.password)
    if not consume(db, user.id, payload.code):
        raise HTTPException(403, "Invalid or already used MFA/recovery code")
    db.delete(db.get(MfaCredential, user.id))
    user.token_version += 1
    db.add(AuthAuditEvent(user_id=user.id, event_type="mfa_disabled"))
    db.commit()
    return {"enabled": False, "message": "Sign in again."}

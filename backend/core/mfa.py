"""RFC 6238 TOTP, encrypted seeds, atomic replay/recovery-code protection."""

import base64
import hashlib
import hmac
import struct
import time
from datetime import datetime, timezone
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select, update
from core.config import get_settings
from core.security import hash_security_token
from models.mfa import MfaCredential


def cipher():
    key = get_settings().MFA_ENCRYPTION_KEY
    if not key:
        raise HTTPException(503, "MFA encryption key is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "MFA configuration unavailable")


def totp(secret, counter):
    raw = base64.b32decode(secret, casefold=True)
    mac = hmac.new(
        raw, struct.pack(">Q", counter), hashlib.sha1
    ).digest()  # RFC 6238 interoperable SHA-1 mode
    offset = mac[-1] & 15
    return str(
        (struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    ).zfill(6)


def consume(db, user_id, code, allow_pending=False):
    row = db.scalar(select(MfaCredential).where(MfaCredential.user_id == user_id).with_for_update())
    if not row or (not row.enabled and not allow_pending):
        return False
    expiry = (
        row.expires_at.replace(tzinfo=timezone.utc)
        if row.expires_at.tzinfo is None
        else row.expires_at
    )
    if not row.enabled and expiry < datetime.now(timezone.utc):
        return False
    if code and len(code) == 6 and code.isdecimal():
        try:
            secret = cipher().decrypt(row.encrypted_secret.encode()).decode()
        except InvalidToken:
            raise HTTPException(503, "MFA credential unavailable; contact the operator")
        counter = int(time.time() // 30)
        for candidate in range(counter - 1, counter + 2):
            if hmac.compare_digest(totp(secret, candidate), code):
                changed = db.execute(
                    update(MfaCredential)
                    .where(
                        MfaCredential.user_id == user_id,
                        MfaCredential.last_counter < candidate,
                        MfaCredential.encrypted_secret == row.encrypted_secret,
                    )
                    .values(last_counter=candidate)
                )
                return bool(changed.rowcount)
    if row.enabled and code:
        hashed = hash_security_token(code)
        old = list(row.recovery_hashes)
        if hashed in old:
            # Locked row serializes recovery-code consumption on PostgreSQL.
            row.recovery_hashes = [x for x in old if x != hashed]
            db.flush()
            return True
    return False

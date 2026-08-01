"""Password hashing, JWT creation, and auth dependencies."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import get_db
from models.user import User

settings = get_settings()
bearer = HTTPBearer(auto_error=False)
PASSWORD_ITERATIONS = 390_000
PASSWORD_SCHEME = "pbkdf2_sha256"
TOKEN_HASH_SCHEME = "sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_b64 = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(candidate, expected)
    except Exception:
        return False


def secure_token_urlsafe() -> str:
    return secrets.token_urlsafe(48)


def hash_security_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{TOKEN_HASH_SCHEME}${digest}"


def create_access_token(subject: str, token_version: int, expires_minutes: Optional[int] = None) -> str:
    issued_at = datetime.now(timezone.utc)
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRES_MINUTES
    )
    payload = {
        "sub": subject,
        "exp": expires,
        "iat": issued_at,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "typ": "access",
        "ver": token_version,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_payload(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
    except (PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )


def _user_from_payload(payload: dict, db: Session) -> User:
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
    user = db.get(User, int(subject))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    token_version = payload.get("ver")
    if token_version is not None and int(token_version) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    payload = _decode_payload(credentials.credentials)
    return _user_from_payload(payload, db)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    payload = _decode_payload(credentials.credentials)
    return _user_from_payload(payload, db)

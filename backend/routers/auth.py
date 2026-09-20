"""Authentication routes."""
from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from core.config import get_settings
from core.database import get_db
from core.email import send_email_verification, send_password_reset_email
from core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    hash_security_token,
    secure_token_urlsafe,
    verify_password,
)
from models.settings import UserSettings
from models.user import AuthAuditEvent, SecurityToken, User
from schemas.auth import (
    AuthMessage,
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UserOut,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])
settings = get_settings()
logger = logging.getLogger("privatelens.auth")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def audit(db: Session, event_type: str, request: Request, user: User | None = None, email: str | None = None) -> None:
    db.add(
        AuthAuditEvent(
            user_id=user.id if user else None,
            event_type=event_type,
            email=(email or user.email if user else email),
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )


def issue_security_token(db: Session, user: User, token_type: str, minutes: int) -> str:
    now = utc_now()
    db.query(SecurityToken).filter(
        SecurityToken.user_id == user.id,
        SecurityToken.token_type == token_type,
        SecurityToken.used_at.is_(None),
    ).delete()
    token = secure_token_urlsafe()
    db.add(
        SecurityToken(
            user_id=user.id,
            token_type=token_type,
            token_hash=hash_security_token(token),
            expires_at=now + timedelta(minutes=minutes),
        )
    )
    return token


def consume_security_token(db: Session, token: str, token_type: str) -> SecurityToken:
    token_hash = hash_security_token(token)
    record = (
        db.query(SecurityToken)
        .filter(
            SecurityToken.token_hash == token_hash,
            SecurityToken.token_type == token_type,
            SecurityToken.used_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if record is None or aware(record.expires_at) < utc_now():
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    record.used_at = utc_now()
    db.add(record)
    return record


def session_for(user: User, response: Response) -> AuthResponse:
    token = create_access_token(str(user.id), user.token_version)
    if settings.COOKIE_AUTH:
        response.set_cookie(settings.SESSION_COOKIE_NAME, token, httponly=True, secure=settings.is_production,
                            samesite="none" if settings.is_production else "lax",
                            max_age=settings.JWT_EXPIRES_MINUTES * 60, path="/")
    return AuthResponse(access_token=token if not settings.COOKIE_AUTH or settings.AUTH_TOKEN_RETURN_IN_RESPONSE else "", user=user)


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        audit(db, "signup_duplicate_email", request, email=email)
        db.commit()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        company=payload.company,
        role=payload.role,
    )
    user.settings = UserSettings()
    db.add(user)
    db.flush()
    audit(db, "signup_success", request, user=user, email=email)
    db.commit()
    db.refresh(user)
    verification_token = issue_security_token(
        db,
        user,
        "email_verification",
        settings.EMAIL_VERIFICATION_TOKEN_MINUTES,
    )
    db.commit()
    try:
        send_email_verification(user.email, verification_token)
    except Exception as exc:
        logger.error("signup_verification_email_failed user_id=%s error=%s", user.id, exc)

    return session_for(user, response)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None:
        audit(db, "login_failed_unknown_user", request, email=payload.email.lower())
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    locked_until = aware(user.locked_until)
    if locked_until and locked_until > utc_now():
        audit(db, "login_blocked_locked_account", request, user=user)
        db.commit()
        raise HTTPException(status_code=423, detail="Account temporarily locked. Try again later.")

    if not user.is_active or not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.LOGIN_MAX_FAILED_ATTEMPTS:
            user.locked_until = utc_now() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            audit(db, "login_account_locked", request, user=user)
        else:
            audit(db, "login_failed_bad_password", request, user=user)
        db.add(user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utc_now()
    audit(db, "login_success", request, user=user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return session_for(user, response)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", response_model=AuthMessage)
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Bump the token version so the presented bearer token stops working.
    # Without this, logging out only wrote an audit row and a stolen token stayed
    # valid for the full JWT lifetime.
    current_user.token_version += 1
    audit(db, "logout", request, user=current_user)
    db.add(current_user)
    db.commit()
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/", secure=settings.is_production, samesite="none" if settings.is_production else "lax")
    return {"message": "Logged out."}


@router.post("/change-password", response_model=AuthMessage)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        audit(db, "change_password_failed", request, user=current_user)
        db.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.password_hash = hash_password(payload.new_password)
    current_user.last_password_change_at = utc_now()
    current_user.token_version += 1
    audit(db, "change_password_success", request, user=current_user)
    db.add(current_user)
    db.commit()
    return {"message": "Password changed. Sign in again with the new password."}


@router.post("/request-password-reset", response_model=AuthMessage)
def request_password_reset(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    token = None
    if user and user.is_active:
        token = issue_security_token(db, user, "password_reset", settings.PASSWORD_RESET_TOKEN_MINUTES)
        audit(db, "password_reset_requested", request, user=user)
    else:
        audit(db, "password_reset_requested_unknown_user", request, email=payload.email.lower())
    db.commit()
    if user and user.is_active and token:
        send_password_reset_email(user.email, token)
    return {
        "message": "If an account exists, reset instructions have been issued.",
        "reset_token": token if settings.AUTH_TOKEN_RETURN_IN_RESPONSE else None,
    }


@router.post("/reset-password", response_model=AuthMessage)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    record = consume_security_token(db, payload.token, "password_reset")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user.password_hash = hash_password(payload.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_password_change_at = utc_now()
    user.token_version += 1
    audit(db, "password_reset_success", request, user=user)
    db.add(user)
    db.commit()
    return {"message": "Password reset. Sign in with the new password."}


@router.post("/request-email-verification", response_model=AuthMessage)
def request_email_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = issue_security_token(
        db,
        current_user,
        "email_verification",
        settings.EMAIL_VERIFICATION_TOKEN_MINUTES,
    )
    audit(db, "email_verification_requested", request, user=current_user)
    db.commit()
    send_email_verification(current_user.email, token)
    return {
        "message": "Verification instructions have been issued.",
        "verification_token": token if settings.AUTH_TOKEN_RETURN_IN_RESPONSE else None,
    }


@router.post("/verify-email", response_model=AuthMessage)
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    record = consume_security_token(db, payload.token, "email_verification")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user.email_verified = True
    audit(db, "email_verified", request, user=user)
    db.add(user)
    db.commit()
    return {"message": "Email verified."}

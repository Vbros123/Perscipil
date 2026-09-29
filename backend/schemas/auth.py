"""Auth schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validate_password_strength(value: str) -> str:
    checks = [
        any(ch.islower() for ch in value),
        any(ch.isupper() for ch in value),
        any(ch.isdigit() for ch in value),
        any(not ch.isalnum() for ch in value),
    ]
    if sum(checks) < 3:
        raise ValueError("Password must include at least three of: lowercase, uppercase, number, symbol.")
    return value


class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    role: str | None = None


class SignupRequest(UserBase):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    mfa_code: str = Field(default="", max_length=80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class AuthMessage(BaseModel):
    message: str
    reset_token: str | None = None
    verification_token: str | None = None


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=180)
    role: str | None = Field(default=None, max_length=120)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    email_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

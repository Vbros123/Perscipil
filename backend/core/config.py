"""Central configuration for PrivateLens API."""
from functools import lru_cache
import re
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    APP_NAME: str = "PrivateLens API"
    APP_VERSION: str = "4.0.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = False
    POLICY_REACCEPTANCE_REQUIRED: bool = False
    TERMS_TEXT: str = ""
    PRIVACY_TEXT: str = ""
    POLICIES_PUBLISHED: bool = False
    TERMS_VERSION: str = "2026-09-20-draft"
    PRIVACY_VERSION: str = "2026-09-20-draft"

    # Persistence
    DATABASE_URL: str = "sqlite:///./privatelens.db"
    AUTO_CREATE_TABLES: bool = True

    # Auth
    MFA_ENCRYPTION_KEY: str | None = None
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60
    COOKIE_AUTH: bool = False
    SESSION_COOKIE_NAME: str = "privatelens_session"
    SECURITY_CONTACT: str | None = None
    SECURITY_EXPIRES: str | None = None
    PUBLIC_DATA_USER_AGENT: str = "PrivateLens/4.0"
    RATE_LIMIT_BACKEND: Literal["memory", "database"] = "memory"
    JWT_ISSUER: str = "privatelens-api"
    JWT_AUDIENCE: str = "privatelens-dashboard"
    PASSWORD_RESET_TOKEN_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_MINUTES: int = 60 * 24
    AUTH_TOKEN_RETURN_IN_RESPONSE: bool = False
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Email delivery
    EMAIL_DELIVERY_MODE: Literal["disabled", "console", "smtp", "resend"] = "console"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "PrivateLens Security"
    SMTP_USE_TLS: bool = True
    RESEND_API_KEY: str | None = None
    RESEND_API_URL: str = "https://api.resend.com/emails"
    APP_PUBLIC_URL: str = "http://localhost:5173"

    NOTIFICATION_DESTINATIONS_JSON: str = "{}"

    # Observability
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05
    METRICS_TOKEN: str | None = None

    # Public mode uses the built-in open-data collectors. Licensed mode adds
    # paid-provider overrides through the vendor-normalization gateway.
    PROVIDER_PERMISSIONS_JSON: str = "{}"
    RETENTION_PERIODS_JSON: str = "{}"
    REPORT_RETENTION_DAYS: int = 30
    DATA_MODE: Literal["public", "licensed", "hybrid"] = "public"
    LICENSED_DATA_GATEWAY_URL: str | None = None
    LICENSED_DATA_API_KEY: str | None = None
    LICENSED_DATA_TIMEOUT: float = 6.0

    # A model can produce a public rating only after its validation packet has
    # been approved. Shadow mode still exercises the full evidence pipeline.
    MODEL_RELEASE_STAGE: Literal["shadow", "validated"] = "shadow"
    MODEL_VALIDATION_REFERENCE: str | None = None
    MODEL_VALIDATION_SHA256: str | None = None
    MODEL_APPROVED_BY: str | None = None

    # Cache TTL in seconds (1 hour)
    CACHE_TTL: int = 3600

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    # Data collector timeouts
    PROVIDER_BUDGETS_ENABLED: bool = True
    HTTP_TIMEOUT: float = 8.0

    # Optional free Census Bureau key. Industry context only; never company financials.
    CENSUS_API_KEY: str | None = None

    # CORS
    ALLOWED_ORIGINS: str = "*"
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_HOSTS: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        origins = [item.strip() for item in self.ALLOWED_ORIGINS.split(",") if item.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins or ["*"]

    @property
    def trusted_hosts(self) -> list[str]:
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [item.strip() for item in self.ALLOWED_HOSTS.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def licensed_credentials_present(self) -> bool:
        url = (self.LICENSED_DATA_GATEWAY_URL or "").strip()
        key = (self.LICENSED_DATA_API_KEY or "").strip()
        return bool(url and key)

    @property
    def effective_data_mode(self) -> str:
        """Configured mode, falling back to public when no licensed gateway exists.

        Missing credentials never invent financial data. They also must not crash
        the API: public collectors still run.
        """
        if self.DATA_MODE == "public":
            return "public"
        if self.licensed_credentials_present:
            return self.DATA_MODE
        return "public"

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if not value or len(value) < 32:
            # Allow short development/test secrets, but fail loudly in production via validate_runtime().
            return value
        return value

    def validate_runtime(self) -> None:
        if self.POLICIES_PUBLISHED and (not self.TERMS_TEXT.strip() or not self.PRIVACY_TEXT.strip()):
            raise RuntimeError("Published policies require their complete approved text.")
        if not self.is_production:
            return
        if self.DEBUG or self.AUTH_TOKEN_RETURN_IN_RESPONSE:
            raise RuntimeError("Debug and security-token responses must be disabled in production.")
        if self.RATE_LIMIT_BACKEND != "database":
            raise RuntimeError("Production requires shared database rate limiting.")
        if self.COOKIE_AUTH and any(not origin.startswith("https://") for origin in self.cors_origins):
            raise RuntimeError("Cookie authentication requires HTTPS origins in production.")
        if self.JWT_SECRET == "change-this-in-production" or len(self.JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be set to a strong random value in production.")
        if self.ALLOWED_ORIGINS == "*":
            raise RuntimeError("ALLOWED_ORIGINS must not be '*' in production.")
        if self.ALLOWED_HOSTS == "*":
            raise RuntimeError("ALLOWED_HOSTS must not be '*' in production.")
        if not self.DATABASE_URL.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("DATABASE_URL must point to managed Postgres in production.")
        if not self.SMTP_FROM_EMAIL:
            raise RuntimeError("A verified SMTP_FROM_EMAIL is required in production.")
        if self.EMAIL_DELIVERY_MODE == "smtp":
            if not self.SMTP_HOST or not self.SMTP_USERNAME or not self.SMTP_PASSWORD:
                raise RuntimeError("SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are required for SMTP delivery.")
        elif self.EMAIL_DELIVERY_MODE == "resend":
            if not self.RESEND_API_KEY:
                raise RuntimeError("RESEND_API_KEY is required for Resend delivery.")
        else:
            raise RuntimeError("Production email delivery must use 'smtp' or 'resend'.")
        if not self.METRICS_TOKEN or len(self.METRICS_TOKEN) < 24:
            raise RuntimeError("METRICS_TOKEN must be set to a strong value in production.")
        if self.effective_data_mode in {"licensed", "hybrid"} and self.licensed_credentials_present:
            if not self.LICENSED_DATA_GATEWAY_URL.startswith("https://"):
                raise RuntimeError("Licensed data gateway must use HTTPS in production.")
        if self.MODEL_RELEASE_STAGE == "validated":
            if self.effective_data_mode not in {"licensed", "hybrid"} or not self.licensed_credentials_present:
                raise RuntimeError("A validated model release requires a configured licensed gateway.")
            if not self.MODEL_VALIDATION_REFERENCE or not self.MODEL_APPROVED_BY:
                raise RuntimeError("Validated model releases require a validation reference and approver.")
            if not self.MODEL_VALIDATION_SHA256 or not re.fullmatch(r"[a-fA-F0-9]{64}", self.MODEL_VALIDATION_SHA256):
                raise RuntimeError("Validated model releases require the validation artifact SHA-256.")


@lru_cache()
def get_settings() -> Settings:
    return Settings()

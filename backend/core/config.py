"""Central configuration for PrivateLens API."""
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    APP_NAME: str = "PrivateLens API"
    APP_VERSION: str = "3.1.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = False

    # Persistence
    DATABASE_URL: str = "sqlite:///./privatelens.db"
    AUTO_CREATE_TABLES: bool = True

    # Auth
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7
    JWT_ISSUER: str = "privatelens-api"
    JWT_AUDIENCE: str = "privatelens-dashboard"
    PASSWORD_RESET_TOKEN_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_MINUTES: int = 60 * 24
    AUTH_TOKEN_RETURN_IN_RESPONSE: bool = False
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Cache TTL in seconds (1 hour)
    CACHE_TTL: int = 3600

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    # Data collector timeouts
    HTTP_TIMEOUT: float = 8.0

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

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if not value or len(value) < 32:
            # Allow short development/test secrets, but fail loudly in production via validate_runtime().
            return value
        return value

    def validate_runtime(self) -> None:
        if not self.is_production:
            return
        if self.JWT_SECRET == "change-this-in-production" or len(self.JWT_SECRET) < 32:
            raise RuntimeError("JWT_SECRET must be set to a strong random value in production.")
        if self.ALLOWED_ORIGINS == "*":
            raise RuntimeError("ALLOWED_ORIGINS must not be '*' in production.")
        if self.ALLOWED_HOSTS == "*":
            raise RuntimeError("ALLOWED_HOSTS must not be '*' in production.")


@lru_cache()
def get_settings() -> Settings:
    return Settings()

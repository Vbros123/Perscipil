"""Configuration for the isolated licensed-provider gateway."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    GATEWAY_SHARED_SECRET: str = "development-only-secret"
    CREDITSAFE_ENABLED: bool = False
    CREDITSAFE_USERNAME: str | None = None
    CREDITSAFE_PASSWORD: str | None = None
    CREDITSAFE_BASE_URL: str = "https://connect.sandbox.creditsafe.com/v1"
    CREDITSAFE_LICENSE_REFERENCE: str | None = None
    PROVIDER_TIMEOUT: float = 12.0

    def validate_runtime(self) -> None:
        if self.ENVIRONMENT == "production" and len(self.GATEWAY_SHARED_SECRET) < 32:
            raise RuntimeError("GATEWAY_SHARED_SECRET must be at least 32 characters in production.")
        if self.CREDITSAFE_ENABLED and not all([
            self.CREDITSAFE_USERNAME,
            self.CREDITSAFE_PASSWORD,
            self.CREDITSAFE_LICENSE_REFERENCE,
        ]):
            raise RuntimeError("Creditsafe credentials and license reference are required when enabled.")
        if self.ENVIRONMENT == "production" and not self.CREDITSAFE_BASE_URL.startswith("https://"):
            raise RuntimeError("Creditsafe must use HTTPS in production.")


@lru_cache()
def get_settings() -> Settings:
    return Settings()

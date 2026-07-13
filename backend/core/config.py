"""Central configuration for PrivateLens API."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PrivateLens API"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False

    # Persistence
    DATABASE_URL: str = "sqlite:///./privatelens.db"

    # Auth
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24 * 7

    # Cache TTL in seconds (1 hour)
    CACHE_TTL: int = 3600

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    # Data collector timeouts
    HTTP_TIMEOUT: float = 8.0

    # CORS
    ALLOWED_ORIGINS: str = "*"
    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        origins = [item.strip() for item in self.ALLOWED_ORIGINS.split(",") if item.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins or ["*"]

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

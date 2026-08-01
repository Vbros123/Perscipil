"""Company and dashboard schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WatchlistCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=180)
    private_score: int | None = Field(default=None, ge=0, le=1000)
    rating: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None


class WatchlistUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None


class WatchlistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    normalized_name: str
    private_score: int | None
    rating: str | None
    color: str | None
    notes: str | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_name: str
    normalized_name: str | None = None
    private_score: int
    rating: str
    color: str
    query_type: str | None = None
    created_at: datetime | None = None
    queried_at: str | None = None


class CompanyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_name: str
    normalized_name: str
    private_score: int
    rating: str
    report: dict[str, Any]
    created_at: datetime | None = None


class CompanyScoreRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=180)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    registration_number: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=24)
    address: str | None = Field(default=None, max_length=300)
    provider_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("provider_ids")
    @classmethod
    def validate_provider_ids(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"creditsafe", "middesk", "codat"}
        if len(value) > len(allowed):
            raise ValueError("provider_ids contains too many entries")
        if any(key not in allowed or not provider_id.strip() or len(provider_id.strip()) > 180 for key, provider_id in value.items()):
            raise ValueError("provider_ids contains an unsupported key or invalid identifier")
        return {key: provider_id.strip() for key, provider_id in value.items()}

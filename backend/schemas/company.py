"""Company and dashboard schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WatchlistCreate(BaseModel):
    """Only the company and the user's own annotations are client-supplied.

    Score, rating, colour, and scoring status are resolved server-side from the
    stored report so a crafted request cannot save a fabricated rating.
    """

    company_name: str = Field(min_length=2, max_length=180)
    notes: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None

    @field_validator("company_name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("company_name must contain at least 2 non-whitespace characters")
        return cleaned


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
    scoring_status: str | None = None
    notes: str | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_name: str
    normalized_name: str | None = None
    private_score: int | None = None
    rating: str
    color: str
    scoring_status: str | None = None
    query_type: str | None = None
    created_at: datetime | None = None
    queried_at: str | None = None


class CompanyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_name: str
    normalized_name: str
    private_score: int | None = None
    rating: str
    report: dict[str, Any]
    created_at: datetime | None = None


class NestedScore(BaseModel):
    value: int | None = None
    max: int = 1000
    riskLevel: str | None = None
    confidence: float = 0
    coverage: float = 0
    evidenceQuality: str | None = None
    observedStrength: float | None = None
    ceiling: int | None = None


class NestedCompany(BaseModel):
    name: str | None = None
    canonicalName: str | None = None
    domain: str | None = None
    industry: str | None = None
    companyType: str | None = None
    location: str | None = None


class CompanyScoreRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=180)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    registration_number: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=24)
    address: str | None = Field(default=None, max_length=300)
    provider_ids: dict[str, str] = Field(default_factory=dict)
    refresh: bool = False
    selected_title: str | None = Field(default=None, max_length=180)

    @field_validator("selected_title")
    @classmethod
    def clean_selected_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("provider_ids")
    @classmethod
    def validate_provider_ids(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"creditsafe", "middesk", "codat"}
        if len(value) > len(allowed):
            raise ValueError("provider_ids contains too many entries")
        if any(key not in allowed or not provider_id.strip() or len(provider_id.strip()) > 180 for key, provider_id in value.items()):
            raise ValueError("provider_ids contains an unsupported key or invalid identifier")
        return {key: provider_id.strip() for key, provider_id in value.items()}

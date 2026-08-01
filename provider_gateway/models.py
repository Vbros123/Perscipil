"""Strict wire models for the provider gateway."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(min_length=2, max_length=180)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    registration_number: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=24)
    address: str | None = Field(default=None, max_length=300)
    provider_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("country_code")
    @classmethod
    def country_upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("provider_ids")
    @classmethod
    def validate_provider_ids(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"creditsafe", "middesk", "codat"}
        if len(value) > len(allowed):
            raise ValueError("provider_ids contains too many entries")
        if any(key not in allowed or not provider_id.strip() or len(provider_id.strip()) > 180 for key, provider_id in value.items()):
            raise ValueError("provider_ids contains an unsupported key or invalid identifier")
        return {key: provider_id.strip() for key, provider_id in value.items()}


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["privatelens.evidence.request.v2"] = Field(alias="schema")
    request_id: str = Field(min_length=8, max_length=180)
    entity: EntityRequest
    providers: list[Literal["creditsafe", "middesk", "codat"]]
    required_permitted_use: Literal["company_intelligence"]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    metric: str
    value: float | int | str | bool
    unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    higher_is_better: bool | None = None
    observed_at: datetime
    fetched_at: datetime
    source_ref: str
    quality_flags: list[str] = Field(default_factory=list)


class ProviderDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["creditsafe", "middesk", "codat"]
    name: str
    license_reference: str
    permitted_use: list[str]


class EntityMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_entity_id: str
    legal_name: str
    country_code: str
    registration_number: str | None = None
    postal_code: str | None = None
    address: str | None = None
    match_status: Literal["exact", "probable", "ambiguous", "not_found"]
    confidence: float = Field(ge=0, le=1)
    matched_fields: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderDescriptor
    entity_match: EntityMatch
    observations: list[Observation]


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["privatelens.evidence.v2"] = Field(
        default="privatelens.evidence.v2",
        alias="schema",
    )
    request_id: str
    generated_at: datetime
    bundles: list[EvidenceBundle]

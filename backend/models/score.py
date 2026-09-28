"""Pydantic models for Perspicil API responses."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SignalResult(BaseModel):
    signal: str
    icon: str
    display: str
    raw_score: float = Field(ge=0, le=100)
    weight: float
    effective_weight: float = 0
    weighted_contribution: float
    insight: str
    is_simulated: bool
    used_in_score: bool = False
    source_url: str
    category: str  # "financial", "operational", "legal", "sentiment", "digital"
    availability_status: str | None = None
    provider: str | None = None
    provider_key: str | None = None
    license_reference: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    observed_at: str | None = None
    freshness_days: int | None = None
    entity_match_confidence: float | None = None
    entity_match_status: str | None = None
    transform_version: str | None = None


class ScoreMeta(BaseModel):
    total_signals: int
    real_signals: int
    scored_signals: int
    simulated_signals: int
    model_version: str
    confidence: float  # 0-1, based on score-eligible weight coverage
    scored_weight: float
    minimum_rating_coverage: float
    scoring_status: str
    disclaimer: str
    cached: bool = False
    computed_at: str
    evidence_coverage: float = 0
    provider_diversity: int = 0
    providers_used: list[str] = Field(default_factory=list)
    identity_verified: bool = False
    gates: dict = Field(default_factory=dict)
    model_release_stage: str = "shadow"
    input_snapshot_hash: str | None = None


class ScoreResponse(BaseModel):
    company_name: str
    normalized_name: str
    private_score: int = Field(ge=0, le=1000)
    scoring_status: str
    previous_score: Optional[int] = None
    score_delta: Optional[int] = None
    rating: str
    color: str
    summary: str
    breakdown: list[SignalResult]
    meta: ScoreMeta
    elapsed_seconds: float
    entity: dict = Field(default_factory=dict)
    evidence: dict = Field(default_factory=dict)


class CompareResponse(BaseModel):
    companies: list[ScoreResponse]
    winner: str
    analysis: str


class HistoryEntry(BaseModel):
    company_name: str
    private_score: int
    rating: str
    color: str
    queried_at: str


class SearchSuggestion(BaseModel):
    name: str
    category: str

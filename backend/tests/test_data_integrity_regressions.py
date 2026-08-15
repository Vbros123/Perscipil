"""Regression tests for accuracy defects found in the 2026-08-08 audit.

Each test names the defect it locks down so the behaviour cannot silently return.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from core.limiter import SlidingWindowLimiter
from services.collectors import _looks_like_organisation, _normalize_entity_name
from services.evidence import (
    CompanyIdentity,
    EntityMatch,
    EvidenceBundle,
    GatewayEvidenceResponse,
    Observation,
    ProviderDescriptor,
    build_licensed_signals,
    _clamp,
    _number,
)
from services.reports import build_company_report, risk_level
from services.scorer import compute_score

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
IDENTITY = CompanyIdentity(legal_name="Acme Manufacturing LLC", country_code="US",
                           registration_number="A-123")


def _obs(metric, value, days_old=1, **kw):
    return Observation(evidence_id=f"ev-{metric}", metric=metric, value=value,
                       observed_at=NOW - timedelta(days=days_old), fetched_at=NOW,
                       source_ref=f"urn:{metric}", **kw)


def _bundle(provider, observations):
    return EvidenceBundle(
        provider=ProviderDescriptor(key=provider, name=provider.title(),
                                    license_reference=f"contract-{provider}",
                                    permitted_use=["company_intelligence"]),
        entity_match=EntityMatch(provider_entity_id=f"{provider}-1",
                                 legal_name="Acme Manufacturing LLC", country_code="US",
                                 registration_number="A-123", match_status="exact",
                                 confidence=0.99,
                                 matched_fields=["legal_name", "registration_number"]),
        observations=observations)


def _response(*bundles):
    return GatewayEvidenceResponse(schema="privatelens.evidence.v2", request_id="request-abcdefgh",
                                   generated_at=NOW, bundles=list(bundles))


def _signal(name, raw, **kw):
    base = {"signal": name, "raw_score": raw, "category": "financial", "is_simulated": False,
            "is_scored": True, "provider_key": "creditsafe", "entity_match_confidence": 1.0,
            "freshness_days": 0}
    return {**base, **kw}


# ── Defect: NaN was clamped to the maximum score ──────────────────────────────

def test_nan_never_becomes_a_score():
    """`max(0, min(100, nan))` is 100 in Python, so NaN used to score a perfect 100."""
    assert _number(float("nan")) is None
    assert _number(float("inf")) is None
    assert _number(float("-inf")) is None
    assert _number("nan") is None
    with pytest.raises(ValueError):
        _clamp(float("nan"))


def test_nan_from_gateway_json_is_rejected_not_scored_as_perfect():
    # Python's json.loads accepts the bare NaN literal, which is how a malformed
    # provider payload reaches the transforms.
    body = json.loads("""
    {"schema": "privatelens.evidence.v2", "request_id": "request-abcdefgh",
     "generated_at": "2026-08-07T12:00:00+00:00",
     "bundles": [{
       "provider": {"key": "creditsafe", "name": "Creditsafe",
                    "license_reference": "contract-x", "permitted_use": ["company_intelligence"]},
       "entity_match": {"provider_entity_id": "cs-1", "legal_name": "Acme Manufacturing LLC",
                        "country_code": "US", "registration_number": "A-123",
                        "match_status": "exact", "confidence": 0.99,
                        "matched_fields": ["legal_name", "registration_number"]},
       "observations": [{"evidence_id": "ev-001", "metric": "creditsafe.credit_score",
                         "value": NaN, "scale_min": 0, "scale_max": 100, "higher_is_better": true,
                         "observed_at": "2026-08-06T12:00:00+00:00",
                         "fetched_at": "2026-08-07T12:00:00+00:00",
                         "source_ref": "urn:creditsafe:1"}]}]}
    """)
    parsed = GatewayEvidenceResponse.model_validate(body)
    signals, _ = build_licensed_signals(parsed, IDENTITY, now=NOW)
    credit = next(s for s in signals if s["signal"] == "Commercial Credit Risk")

    assert credit["raw_score"] is None
    assert credit["is_scored"] is False
    assert credit["availability_status"] == "unavailable"


def test_unusable_raw_scores_are_excluded_rather_than_defaulted():
    for bad in (float("nan"), float("inf"), None, {}, [], "abc"):
        result = compute_score([_signal("Commercial Credit Risk", bad)],
                               model_release_stage="validated")
        assert result["meta"]["scored_signals"] == 0, bad
        assert result["meta"]["model_output_score"] is None, bad
        assert "Commercial Credit Risk" in result["meta"]["unusable_signals"], bad


def test_one_bad_signal_does_not_corrupt_the_others():
    result = compute_score([
        _signal("Commercial Credit Risk", float("nan")),
        _signal("B2B Payment Behavior", 40),
        _signal("Cash Flow & Liquidity", 40, provider_key="codat"),
        _signal("Business Identity & Standing", 40, provider_key="middesk", category="legal"),
        _signal("Liens, Bankruptcy & Litigation", 40, provider_key="middesk", category="legal"),
    ], model_release_stage="validated")

    assert result["meta"]["model_output_score"] == 400
    assert result["meta"]["evidence_coverage"] == pytest.approx(0.70)


# ── Defect: unrated companies carried a neutral 500 placeholder ───────────────

def test_unrated_company_publishes_no_number():
    result = compute_score([], model_release_stage="validated")

    assert result["private_score"] is None
    assert result["scoring_status"] == "unrated"
    assert risk_level(result["private_score"], result["scoring_status"]) == "Unrated"


def test_shadow_mode_withholds_the_score_even_when_gates_pass():
    signals, _ = build_licensed_signals(_response(
        _bundle("creditsafe", [_obs("creditsafe.credit_score", 90, scale_min=0, scale_max=100,
                                    higher_is_better=True),
                               _obs("creditsafe.days_beyond_terms", 0)]),
        _bundle("middesk", [_obs("middesk.registration_status", "active"),
                            _obs("middesk.active_bankruptcy_count", 0),
                            _obs("middesk.recent_lien_count_12m", 0),
                            _obs("middesk.active_tax_lien_count", 0),
                            _obs("middesk.defendant_litigation_count_24m", 0)]),
    ), IDENTITY, now=NOW)
    result = compute_score(signals, model_release_stage="shadow")

    assert result["scoring_status"] == "validation_hold"
    assert result["private_score"] is None
    # The model still runs in shadow mode; its output is available for governance.
    assert isinstance(result["meta"]["model_output_score"], int)


def test_report_builder_handles_a_missing_score():
    report = build_company_report({
        "company_name": "Example Co", "private_score": None, "rating": "Preliminary",
        "scoring_status": "insufficient_data", "summary": "No coverage.", "breakdown": [],
        "category_summary": {}, "meta": {},
    })

    assert report["risk_level"] == "Unrated"
    assert report["score"] is None


# ── Defect: entity_match_confidence was unbounded ─────────────────────────────

def test_evidence_confidence_cannot_exceed_one():
    result = compute_score([_signal("Commercial Credit Risk", 80, entity_match_confidence=99.0)],
                           model_release_stage="validated")
    assert 0 <= result["meta"]["confidence"] <= 1


# ── Defect: whitespace-only names passed the min-length check ─────────────────

def test_whitespace_only_company_name_is_rejected():
    for blank in ("   ", "\t\t", "  \n ", " a "):
        with pytest.raises(Exception):
            CompanyIdentity(legal_name=blank)


def test_invalid_country_code_is_rejected():
    for bad in ("ZZ", "XX", "QQ", "OO"):
        with pytest.raises(Exception):
            CompanyIdentity(legal_name="Acme Corp", country_code=bad)
    assert CompanyIdentity(legal_name="Acme Corp", country_code="gb").country_code == "GB"


# ── Defect: Wikipedia resolved disambiguation pages and unrelated topics ──────

def test_disambiguation_and_non_company_pages_are_not_treated_as_companies():
    # The real "Stripe" summary is a disambiguation stub.
    assert not _looks_like_organisation({"description": "Topics referred to by the same term",
                                         "extract": "Stripe, striped, or stripes may refer to:"})
    # The real "Apple" summary is about the fruit.
    assert not _looks_like_organisation({"description": "Edible fruit",
                                         "extract": "An apple is a round, edible fruit produced by an apple tree."})
    assert _looks_like_organisation({"description": "American multinational financial services and SaaS company",
                                     "extract": "Stripe, Inc. is an American company."})


def test_entity_name_normalisation_ignores_legal_suffixes_only():
    assert _normalize_entity_name("Stripe, Inc.") == _normalize_entity_name("Stripe")
    assert _normalize_entity_name("Apple Inc.") == _normalize_entity_name("Apple")
    assert _normalize_entity_name("Red Stripe") != _normalize_entity_name("Stripe")
    assert _normalize_entity_name("Adidas") != _normalize_entity_name("Stripe")


# ── Defect: batch endpoints bypassed the per-company rate limit ───────────────

def test_rate_limiter_charges_one_token_per_company():
    async def scenario():
        limiter = SlidingWindowLimiter(max_requests=4, window_seconds=60)
        first = await limiter.is_allowed("ip", cost=4)
        second = await limiter.is_allowed("ip", cost=1)
        return first, second

    (allowed, _), (blocked, retry_after) = asyncio.run(scenario())
    assert allowed
    assert not blocked and retry_after >= 1


def test_rate_limiter_reads_configured_limit():
    from core.config import get_settings
    from core.limiter import rate_limiter

    assert rate_limiter._max == get_settings().RATE_LIMIT_PER_MINUTE

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from services.evidence import (
    CompanyIdentity,
    EvidenceBundle,
    EntityMatch,
    GatewayEvidenceResponse,
    Observation,
    ProviderDescriptor,
    build_licensed_signals,
    evidence_hash,
)
from services.reports import build_company_report
from services.scorer import compute_score


NOW = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
IDENTITY = CompanyIdentity(
    legal_name="Acme Manufacturing LLC",
    country_code="US",
    registration_number="A-123",
)


def observation(metric, value, *, provider="source", days_old=1, **kwargs):
    return Observation(
        evidence_id=f"{provider}:{metric}:{days_old}",
        metric=metric,
        value=value,
        observed_at=NOW - timedelta(days=days_old),
        fetched_at=NOW,
        source_ref=f"urn:{provider}:report:123",
        **kwargs,
    )


def bundle(provider, observations, *, confidence=0.99, status="exact", matched_fields=None):
    return EvidenceBundle(
        provider=ProviderDescriptor(
            key=provider,
            name=provider.title(),
            license_reference=f"contract-{provider}-2026",
            permitted_use=["company_intelligence"],
        ),
        entity_match=EntityMatch(
            provider_entity_id=f"{provider}-entity-123",
            legal_name="Acme Manufacturing LLC",
            country_code="US",
            registration_number="A-123",
            match_status=status,
            confidence=confidence,
            matched_fields=matched_fields or ["legal_name", "registration_number"],
        ),
        observations=observations,
    )


def response(*bundles):
    return GatewayEvidenceResponse(
        schema="privatelens.evidence.v2",
        request_id="request-12345678",
        generated_at=NOW,
        bundles=list(bundles),
    )


def creditsafe_bundle(days_old=1):
    return bundle("creditsafe", [
        observation(
            "creditsafe.credit_score",
            82,
            provider="creditsafe",
            days_old=days_old,
            scale_min=0,
            scale_max=100,
            higher_is_better=True,
        ),
        observation("creditsafe.days_beyond_terms", 4, provider="creditsafe", days_old=days_old, unit="days"),
    ])


def middesk_bundle(days_old=1):
    return bundle("middesk", [
        observation("middesk.registration_status", "active", provider="middesk", days_old=days_old),
        observation("middesk.active_bankruptcy_count", 0, provider="middesk", days_old=days_old),
        observation("middesk.recent_lien_count_12m", 0, provider="middesk", days_old=days_old),
        observation("middesk.active_tax_lien_count", 0, provider="middesk", days_old=days_old),
        observation("middesk.defendant_litigation_count_24m", 1, provider="middesk", days_old=days_old),
    ])


def codat_bundle(days_old=1):
    return bundle("codat", [
        observation("codat.current_ratio", 1.5, provider="codat", days_old=days_old, unit="ratio"),
        observation("codat.debt_service_coverage_ratio", 1.4, provider="codat", days_old=days_old, unit="ratio"),
        observation("codat.months_cash_on_hand", 8, provider="codat", days_old=days_old, unit="months"),
    ])


def test_gateway_contract_rejects_vendor_injected_score():
    payload = {
        "schema": "privatelens.evidence.v2",
        "request_id": "request-12345678",
        "generated_at": NOW.isoformat(),
        "bundles": [],
        "raw_score": 99,
    }
    with pytest.raises(ValidationError):
        GatewayEvidenceResponse.model_validate(payload)


def test_evidence_snapshot_hash_is_stable_and_entity_specific():
    audit = {"schema": "privatelens.evidence.audit.v1", "accepted_bundles": []}
    acme = CompanyIdentity(legal_name="Acme Manufacturing LLC", country_code="US")
    beta = CompanyIdentity(legal_name="Beta Manufacturing LLC", country_code="US")

    assert evidence_hash([], audit, acme) == evidence_hash([], audit, acme)
    assert evidence_hash([], audit, acme) != evidence_hash([], audit, beta)


def test_ambiguous_entity_is_rejected_and_never_scored():
    weak = bundle(
        "creditsafe",
        creditsafe_bundle().observations,
        confidence=0.80,
        status="ambiguous",
        matched_fields=["legal_name"],
    )
    signals, audit = build_licensed_signals(response(weak), IDENTITY, now=NOW)
    result = compute_score(signals, model_release_stage="validated")

    assert result["scoring_status"] == "insufficient_data"
    assert result["meta"]["scored_signals"] == 0
    assert audit["rejected_bundles"] == [{"provider": "creditsafe", "reason": "entity_match_below_threshold"}]


def test_gateway_match_for_a_different_requested_entity_is_rejected():
    different_request = CompanyIdentity(
        legal_name="Beta Manufacturing LLC",
        country_code="US",
        registration_number="B-999",
    )

    signals, audit = build_licensed_signals(response(creditsafe_bundle()), different_request, now=NOW)
    result = compute_score(signals, model_release_stage="validated")

    assert result["meta"]["scored_signals"] == 0
    assert audit["rejected_bundles"] == [
        {"provider": "creditsafe", "reason": "entity_match_request_mismatch"}
    ]


def test_stale_observations_are_excluded():
    signals, _ = build_licensed_signals(response(creditsafe_bundle(days_old=121)), IDENTITY, now=NOW)
    result = compute_score(signals, model_release_stage="validated")

    assert result["meta"]["scored_signals"] == 0
    assert result["scoring_status"] == "insufficient_data"


def test_valid_evidence_is_deterministic_and_held_in_shadow_mode():
    evidence = response(creditsafe_bundle(), middesk_bundle(), codat_bundle())
    first_signals, first_audit = build_licensed_signals(evidence, IDENTITY, now=NOW)
    second_signals, second_audit = build_licensed_signals(evidence, IDENTITY, now=NOW)
    first = compute_score(first_signals, model_release_stage="shadow")
    second = compute_score(second_signals, model_release_stage="shadow")

    assert first == second
    assert first_audit == second_audit
    assert first["meta"]["evidence_coverage"] == 1
    assert first["meta"]["provider_diversity"] == 3
    assert first["meta"]["identity_verified"] is True
    assert first["scoring_status"] == "validation_hold"
    assert first["rating"] == "Validation hold"


def test_validated_release_requires_coverage_identity_and_two_providers():
    signals, _ = build_licensed_signals(response(creditsafe_bundle(), middesk_bundle()), IDENTITY, now=NOW)
    result = compute_score(signals, model_release_stage="validated")

    assert result["meta"]["evidence_coverage"] == pytest.approx(0.8)
    assert result["meta"]["provider_diversity"] == 2
    assert all(result["meta"]["gates"].values())
    assert result["scoring_status"] == "rated"
    assert result["rating"] in {"Strong", "Exceptional"}


def test_two_financial_providers_cannot_replace_legal_entity_verification():
    signals, _ = build_licensed_signals(response(creditsafe_bundle(), codat_bundle()), IDENTITY, now=NOW)
    result = compute_score(signals, model_release_stage="validated")

    assert result["meta"]["evidence_coverage"] == pytest.approx(0.7)
    assert result["meta"]["provider_diversity"] == 2
    assert result["meta"]["identity_verified"] is False
    assert result["scoring_status"] == "insufficient_data"


def test_context_and_unavailable_values_do_not_change_score_or_flags():
    signals = [
        {
            "signal": "News & Media Sentiment",
            "raw_score": 0,
            "category": "sentiment",
            "is_simulated": False,
            "is_scored": False,
            "display": "context",
            "insight": "context",
            "source_url": "https://example.com",
        },
        {
            "signal": "Commercial Credit Risk",
            "raw_score": 100,
            "category": "financial",
            "is_simulated": True,
            "is_scored": False,
            "display": "unavailable",
            "insight": "unavailable",
            "source_url": "https://example.com",
        },
    ]
    result = compute_score(signals, model_release_stage="validated")

    # No evidence is scored, so no number is published at all. A neutral
    # placeholder here would be indistinguishable from a real mid-range score
    # once it reached a database row, an export, or an API consumer.
    assert result["private_score"] is None
    assert result["scoring_status"] == "insufficient_data"
    assert result["meta"]["model_output_score"] is None
    assert result["meta"]["evidence_coverage"] == 0
    assert result["risk_flags"] == []
    assert all(item["used_in_score"] is False for item in result["breakdown"])


def test_preliminary_report_does_not_claim_a_risk_level():
    score_data = {
        "company_name": "Example Co",
        "private_score": 800,
        "rating": "Preliminary",
        "scoring_status": "insufficient_data",
        "summary": "Insufficient coverage.",
        "breakdown": [],
        "category_summary": {},
        "meta": {"confidence": 0.08, "scored_weight": 0.08},
    }

    report = build_company_report(score_data)

    assert report["risk_level"] == "Unrated"
    assert "unrated" in report["headline"].lower()

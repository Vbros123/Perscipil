"""GLEIF identity provider: matching, collector isolation, and scoring neutrality."""
import asyncio

import httpx
import pytest

from services.collectors import collect_gleif
from services.providers.gleif import (
    GleifEntity,
    GleifLookup,
    parse_lei_record,
    rank_gleif_match,
    select_gleif_match,
)
from services.resolver import ResolvedCompany, _apply_gleif
from services.scorer import compute_score


CARGILL_LEI = "QXZYQNMR4JZ5RIRN4T31"
MICROSOFT_LEI = "INR2EJN1ERAN0W5ZP974"


def _record(lei, legal_name, country="US", status="ACTIVE", registration="ISSUED", jurisdiction="US-DE", other_names=None):
    return {
        "type": "lei-records",
        "id": lei,
        "attributes": {
            "lei": lei,
            "entity": {
                "legalName": {"name": legal_name},
                "otherNames": [{"name": item} for item in (other_names or [])],
                "legalAddress": {
                    "addressLines": ["1 Main"],
                    "city": "Wilmington",
                    "country": country,
                    "postalCode": "19801",
                },
                "headquartersAddress": {"addressLines": ["1 Main"], "city": "Wilmington", "country": country},
                "jurisdiction": jurisdiction,
                "legalForm": {"id": "XTIQ", "other": None},
                "status": status,
            },
            "registration": {"status": registration},
        },
    }


def test_parse_lei_record_extracts_identity_fields():
    entity = parse_lei_record(_record(CARGILL_LEI, "CARGILL, INCORPORATED"))
    assert entity.lei == CARGILL_LEI
    assert entity.legal_name == "CARGILL, INCORPORATED"
    assert entity.entity_status == "ACTIVE"
    assert entity.jurisdiction == "US-DE"
    assert entity.country == "US"
    assert entity.registered_address
    payload = entity.as_identity_dict()
    assert payload["source"] == "GLEIF"
    assert payload["lei"] == CARGILL_LEI


def test_malformed_response_is_rejected():
    with pytest.raises(ValueError):
        parse_lei_record({"attributes": {}})
    with pytest.raises(ValueError):
        parse_lei_record("not-json")
    with pytest.raises(ValueError):
        parse_lei_record({"id": "short", "attributes": {"entity": {"legalName": {"name": "X"}}}})


def test_company_with_lei_ranks_above_pension_trust():
    operating = parse_lei_record(_record(CARGILL_LEI, "CARGILL, INCORPORATED"))
    pension = parse_lei_record(_record(
        "9XHUQ4XI7GXPSNNRMD92",
        "CARGILL, INCORPORATED & ASSOCIATED COMPANIES MASTER PENSION TRUST",
        jurisdiction="US-MN",
    ))
    assert rank_gleif_match("Cargill", operating, "US") > rank_gleif_match("Cargill", pension, "US")
    lookup = select_gleif_match("Cargill", [pension, operating], "US")
    assert lookup.status == "live"
    assert lookup.selected.lei == CARGILL_LEI


def test_multiple_fuzzy_matches_do_not_auto_select_a_subsidiary():
    norway = parse_lei_record(_record("5493004XZPZSK8QE0X54", "CARGILL AS", country="NO", jurisdiction="NO"))
    belgium = parse_lei_record(_record("549300D2X85WHEH82V07", "CARGILL NV", country="BE", jurisdiction="BE"))
    lookup = select_gleif_match("Cargill", [norway, belgium], "US")
    assert lookup.status == "ambiguous"
    assert lookup.selected is None
    assert len(lookup.candidates) == 2


def test_no_gleif_result_is_unavailable_not_negative():
    lookup = select_gleif_match("Perscipil Research LLC", [], "US")
    assert lookup.status == "unavailable"
    assert lookup.selected is None


def test_known_companies_match_expected_legal_names():
    fixtures = {
        "Cargill": parse_lei_record(_record(CARGILL_LEI, "CARGILL, INCORPORATED")),
        "Microsoft": parse_lei_record(_record(MICROSOFT_LEI, "MICROSOFT CORPORATION")),
        "OpenAI": parse_lei_record(_record("5493006YX8088J1Z0X97", "OPENAI, INC.")),
        "Stripe": parse_lei_record(_record("549300T7WO7AEL4U4X81", "STRIPE, INC.")),
            "SpaceX": parse_lei_record(_record(
                "5493006XCW32Z7TBNM29",
                "SPACE EXPLORATION TECHNOLOGIES CORP.",
                other_names=["SpaceX"],
            )),
    }
    for query, entity in fixtures.items():
        lookup = select_gleif_match(query, [entity], "US")
        assert lookup.status == "live", query
        assert lookup.selected is not None, query
        assert lookup.selected.match_score >= 70, query


def test_company_without_lei_does_not_change_resolution():
    resolved = ResolvedCompany(
        query_name="Perscipil",
        canonical_key="privatelens",
        canonical_name="Perscipil",
        legal_name="Perscipil",
        resolution_status="unresolved",
        limited_identification=True,
    )
    updated = _apply_gleif(resolved, GleifLookup(status="unavailable"))
    assert updated.identifiers.get("lei") is None
    assert updated.resolution_status == "unresolved"
    assert updated.gleif["status"] == "unavailable"


def test_gleif_timeout_never_breaks_collector(monkeypatch):
    async def boom(query, country_code=None):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("services.providers.gleif.lookup_gleif", boom)
    result = asyncio.run(collect_gleif("Cargill"))
    assert result.source == "gleif"
    assert result.status == "unavailable"
    assert result.error_code == "TIMEOUT"
    assert result.signals[0]["availability_status"] == "unavailable"
    assert result.signals[0]["is_scored"] is False


def test_gleif_live_identity_is_not_scored():
    resolved = ResolvedCompany(
        query_name="Cargill",
        canonical_key="cargill",
        canonical_name="Cargill",
        legal_name="CARGILL, INCORPORATED",
        identifiers={"lei": CARGILL_LEI},
        resolution_status="resolved",
        gleif={
            "status": "live",
            "selected": {
                "lei": CARGILL_LEI,
                "legalName": "CARGILL, INCORPORATED",
                "entityStatus": "ACTIVE",
                "jurisdiction": "US-DE",
                "legalForm": "XTIQ",
                "registeredAddress": "Wilmington, US",
                "parents": [],
                "source": "GLEIF",
                "sourceUrl": f"https://api.gleif.org/api/v1/lei-records/{CARGILL_LEI}",
                "retrievedAt": "2026-08-15T00:00:00+00:00",
            },
        },
    )
    result = asyncio.run(collect_gleif("Cargill", resolved))
    assert result.status == "live"
    assert result.as_source_card()["evidenceQuality"] == "high"
    signal = result.signals[0]
    assert signal["is_scored"] is False
    assert signal["lei"] == CARGILL_LEI

    scored = compute_score([
        {
            "signal": "Legal Entity Identity",
            "raw_score": 100,
            "category": "legal",
            "is_simulated": False,
            "is_scored": False,
            "availability_status": "live",
            "evidence_quality": "high",
        },
        {
            "signal": "News & Media Sentiment",
            "raw_score": 70,
            "category": "sentiment",
            "is_simulated": False,
            "is_scored": True,
            "availability_status": "live",
            "evidence_quality": "low",
        },
    ], model_release_stage="shadow")
    gleif = next(item for item in scored["breakdown"] if item["signal"] == "Legal Entity Identity")
    assert gleif["used_in_score"] is False
    assert gleif["weighted_contribution"] == 0
    assert scored["private_score"] is not None
    assert scored["private_score"] < 700


def test_live_gleif_cargill_when_reachable():
    from services.providers.gleif import lookup_gleif

    try:
        lookup = asyncio.run(lookup_gleif("Cargill", "US"))
    except Exception as exc:
        pytest.skip(f"GLEIF unreachable: {type(exc).__name__}")
    if lookup.error_code:
        pytest.skip(f"GLEIF {lookup.error_code}")
    if lookup.status == "unavailable":
        pytest.skip("GLEIF returned no Cargill match")
    assert lookup.selected is not None
    assert lookup.selected.lei == CARGILL_LEI
    assert "CARGILL" in lookup.selected.legal_name.upper()


def test_lookup_timeout_returns_structured_error(monkeypatch):
    class _Boom:
        async def __aenter__(self):
            raise httpx.TimeoutException("timeout")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("services.providers.gleif.ProviderClient", lambda *args, **kwargs: _Boom())
    from services.providers.gleif import GleifProvider

    lookup = asyncio.run(GleifProvider().lookup("Cargill", "US"))
    assert lookup.status == "unavailable"
    assert lookup.error_code == "TIMEOUT"
    assert lookup.selected is None

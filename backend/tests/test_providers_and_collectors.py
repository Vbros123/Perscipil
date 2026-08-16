"""Provider registry, collector isolation, and insufficient-evidence reports."""
import asyncio

import httpx

from services.collectors import CollectorResult, _error_code, collect_all
from services.evidence import CompanyIdentity
from services.providers.base import unavailable_licensed_signal
from services.providers.registry import ProviderRegistry
from services.reports import build_company_report, score_company
from services.scorer import compute_score


def test_error_code_maps_timeout_and_rate_limit():
    assert _error_code(httpx.TimeoutException("timed out")) == "TIMEOUT"
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
    assert _error_code(httpx.HTTPStatusError("limited", request=response.request, response=response)) == "RATE_LIMIT"
    blocked = httpx.Response(403, request=httpx.Request("GET", "https://example.com"))
    assert _error_code(httpx.HTTPStatusError("blocked", request=blocked.request, response=blocked)) == "BLOCKED"


def test_source_card_never_includes_a_stack_trace():
    card = CollectorResult(
        source="jobs",
        status="unavailable",
        error="TIMEOUT",
        error_code="TIMEOUT",
        evidence_quality="unavailable",
    ).as_source_card()
    assert card["source"] == "Indeed"
    assert card["status"] == "unavailable"
    assert card["evidenceQuality"] == "unavailable"
    assert card["errorCode"] == "TIMEOUT"
    assert "Traceback" not in str(card)


def test_licensed_placeholder_is_unavailable_not_invented():
    signal = unavailable_licensed_signal("Commercial Credit Risk", "financial", "creditsafe")
    assert signal["status"] == "unavailable"
    assert signal["score"] is None
    assert signal["value"] is None
    assert "does not invent" in signal["explanation"]


def test_registry_reports_licensed_unavailable_without_credentials():
    status = ProviderRegistry().get_provider_status()
    assert status["effective_data_mode"] == "public"
    licensed = [item for item in status["providers"] if item["track"] == "licensed"]
    assert licensed
    assert all(item["status"] == "unavailable" for item in licensed)
    assert all(item["configured"] is False for item in licensed)


def test_registry_register_does_not_rewrite_scoring():
    class Stub:
        key = "future"
        name = "Future Vendor"

        def configured(self):
            return False

    registry = ProviderRegistry()
    registry.register(Stub())
    keys = [item["key"] for item in registry.get_available_providers()]
    assert "future" in keys


def test_all_collectors_failed_report_is_honest(monkeypatch):
    async def boom(_name, resolved=None):
        raise httpx.TimeoutException("timeout")

    async def no_licensed(_identity):
        return [], {"gateway_enabled": False}

    monkeypatch.setattr("services.collectors.collect_wikipedia", boom)
    monkeypatch.setattr("services.collectors.collect_job_postings", boom)
    monkeypatch.setattr("services.collectors.collect_news_sentiment", boom)
    monkeypatch.setattr("services.collectors.collect_sec_edgar", boom)
    monkeypatch.setattr("services.collectors.collect_usa_spending", boom)
    monkeypatch.setattr("services.collectors.collect_gleif", boom)
    monkeypatch.setattr("services.collectors.collect_licensed_signals", no_licensed)

    collection = asyncio.run(collect_all(CompanyIdentity(legal_name="Unknown Startup LLC")))
    assert collection["partial_failure"] is True
    assert all(item.status == "unavailable" for item in collection["collector_results"])
    assert all(item.error_code == "TIMEOUT" for item in collection["collector_results"])

    result = compute_score(collection["signals"], model_release_stage="shadow")
    assert result["private_score"] is None
    assert result["scoring_status"] == "unrated"
    assert result["rating"] == "Insufficient public evidence"
    assert "could not obtain enough reliable external evidence" in result["summary"]


def test_partial_collector_timeout_does_not_stop_others(monkeypatch):
    async def boom(_name, resolved=None):
        raise httpx.TimeoutException("timeout")

    async def jobs(_name, resolved=None):
        return CollectorResult(
            source="jobs",
            status="live",
            evidence_quality="low",
            signals=[{
                "signal": "Job Posting Velocity",
                "raw_score": 61,
                "category": "operational",
                "is_simulated": False,
                "is_scored": True,
                "availability_status": "live",
                "evidence_quality": "low",
            }],
        )

    async def news(_name, resolved=None):
        return CollectorResult(source="news", status="unavailable", signals=[])

    async def sec(_name, resolved=None):
        return CollectorResult(source="sec", status="not_applicable", signals=[])

    async def awards(_name, resolved=None):
        return CollectorResult(source="usaspending", status="not_applicable", signals=[])

    async def gleif(_name, resolved=None):
        return CollectorResult(source="gleif", status="not_applicable", signals=[])

    async def no_licensed(_identity):
        return [], {"gateway_enabled": False}

    monkeypatch.setattr("services.collectors.collect_wikipedia", boom)
    monkeypatch.setattr("services.collectors.collect_job_postings", jobs)
    monkeypatch.setattr("services.collectors.collect_news_sentiment", news)
    monkeypatch.setattr("services.collectors.collect_sec_edgar", sec)
    monkeypatch.setattr("services.collectors.collect_usa_spending", awards)
    monkeypatch.setattr("services.collectors.collect_gleif", gleif)
    monkeypatch.setattr("services.collectors.collect_licensed_signals", no_licensed)

    collection = asyncio.run(collect_all(CompanyIdentity(legal_name="Example Co")))
    sources = {item.source: item.status for item in collection["collector_results"]}
    assert sources["wikipedia"] == "unavailable"
    assert sources["jobs"] == "live"
    result = compute_score(collection["signals"], model_release_stage="shadow")
    assert result["private_score"] is not None
    assert result["scoring_status"] in {"rated", "limited"}


def test_unrated_report_lists_failed_sources():
    report = build_company_report({
        "company_name": "Unknown Co",
        "private_score": None,
        "rating": "Insufficient public evidence",
        "scoring_status": "unrated",
        "summary": "PrivateLens could not obtain enough reliable external evidence.",
        "breakdown": [],
        "category_summary": {},
        "dataSources": [
            {"source": "Wikipedia", "status": "unavailable", "errorCode": "TIMEOUT"},
            {"source": "Indeed", "status": "unavailable", "errorCode": "TIMEOUT"},
        ],
        "growthSignals": [],
        "sourceAttempts": {"attempted": 5, "successful": 0, "unavailable": 5},
        "metadata": {"generatedAt": "2026-08-15T00:00:00+00:00", "modelVersion": "public-v2", "dataVersion": "public-v2"},
        "meta": {"confidence": 0, "evidence_coverage": 0, "model_version": "public-v2"},
    })
    assert "insufficient public evidence" in report["headline"].lower()
    assert report["score"] is None
    assert report["data_sources"]
    assert report["disclaimer"]
    assert report["data_version"] == "public-v2"


def test_score_company_all_timeouts_stays_unrated(monkeypatch):
    async def boom(_name, resolved=None):
        raise httpx.TimeoutException("timeout")

    async def no_licensed(_identity):
        return [], {"gateway_enabled": False}

    async def fake_resolve(name, selected_title=None, country_code=None):
        from services.resolver import ResolvedCompany
        return ResolvedCompany(
            query_name=name,
            canonical_key="unknown co llc",
            canonical_name="Unknown Co LLC",
            legal_name="Unknown Co LLC",
            resolution_status="resolved",
            limited_identification=True,
            resolution_confidence=20,
        )

    monkeypatch.setattr("services.reports.resolve_company", fake_resolve)
    monkeypatch.setattr("services.collectors.collect_wikipedia", boom)
    monkeypatch.setattr("services.collectors.collect_job_postings", boom)
    monkeypatch.setattr("services.collectors.collect_news_sentiment", boom)
    monkeypatch.setattr("services.collectors.collect_sec_edgar", boom)
    monkeypatch.setattr("services.collectors.collect_usa_spending", boom)
    monkeypatch.setattr("services.collectors.collect_gleif", boom)
    monkeypatch.setattr("services.collectors.collect_licensed_signals", no_licensed)

    result = asyncio.run(score_company("Unknown Co LLC", refresh=True))
    assert result["private_score"] is None
    assert result["scoring_status"] == "unrated"
    assert result["rating"] == "Insufficient public evidence"
    assert result["sourceAttempts"]["attempted"] == 6
    assert result["sourceAttempts"]["unavailable"] == 6
    assert result["dataSources"]
    licensed = next(item for item in result["dataSources"] if item["key"] == "licensed")
    assert licensed["status"] == "unavailable"
    assert "Traceback" not in str(result)

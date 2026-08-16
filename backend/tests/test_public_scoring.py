"""Public-track scoring: publish a number from usable public signals."""
import asyncio

from services.collectors import CollectorResult, collect_all
from services.evidence import CompanyIdentity
from services.scorer import compute_score


def _public(name, raw, status="live", category="operational", **extra):
    return {
        "signal": name,
        "raw_score": raw,
        "category": category,
        "is_simulated": status == "modelled",
        "is_scored": status in {"live", "modelled"} and raw is not None,
        "availability_status": status,
        "display": name,
        "insight": "test",
        "source_url": "https://example.com",
        **extra,
    }


def test_public_wikipedia_and_jobs_publish_a_numeric_score():
    result = compute_score([
        _public("Brand Legitimacy & Web Presence", 78, category="digital"),
        _public("Job Posting Velocity", 70, category="operational"),
        _public("News & Media Sentiment", None, status="unavailable", category="sentiment"),
        _public("Government Contract Awards", None, status="not_applicable", category="financial"),
        _public("Company Stability", 90, category="operational"),
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert 0 <= result["private_score"] <= 1000
    assert result["scoring_status"] in {"rated", "limited"}
    assert result["meta"]["scoring_track"] == "public"
    assert result["meta"]["confidence"] > 0
    assert result["meta"]["evidence_coverage"] > 0
    assert result["meta"]["model_version"].startswith("public-v2")


def test_sec_not_applicable_does_not_zero_the_score():
    result = compute_score([
        _public("Brand Legitimacy & Web Presence", 78, category="digital"),
        {
            "signal": "SEC / Regulatory Filings",
            "raw_score": None,
            "category": "legal",
            "is_simulated": False,
            "is_scored": False,
            "availability_status": "not_applicable",
            "display": "Not applicable",
            "insight": "private company",
            "source_url": "https://efts.sec.gov",
        },
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert result["scoring_status"] in {"rated", "limited"}
    sec = next(item for item in result["breakdown"] if item["signal"] == "SEC / Regulatory Filings")
    assert sec["used_in_score"] is False
    assert sec["availability_status"] == "not_applicable"
    assert sec["raw_score"] is None


def test_all_collectors_empty_is_unrated():
    result = compute_score([
        _public("Brand Legitimacy & Web Presence", None, status="unavailable", category="digital"),
        _public("Job Posting Velocity", None, status="unavailable"),
        _public("News & Media Sentiment", None, status="unavailable", category="sentiment"),
        _public("Government Contract Awards", None, status="unavailable", category="financial"),
        _public("Company Stability", None, status="unavailable"),
    ], model_release_stage="shadow")

    assert result["private_score"] is None
    assert result["scoring_status"] == "unrated"
    assert result["rating"] == "Insufficient public evidence"


def test_licensed_live_overlay_increases_coverage_without_fake_values():
    public_only = compute_score([
        _public("Brand Legitimacy & Web Presence", 78, category="digital"),
        _public("Job Posting Velocity", 70),
    ], model_release_stage="shadow")
    with_licensed = compute_score([
        _public("Brand Legitimacy & Web Presence", 78, category="digital"),
        _public("Job Posting Velocity", 70),
        {
            "signal": "Commercial Credit Risk",
            "raw_score": 82,
            "category": "financial",
            "is_simulated": False,
            "is_scored": True,
            "availability_status": "live",
            "provider_key": "creditsafe",
            "entity_match_confidence": 0.99,
            "freshness_days": 1,
        },
    ], model_release_stage="shadow")

    assert with_licensed["meta"]["evidence_coverage"] >= public_only["meta"]["evidence_coverage"]
    assert with_licensed["scoring_status"] in {"rated", "limited"}
    assert with_licensed["private_score"] is not None


def test_public_mode_does_not_invent_licensed_scores():
    result = compute_score([
        _public("Brand Legitimacy & Web Presence", 78, category="digital"),
        {
            "signal": "Commercial Credit Risk",
            "raw_score": None,
            "category": "financial",
            "is_simulated": True,
            "is_scored": False,
            "availability_status": "unavailable",
        },
        {
            "signal": "Business Identity & Standing",
            "raw_score": None,
            "category": "legal",
            "is_simulated": True,
            "is_scored": False,
            "availability_status": "unavailable",
        },
    ], model_release_stage="shadow")

    licensed = [item for item in result["breakdown"] if item.get("track") == "licensed"]
    assert licensed
    assert all(item["used_in_score"] is False for item in licensed)
    assert all(item["raw_score"] is None for item in licensed)
    assert result["private_score"] is not None


def test_collector_crash_still_builds_a_report(monkeypatch):
    async def boom(_name, resolved=None):
        raise RuntimeError("wikipedia down")

    async def jobs(_name, resolved=None):
        return CollectorResult(source="jobs", status="live", signals=[
            _public("Job Posting Velocity", 64),
        ])

    async def news(_name, resolved=None):
        return CollectorResult(source="news", status="unavailable", signals=[
            _public("News & Media Sentiment", None, status="unavailable", category="sentiment"),
        ])

    async def sec(_name, resolved=None):
        return CollectorResult(source="sec", status="not_applicable", signals=[
            _public("SEC / Regulatory Filings", None, status="not_applicable", category="legal"),
        ])

    async def awards(_name, resolved=None):
        return CollectorResult(source="usaspending", status="not_applicable", signals=[
            _public("Government Contract Awards", None, status="not_applicable", category="financial"),
        ])

    async def no_licensed(_identity):
        return [], {"gateway_enabled": False}

    async def gleif(_name, resolved=None):
        return CollectorResult(source="gleif", status="not_applicable", signals=[
            _public("Legal Entity Identity", None, status="not_applicable", category="legal"),
        ])

    monkeypatch.setattr("services.collectors.collect_wikipedia", boom)
    monkeypatch.setattr("services.collectors.collect_job_postings", jobs)
    monkeypatch.setattr("services.collectors.collect_news_sentiment", news)
    monkeypatch.setattr("services.collectors.collect_sec_edgar", sec)
    monkeypatch.setattr("services.collectors.collect_usa_spending", awards)
    monkeypatch.setattr("services.collectors.collect_gleif", gleif)
    monkeypatch.setattr("services.collectors.collect_licensed_signals", no_licensed)

    collection = asyncio.run(collect_all(CompanyIdentity(legal_name="Example Manufacturing")))
    assert collection["partial_failure"] is True
    result = compute_score(collection["signals"], model_release_stage="shadow")
    assert result["private_score"] is not None
    assert result["scoring_status"] in {"rated", "limited"}
    wiki = next(item for item in result["breakdown"] if item["signal"] == "Brand Legitimacy & Web Presence")
    assert wiki["used_in_score"] is False
    jobs_signal = next(item for item in result["breakdown"] if item["signal"] == "Job Posting Velocity")
    assert jobs_signal["used_in_score"] is True

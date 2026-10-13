"""Public-data overhaul: source roles, scoring neutrality, and optional collectors."""
import asyncio

from services.collectors import CollectorResult, collect_all, collect_job_postings
from services.evidence import CompanyIdentity
from services.scorer import CATEGORY_LABELS, compute_score


def _signal(name, raw, category, status="live", scored=True, quality="low", scope="company", **extra):
    return {
        "signal": name,
        "raw_score": raw,
        "category": category,
        "is_simulated": False,
        "is_scored": scored and raw is not None,
        "availability_status": status,
        "evidence_quality": quality,
        "evidence_scope": scope,
        **extra,
    }


def test_licensed_unavailable_copy_does_not_name_vendors():
    from services.evidence import unavailable_signal

    signal = unavailable_signal("Commercial Credit Risk")
    assert "Creditsafe" not in signal["insight"]
    assert "Codat" not in signal["insight"]
    assert "Middesk" not in signal["insight"]
    assert "not currently connected" in signal["insight"]


def test_jobs_are_optional_and_not_scraped():
    result = asyncio.run(collect_job_postings("Cargill"))
    assert result.optional is True
    assert result.status == "unavailable"
    assert result.error_code == "OPTIONAL_UNAVAILABLE"
    assert result.as_source_card()["entityMatch"] == "Optional source"


def test_gleif_and_census_do_not_inflate_score():
    result = compute_score([
        _signal("Legal Entity Identity", None, "identity", scored=False, quality="high"),
        _signal("Industry Context", 90, "industry", scored=False, quality="medium", scope="industry"),
        _signal("Brand Legitimacy & Web Presence", 90, "identity", quality="low"),
        _signal("News & Media Sentiment", 90, "sentiment", quality="low"),
    ], model_release_stage="shadow")
    used = {item["signal"]: item for item in result["breakdown"] if item["used_in_score"]}
    assert "Legal Entity Identity" not in used
    assert "Industry Context" not in used
    assert result["private_score"] is None


def test_sec_company_facts_can_score_and_census_cannot():
    result = compute_score([
        _signal("SEC Financial Evidence", 74, "financial", quality="high"),
        _signal("Industry Context", 88, "industry", scored=False, quality="medium", scope="industry"),
        _signal("Legal Entity Identity", None, "identity", scored=False, quality="high"),
    ], model_release_stage="shadow")
    used = {item["signal"]: item for item in result["breakdown"] if item["used_in_score"]}
    assert used["SEC Financial Evidence"]["used_in_score"] is True
    assert "Industry Context" not in used
    assert "legal" not in result["category_summary"]
    assert result["category_summary"]["financial"]["label"] == "Financial Evidence"
    assert result["category_summary"]["industry"]["score"] is None


def test_usaspending_match_tiers():
    from services.collectors import _usaspending_match_tier

    assert _usaspending_match_tier("CARGILL, INCORPORATED", ["CARGILL, INCORPORATED"], True) == "Exact"
    assert _usaspending_match_tier("Cargill Inc", ["CARGILL, INCORPORATED"], True) == "Exact"
    assert _usaspending_match_tier("Cargill Inc", ["CARGILL, INCORPORATED"], False) == "Strong"
    assert _usaspending_match_tier("Cargill Foods", ["Cargill"], False) == "Name Match"
    assert _usaspending_match_tier("Cargill Foodservice", ["Microsoft"], True) == "Unresolved"


def test_sec_outranks_identity_only_public_context():
    identity_only = compute_score([
        _signal("Legal Entity Identity", None, "identity", scored=False, quality="high"),
        _signal("Brand Legitimacy & Web Presence", 90, "identity", quality="low"),
        _signal("Industry Context", 90, "industry", scored=False, quality="medium", scope="industry"),
    ], model_release_stage="shadow")
    with_sec = compute_score([
        _signal("SEC Financial Evidence", 82, "financial", quality="high"),
        _signal("Company Stability", 66, "operational", quality="medium"),
    ], model_release_stage="shadow", resolution_confidence=95)
    assert identity_only["private_score"] is None
    assert with_sec["private_score"] is not None
    assert with_sec["rating"] == "Public evidence available"


def test_low_confidence_does_not_use_strong_label():
    result = compute_score([
        _signal("Brand Legitimacy & Web Presence", 99, "identity", quality="low"),
        _signal("News & Media Sentiment", 99, "sentiment", quality="low"),
    ], model_release_stage="shadow")
    if result["meta"]["confidence"] < 0.30:
        assert result["rating"] not in {"Exceptional", "Strong"}


def test_categories_use_the_new_labels():
    assert CATEGORY_LABELS["identity"] == "Identity & Standing"
    assert CATEGORY_LABELS["government"] == "Government Activity"
    assert CATEGORY_LABELS["industry"] == "Industry Context"
    assert CATEGORY_LABELS["financial"] == "Financial Evidence"


def test_optional_census_failure_is_not_a_system_failure(monkeypatch):
    async def boom(_name, resolved=None):
        raise RuntimeError("down")

    async def wiki(_name, resolved=None):
        return CollectorResult(source="wikipedia", status="live", signals=[
            _signal("Brand Legitimacy & Web Presence", 56, "identity"),
        ])

    async def news(_name, resolved=None):
        return CollectorResult(source="news", status="unavailable", signals=[])

    async def sec(_name, resolved=None):
        return CollectorResult(source="sec", status="not_applicable", signals=[])

    async def awards(_name, resolved=None):
        return CollectorResult(source="usaspending", status="not_applicable", signals=[])

    async def gleif(_name, resolved=None):
        return CollectorResult(source="gleif", status="live", signals=[
            _signal("Legal Entity Identity", None, "identity", scored=False, quality="high"),
        ])

    async def no_licensed(_identity):
        return [], {"gateway_enabled": False}

    monkeypatch.setattr("services.collectors.collect_wikipedia", wiki)
    monkeypatch.setattr("services.collectors.collect_news_sentiment", news)
    monkeypatch.setattr("services.collectors.collect_sec_edgar", sec)
    monkeypatch.setattr("services.collectors.collect_usa_spending", awards)
    monkeypatch.setattr("services.collectors.collect_gleif", gleif)
    monkeypatch.setattr("services.collectors.collect_job_postings", boom)
    monkeypatch.setattr("services.collectors.collect_census", boom)
    monkeypatch.setattr("services.collectors.collect_licensed_signals", no_licensed)

    collection = asyncio.run(collect_all(CompanyIdentity(legal_name="Cargill")))
    assert collection["partial_failure"] is False
    sources = {item.source: item for item in collection["collector_results"]}
    assert sources["jobs"].optional is True
    assert sources["census"].optional is True

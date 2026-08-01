import pytest

from services.collectors import sim_court, sim_ucc
from services.reports import build_company_report
from services.scorer import WEIGHTS, compute_score


def signal(name, score, *, simulated=False, scored=True, category="financial"):
    return {
        "signal": name,
        "raw_score": score,
        "category": category,
        "is_simulated": simulated,
        "is_scored": scored,
        "display": "test",
        "insight": "test",
        "source_url": "https://example.com",
    }


def test_modelled_values_do_not_change_score_or_risk_flags():
    observed = signal("News & Media Sentiment", 80, simulated=False)
    modelled_low = signal("Open Banking Payment Flows", 0, simulated=True)
    modelled_high = signal("B2B Payment Behavior", 100, simulated=True)

    result = compute_score([observed, modelled_low, modelled_high])

    assert result["private_score"] == 800
    assert result["rating"] == "Preliminary"
    assert result["scoring_status"] == "insufficient_data"
    assert result["risk_flags"] == []
    assert result["meta"]["confidence"] == pytest.approx(WEIGHTS["News & Media Sentiment"])
    modelled = [item for item in result["breakdown"] if item["is_simulated"]]
    assert all(item["used_in_score"] is False for item in modelled)
    assert all(item["weighted_contribution"] == 0 for item in modelled)


def test_context_only_live_data_is_excluded_from_score():
    score_input = signal("Brand Legitimacy & Web Presence", 80)
    broad_keyword_match = signal("SEC / Regulatory Filings", 0, scored=False, category="legal")

    result = compute_score([score_input, broad_keyword_match])

    assert result["private_score"] == 800
    sec = next(item for item in result["breakdown"] if item["signal"] == "SEC / Regulatory Filings")
    assert sec["used_in_score"] is False
    assert result["risk_flags"] == []


def test_rating_requires_at_least_half_of_configured_weight():
    names = [
        "Open Banking Payment Flows",
        "B2B Payment Behavior",
        "Job Posting Velocity",
        "UCC Filings & Lien Activity",
        "Court Records & Litigation",
    ]
    result = compute_score([signal(name, 80) for name in names])

    assert sum(WEIGHTS[name] for name in names) >= 0.5
    assert result["private_score"] == 800
    assert result["scoring_status"] == "rated"
    assert result["rating"] == "Strong"


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


def test_unavailable_sources_do_not_fabricate_company_values():
    for fallback in (sim_ucc("Cargill"), sim_court("Theranos")):
        assert fallback["raw_score"] == 50
        assert fallback["display"] == "Verified data unavailable — not scored"
        assert "estimated" not in fallback["display"].lower()
        assert fallback["is_simulated"] is True

"""Calibration: missing and weak internet signals must not inflate Perspicil Score."""
from services.scorer import compute_score


def _signal(name, raw, status="live", category="operational", quality=None, **extra):
    payload = {
        "signal": name,
        "raw_score": raw,
        "category": category,
        "is_simulated": status == "modelled",
        "is_scored": status in {"live", "modelled", "verified"} and raw is not None,
        "availability_status": status,
        "display": name,
        "insight": "test",
        "source_url": "https://example.com",
        **extra,
    }
    if quality:
        payload["evidence_quality"] = quality
    return payload


def _licensed(name, raw, category="financial", provider="creditsafe"):
    return _signal(
        name,
        raw,
        status="live",
        category=category,
        quality="high",
        provider_key=provider,
        entity_match_confidence=0.99,
        freshness_days=1,
    )


PUBLIC_UNAVAILABLE = [
    _signal("Brand Legitimacy & Web Presence", None, status="unavailable", category="digital"),
    _signal("Company Stability", None, status="unavailable", category="operational"),
    _signal("Job Posting Velocity", None, status="unavailable", category="operational"),
    _signal("News & Media Sentiment", None, status="unavailable", category="sentiment"),
    _signal("Government Contract Awards", None, status="not_applicable", category="financial"),
]

LICENSED_UNAVAILABLE = [
    _signal("Commercial Credit Risk", None, status="unavailable", category="financial"),
    _signal("B2B Payment Behavior", None, status="unavailable", category="financial"),
    _signal("Cash Flow & Liquidity", None, status="unavailable", category="financial"),
    _signal("Business Identity & Standing", None, status="unavailable", category="legal"),
    _signal("Liens, Bankruptcy & Litigation", None, status="unavailable", category="legal"),
]


def test_single_perfect_news_hit_cannot_score_1000():
    result = compute_score([
        _signal("News & Media Sentiment", 100, category="sentiment", quality="low"),
        _signal("Brand Legitimacy & Web Presence", None, status="unavailable", category="digital"),
        _signal("Company Stability", None, status="unavailable", category="operational"),
        _signal("Job Posting Velocity", None, status="unavailable", category="operational"),
        _signal("Government Contract Awards", None, status="not_applicable", category="financial"),
        *LICENSED_UNAVAILABLE,
        _signal("SEC / Regulatory Filings", None, status="not_applicable", category="legal"),
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert result["private_score"] < 700
    assert result["private_score"] != 1000
    assert result["meta"]["confidence"] < 0.5
    news = next(item for item in result["breakdown"] if item["signal"] == "News & Media Sentiment")
    assert news["used_in_score"] is True
    assert news["evidence_quality"] == "low"
    missing = next(item for item in result["breakdown"] if item["signal"] == "Commercial Credit Risk")
    assert missing["used_in_score"] is False
    assert missing["raw_score"] is None


def test_profile_a_excellent_verified_evidence_can_score_high():
    result = compute_score([
        _licensed("Commercial Credit Risk", 96),
        _licensed("B2B Payment Behavior", 94),
        _licensed("Cash Flow & Liquidity", 92, provider="codat"),
        _licensed("Business Identity & Standing", 95, category="legal", provider="middesk"),
        _licensed("Liens, Bankruptcy & Litigation", 90, category="legal", provider="middesk"),
        _signal("Brand Legitimacy & Web Presence", 60, category="digital", quality="low"),
        _signal("Job Posting Velocity", 70, quality="low"),
    ], model_release_stage="validated")

    assert result["scoring_status"] == "rated"
    assert result["private_score"] >= 850
    assert result["meta"]["confidence"] >= 0.7
    assert result["meta"]["evidence_quality"] == "high"


def test_profile_b_web_presence_without_financials_is_not_near_perfect():
    result = compute_score([
        _signal("Brand Legitimacy & Web Presence", 78, category="digital", quality="low"),
        _signal("News & Media Sentiment", 88, category="sentiment", quality="low"),
        _signal("Job Posting Velocity", 40, quality="low"),
        _signal("Company Stability", None, status="unavailable"),
        _signal("Government Contract Awards", None, status="not_applicable", category="financial"),
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert result["private_score"] < 800
    assert result["meta"]["confidence"] < 0.45
    assert result["meta"]["evidence_quality"] in {"low", "medium"}


def test_profile_c_very_little_evidence_is_constrained():
    result = compute_score([
        _signal("Job Posting Velocity", 35, quality="low"),
        _signal("Brand Legitimacy & Web Presence", None, status="unavailable", category="digital"),
        _signal("News & Media Sentiment", None, status="unavailable", category="sentiment"),
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert result["private_score"] < 650
    assert result["meta"]["confidence"] < 0.35
    assert result["scoring_status"] in {"limited", "rated"}


def test_profile_d_negative_verified_evidence_scores_low():
    result = compute_score([
        _licensed("Commercial Credit Risk", 12),
        _licensed("B2B Payment Behavior", 18),
        _licensed("Cash Flow & Liquidity", 20, provider="codat"),
        _licensed("Business Identity & Standing", 10, category="legal", provider="middesk"),
        _licensed("Liens, Bankruptcy & Litigation", 8, category="legal", provider="middesk"),
    ], model_release_stage="validated")

    assert result["scoring_status"] == "rated"
    assert result["private_score"] < 300
    assert result["meta"]["evidence_quality"] == "high"


def test_profile_e_mostly_unavailable_is_unrated():
    result = compute_score([
        *PUBLIC_UNAVAILABLE,
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow")

    assert result["private_score"] is None
    assert result["scoring_status"] == "unrated"
    assert result["meta"]["confidence"] == 0
    assert all(item["used_in_score"] is False for item in result["breakdown"])
    assert all(item["raw_score"] is None or not item["used_in_score"] for item in result["breakdown"])


def test_profile_f_modelled_signals_cannot_dominate():
    result = compute_score([
        _signal("Brand Legitimacy & Web Presence", 100, status="modelled", category="digital", quality="modelled"),
        _signal("Company Stability", 100, status="modelled", quality="modelled"),
        _signal("Job Posting Velocity", 100, status="modelled", quality="modelled"),
        _signal("News & Media Sentiment", 100, status="modelled", category="sentiment", quality="modelled"),
        _signal("Government Contract Awards", 100, status="modelled", category="financial", quality="modelled"),
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow")

    assert result["private_score"] is not None
    assert result["private_score"] < 800
    assert result["private_score"] != 1000
    assert result["meta"]["confidence"] < 0.5
    assert result["meta"]["evidence_quality"] == "modelled"
    modelled = [item for item in result["breakdown"] if item["availability_status"] == "modelled"]
    assert modelled
    assert all(item["evidence_quality"] == "modelled" for item in modelled)


def test_profile_g_private_company_without_sec_can_still_score():
    result = compute_score([
        _licensed("Commercial Credit Risk", 84),
        _licensed("B2B Payment Behavior", 80),
        _licensed("Cash Flow & Liquidity", 78, provider="codat"),
        _licensed("Business Identity & Standing", 88, category="legal", provider="middesk"),
        _licensed("Liens, Bankruptcy & Litigation", 82, category="legal", provider="middesk"),
        _signal("SEC / Regulatory Filings", None, status="not_applicable", category="legal"),
    ], model_release_stage="validated")

    sec = next(item for item in result["breakdown"] if item["signal"] == "SEC / Regulatory Filings")
    assert sec["used_in_score"] is False
    assert sec["availability_status"] == "not_applicable"
    assert result["scoring_status"] == "rated"
    assert result["private_score"] >= 700


def test_early_stage_public_presence_is_not_a_perfect_score():
    """Generic stand-in for an early startup with internet activity and no finances."""
    result = compute_score([
        _signal("Brand Legitimacy & Web Presence", 56, category="digital", quality="low"),
        _signal("Job Posting Velocity", 22, quality="low"),
        _signal("News & Media Sentiment", 70, category="sentiment", quality="low"),
        _signal("Company Stability", 40, quality="medium"),
        _signal("Government Contract Awards", None, status="not_applicable", category="financial"),
        _signal("SEC / Regulatory Filings", None, status="not_applicable", category="legal"),
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow", resolution_confidence=40)

    assert result["private_score"] is not None
    assert result["private_score"] < 1000
    assert result["meta"]["confidence"] < 0.4
    assert result["meta"]["data_coverage"]["unavailableSignals"] >= 5
    used = [item for item in result["breakdown"] if item["used_in_score"]]
    assert used
    assert all(item["raw_score"] is not None for item in used)
    unused = [item for item in result["breakdown"] if not item["used_in_score"]]
    assert all(item["weighted_contribution"] == 0 for item in unused)


def test_missing_financials_are_not_scored_as_positive():
    result = compute_score([
        _signal("Brand Legitimacy & Web Presence", 56, category="digital", quality="low"),
        *LICENSED_UNAVAILABLE,
    ], model_release_stage="shadow")

    for name in (
        "Commercial Credit Risk",
        "B2B Payment Behavior",
        "Cash Flow & Liquidity",
        "Liens, Bankruptcy & Litigation",
    ):
        item = next(row for row in result["breakdown"] if row["signal"] == name)
        assert item["used_in_score"] is False
        assert item["raw_score"] is None
        assert item["weighted_contribution"] == 0
        assert item["evidence_role"] == "missing"

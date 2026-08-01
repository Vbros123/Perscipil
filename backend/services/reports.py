"""Score assembly and report formatting helpers."""
from __future__ import annotations

import copy
import re
import time
from datetime import datetime, timezone
from typing import Any

from core.cache import score_cache
from services.collectors import collect_all
from services.scorer import compute_score

DISCLAIMER = "PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice."


def normalize_company(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def risk_level(score: int, scoring_status: str = "rated") -> str:
    if scoring_status != "rated":
        return "Unrated"
    if score >= 750:
        return "Low"
    if score >= 550:
        return "Moderate"
    if score >= 400:
        return "Elevated"
    return "High"


async def score_company(company_name: str) -> dict[str, Any]:
    company_clean = company_name.strip()
    cache_key = normalize_company(company_clean)
    start = time.perf_counter()

    cached = await score_cache.get(cache_key)
    if cached:
        response = copy.deepcopy(cached)
        response["meta"]["cached"] = True
        response["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        response["report"] = build_company_report(response)
        return response

    signals = await collect_all(company_clean)
    result = compute_score(signals)
    elapsed = round(time.perf_counter() - start, 3)

    response = {
        "company_name": company_clean,
        "normalized_name": cache_key,
        "private_score": result["private_score"],
        "scoring_status": result["scoring_status"],
        "rating": result["rating"],
        "color": result["color"],
        "summary": result["summary"],
        "breakdown": result["breakdown"],
        "category_summary": result["category_summary"],
        "risk_flags": result["risk_flags"],
        "meta": {
            **result["meta"],
            "cached": False,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "legal_disclaimer": DISCLAIMER,
        },
        "elapsed_seconds": elapsed,
    }
    response["report"] = build_company_report(response)
    await score_cache.set(cache_key, response)
    return response


def build_company_report(score_data: dict[str, Any]) -> dict[str, Any]:
    score = int(score_data.get("private_score", 0))
    scoring_status = score_data.get("scoring_status") or score_data.get("meta", {}).get("scoring_status", "rated")
    rating_status = risk_level(score, scoring_status)
    breakdown = score_data.get("breakdown", [])
    live = [item for item in breakdown if not item.get("is_simulated", True)]
    simulated = [item for item in breakdown if item.get("is_simulated", True)]
    scored = [item for item in breakdown if item.get("used_in_score", False)]
    strongest = sorted(scored, key=lambda item: item.get("raw_score", 0), reverse=True)[:3]
    weakest = sorted(scored, key=lambda item: item.get("raw_score", 100))[:3]

    headline = (
        f"{score_data.get('company_name')} is unrated because verified coverage is below the required threshold."
        if scoring_status != "rated" else
        f"{score_data.get('company_name')} has a {rating_status.lower()} research risk profile."
    )

    return {
        "headline": headline,
        "risk_level": rating_status,
        "scoring_status": scoring_status,
        "score": score,
        "rating": score_data.get("rating"),
        "summary": score_data.get("summary"),
        "categories": [
            {
                "key": key,
                "label": value.get("label"),
                "score": value.get("score"),
                "signal_count": value.get("signal_count"),
            }
            for key, value in (score_data.get("category_summary") or {}).items()
        ],
        "strongest_signals": strongest,
        "watch_signals": weakest,
        "live_signal_count": len(live),
        "simulated_signal_count": len(simulated),
        "data_quality": {
            "confidence": score_data.get("meta", {}).get("confidence", 0),
            "scored_weight": score_data.get("meta", {}).get("scored_weight", 0),
            "live_sources": [item.get("signal") for item in live],
            "simulated_sources": [item.get("signal") for item in simulated],
        },
        "recommended_next_steps": [
            "Request bank-statement or open-banking cash-flow validation.",
            "Verify UCC lien and court-record status before material exposure.",
            "Monitor hiring, news sentiment, and vendor-risk changes weekly.",
        ],
        "limitations": [
            "Unavailable-source signals contain no fabricated values and are excluded from the score.",
            "Preliminary evidence scores are not financial-health ratings or standalone decisions.",
        ],
        "disclaimer": DISCLAIMER,
    }

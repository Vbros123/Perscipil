"""Score assembly, evidence snapshots, and report formatting."""
from __future__ import annotations

import copy
import re
import time
from datetime import datetime, timezone
from typing import Any

from core.cache import score_cache
from core.config import get_settings
from services.collectors import collect_all
from services.evidence import CompanyIdentity, evidence_hash
from services.scorer import compute_score

DISCLAIMER = "PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice."
settings = get_settings()


def normalize_company(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def risk_level(score: int | None, scoring_status: str = "rated") -> str:
    if scoring_status != "rated" or score is None:
        return "Unrated"
    if score >= 750:
        return "Low"
    if score >= 550:
        return "Moderate"
    if score >= 400:
        return "Elevated"
    return "High"


async def score_company(company_name: str, identity: CompanyIdentity | None = None) -> dict[str, Any]:
    identity = identity or CompanyIdentity(legal_name=company_name)
    company_clean = identity.legal_name
    normalized_name = normalize_company(company_clean)
    cache_key = "score:v4:" + identity.cache_key()
    start = time.perf_counter()

    cached = await score_cache.get(cache_key)
    if cached:
        response = copy.deepcopy(cached)
        response["meta"]["cached"] = True
        response["elapsed_seconds"] = round(time.perf_counter() - start, 3)
        response["report"] = build_company_report(response)
        return response

    collection = await collect_all(identity)
    signals = collection["signals"]
    evidence = collection["evidence"]
    result = compute_score(signals, model_release_stage=settings.MODEL_RELEASE_STAGE)
    snapshot_hash = evidence_hash(signals, evidence, identity)
    elapsed = round(time.perf_counter() - start, 3)

    response = {
        "company_name": company_clean,
        "normalized_name": normalized_name,
        "entity": identity.model_dump(mode="json", exclude_none=True),
        "private_score": result["private_score"],
        "scoring_status": result["scoring_status"],
        "rating": result["rating"],
        "color": result["color"],
        "summary": result["summary"],
        "breakdown": result["breakdown"],
        "category_summary": result["category_summary"],
        "risk_flags": result["risk_flags"],
        "evidence": evidence,
        "meta": {
            **result["meta"],
            "cached": False,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "input_snapshot_hash": snapshot_hash,
            "validation_reference": settings.MODEL_VALIDATION_REFERENCE,
            "validation_sha256": settings.MODEL_VALIDATION_SHA256,
            "model_approved_by": settings.MODEL_APPROVED_BY,
            "legal_disclaimer": DISCLAIMER,
        },
        "elapsed_seconds": elapsed,
    }
    response["report"] = build_company_report(response)
    await score_cache.set(cache_key, response)
    return response


def build_company_report(score_data: dict[str, Any]) -> dict[str, Any]:
    raw_score = score_data.get("private_score")
    score = int(raw_score) if raw_score is not None else None
    scoring_status = score_data.get("scoring_status") or score_data.get("meta", {}).get("scoring_status", "rated")
    rating_status = risk_level(score, scoring_status)
    breakdown = score_data.get("breakdown", [])
    live = [item for item in breakdown if not item.get("is_simulated", True)]
    unavailable = [item for item in breakdown if item.get("is_simulated", True)]
    scored = [item for item in breakdown if item.get("used_in_score", False)]
    strongest = sorted(scored, key=lambda item: item.get("raw_score", 0), reverse=True)[:3]
    weakest = sorted(scored, key=lambda item: item.get("raw_score", 100))[:3]

    if scoring_status == "validation_hold":
        headline = f"{score_data.get('company_name')} has sufficient evidence, but the model is awaiting validation approval."
    elif scoring_status != "rated":
        headline = f"{score_data.get('company_name')} is unrated because required evidence gates were not met."
    else:
        headline = f"{score_data.get('company_name')} has a {rating_status.lower()} research risk profile."

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
        "simulated_signal_count": len(unavailable),
        "data_quality": {
            "confidence": score_data.get("meta", {}).get("confidence", 0),
            "evidence_coverage": score_data.get("meta", {}).get("evidence_coverage", 0),
            "scored_weight": score_data.get("meta", {}).get("scored_weight", 0),
            "providers_used": score_data.get("meta", {}).get("providers_used", []),
            "gates": score_data.get("meta", {}).get("gates", {}),
            "input_snapshot_hash": score_data.get("meta", {}).get("input_snapshot_hash"),
            "live_sources": [item.get("signal") for item in live],
            "unavailable_sources": [item.get("signal") for item in unavailable],
        },
        "recommended_next_steps": [
            "Confirm the legal entity using its registration number and registered address.",
            "Review the underlying licensed provider records before material exposure.",
            "Obtain company consent for current accounting or banking evidence where appropriate.",
        ],
        "limitations": [
            "Unavailable and context-only inputs are excluded from the score.",
            "A rating is blocked until entity, coverage, provider-diversity, and model-approval gates pass.",
            "Provider data rights, retention, and derived-output permissions remain governed by signed contracts.",
        ],
        "disclaimer": DISCLAIMER,
    }

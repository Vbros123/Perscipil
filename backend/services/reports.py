"""Score assembly, evidence snapshots, and report formatting."""
from __future__ import annotations

import copy
import logging
import time
from datetime import datetime, timezone
from typing import Any

from core.cache import score_cache
from core.config import get_settings
from services.collectors import collect_all
from services.evidence import CompanyIdentity, evidence_hash
from services.licensed_data import enabled as licensed_data_enabled
from services.resolver import ResolvedCompany, canonical_key, resolve_company
from services.scorer import PUBLISHED_SCORE_STATUSES, compute_score

logger = logging.getLogger("privatelens.reports")
DISCLAIMER = "PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice."
settings = get_settings()


def normalize_company(name: str) -> str:
    key = canonical_key(name)
    return key or " ".join((name or "").split()).lower()


def risk_level(score: int | None, scoring_status: str = "rated") -> str:
    if scoring_status not in PUBLISHED_SCORE_STATUSES or score is None:
        return "Unrated"
    if score >= 750:
        return "Low"
    if score >= 550:
        return "Moderate"
    if score >= 400:
        return "Elevated"
    return "High"


def _disambiguation_response(
    company_name: str,
    identity: CompanyIdentity,
    resolved: ResolvedCompany,
    elapsed: float,
) -> dict[str, Any]:
    candidates = [item.as_dict() for item in resolved.candidates]
    response = {
        "company_name": company_name,
        "canonical_name": resolved.canonical_name,
        "normalized_name": resolved.canonical_key or normalize_company(company_name),
        "entity": identity.model_dump(mode="json", exclude_none=True),
        "private_score": None,
        "scoring_status": "needs_disambiguation",
        "rating": "Unrated",
        "color": "#64748B",
        "summary": "Several companies match this name. Choose the intended company to generate a score.",
        "breakdown": [],
        "category_summary": {},
        "risk_flags": [],
        "evidence": {},
        "candidates": candidates,
        "company": resolved.as_dict(),
        "score": {
            "value": None,
            "max": 1000,
            "riskLevel": "Unrated",
            "confidence": 0,
            "coverage": 0,
        },
        "signals": [],
        "dataCoverage": {"live": 0, "modelled": 0, "unavailable": 0, "notApplicable": 0, "totalSignals": 0, "coveragePercent": 0},
        "dataSources": [],
        "metadata": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "modelVersion": "public-v1",
            "dataVersion": "public-v1",
        },
        "meta": {
            "cached": False,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "scoring_status": "needs_disambiguation",
            "scoring_track": "none",
            "model_version": "public-v1",
            "confidence": 0,
            "evidence_coverage": 0,
            "legal_disclaimer": DISCLAIMER,
        },
        "elapsed_seconds": elapsed,
        "resolution": resolved.resolution_payload(),
    }
    response["report"] = build_company_report(response)
    return response


def _data_sources(collection: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for item in collection.get("collector_results") or []:
        if hasattr(item, "as_source_card"):
            cards.append(item.as_source_card())
    cards.append({
        "source": "Licensed credit / cash-flow / payment data",
        "key": "licensed",
        "status": "configured" if licensed_data_enabled() else "not_connected",
        "evidenceQuality": "high" if licensed_data_enabled() else "none",
        "coverage": "entity" if licensed_data_enabled() else "none",
        "lastRetrieved": None,
        "errorCode": None if licensed_data_enabled() else "NOT_CONFIGURED",
        "entityMatch": "Connected" if licensed_data_enabled() else "Not connected",
        "sourceUrl": None,
        "group": "licensed",
        "groupLabel": "LICENSED DATA",
        "optional": False,
    })
    if any((item.get("availability_status") or item.get("status")) == "modelled" for item in collection.get("signals") or []):
        cards.append({
            "source": "Modelled Signals",
            "key": "modelled",
            "status": "modelled",
            "evidenceQuality": "modelled",
            "errorCode": None,
            "retrievedAt": None,
        })
    return cards


def _growth_signals(breakdown: list[dict[str, Any]]) -> list[dict[str, Any]]:
    growth = []
    for item in breakdown:
        if not item.get("used_in_score"):
            continue
        if item.get("evidence_role") != "positive":
            continue
        if item.get("category") not in {"operational", "financial"}:
            continue
        growth.append({
            "name": item.get("signal"),
            "score": item.get("raw_score"),
            "explanation": item.get("insight"),
            "evidenceQuality": item.get("evidence_quality"),
        })
    return growth[:5]


def _nested_signals(breakdown: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nested = []
    for item in breakdown:
        nested.append({
            "name": item.get("signal"),
            "category": item.get("category"),
            "value": item.get("display"),
            "score": item.get("raw_score") if item.get("used_in_score") else None,
            "weight": item.get("weight"),
            "status": item.get("availability_status") or item.get("status") or "unavailable",
            "source": item.get("provider") or item.get("track"),
            "sourceUrl": item.get("source_url"),
            "retrievedAt": item.get("retrieved_at") or item.get("observed_at"),
            "lastUpdated": item.get("retrieved_at") or item.get("observed_at"),
            "explanation": item.get("insight"),
            "evidenceQuality": item.get("evidence_quality") or item.get("evidenceQuality"),
            "evidenceRole": item.get("evidence_role"),
        })
    return nested


async def score_company(
    company_name: str,
    identity: CompanyIdentity | None = None,
    refresh: bool = False,
    selected_title: str | None = None,
) -> dict[str, Any]:
    identity = identity or CompanyIdentity(legal_name=company_name)
    company_clean = identity.legal_name
    start = time.perf_counter()
    selected = (selected_title or "").strip() or None
    cache_key = "score:v12:" + scoring_config_hash() + ":" + __import__("hashlib").sha256(settings.PROVIDER_PERMISSIONS_JSON.encode()).hexdigest() + ":" + identity.cache_key() + (f":sel:{canonical_key(selected)}" if selected else "")

    if not refresh:
        cached = await score_cache.get(cache_key)
        if cached:
            response = copy.deepcopy(cached)
            response["meta"]["cached"] = True
            response["elapsed_seconds"] = round(time.perf_counter() - start, 3)
            response["report"] = build_company_report(response)
            return response

    resolved = await resolve_company(
        identity.legal_name,
        selected_title=selected,
        country_code=identity.country_code,
    )
    if resolved.needs_disambiguation or resolved.resolution_status == "ambiguous":
        logger.info("[Report] Query=%r status=ambiguous candidates=%s", company_clean, len(resolved.candidates))
        return _disambiguation_response(company_clean, identity, resolved, round(time.perf_counter() - start, 3))

    search_identity = identity
    if resolved.legal_name and not resolved.limited_identification:
        search_identity = identity.model_copy(update={"legal_name": resolved.legal_name})

    logger.info("[Collectors] Starting public collectors for %r", search_identity.legal_name)
    collection = await collect_all(search_identity, resolved=resolved)
    for item in collection.get("collector_results") or []:
        logger.info("[Collectors] %s: %s", item.source, item.status)
    signals = collection["signals"]
    evidence = collection["evidence"]
    live_count = sum(1 for item in signals if item.get("availability_status") in {"live", "verified"} and item.get("is_scored"))
    modelled_count = sum(1 for item in signals if item.get("availability_status") == "modelled" and item.get("is_scored"))
    logger.info("[Aggregator] Live signals: %s modelled: %s total: %s", live_count, modelled_count, len(signals))
    result = compute_score(
        signals,
        model_release_stage=settings.MODEL_RELEASE_STAGE,
        resolution_confidence=resolved.resolution_confidence,
    )
    logger.info(
        "[Scorer] Score=%s status=%s confidence=%s coverage=%s",
        result["private_score"],
        result["scoring_status"],
        result["meta"].get("confidence"),
        result["meta"].get("evidence_coverage"),
    )
    snapshot_hash = evidence_hash(signals, evidence, identity)
    elapsed = round(time.perf_counter() - start, 3)
    canonical = resolved.canonical_key or normalize_company(company_clean)
    data_coverage = result["meta"].get("data_coverage") or {
        "live": 0,
        "modelled": 0,
        "unavailable": 0,
        "notApplicable": 0,
    }
    warnings: list[str] = []
    if collection.get("partial_failure"):
        warnings.append("One or more data sources could not be retrieved. Report used remaining signals.")
    if resolved.limited_identification:
        warnings.append("Limited company identification. Score uses whatever public signals could be collected.")

    collectors = collection.get("collector_results") or []
    required = [item for item in collectors if not getattr(item, "optional", False)]
    source_attempts = {
        "attempted": len(required),
        "successful": sum(1 for item in required if item.status in {"live", "modelled", "not_applicable"}),
        "unavailable": sum(1 for item in required if item.status == "unavailable"),
        "optionalUnavailable": sum(1 for item in collectors if getattr(item, "optional", False) and item.status == "unavailable"),
        "failed": [
            {"source": item.source, "errorCode": item.error_code or item.error}
            for item in required if item.status == "unavailable"
        ],
    }
    data_sources = _data_sources(collection)
    growth_signals = _growth_signals(result["breakdown"])

    response = {
        "company_name": resolved.canonical_name or company_clean,
        "canonical_name": resolved.canonical_name or company_clean,
        "normalized_name": canonical,
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
        "candidates": [item.as_dict() for item in resolved.candidates],
        "company": resolved.as_dict(),
        "score": {
            "value": result["private_score"],
            "max": 1000,
            "riskLevel": risk_level(result["private_score"], result["scoring_status"]),
            "confidence": result["meta"]["confidence"],
            "coverage": result["meta"]["evidence_coverage"],
            "evidenceQuality": result["meta"].get("evidence_quality"),
            "observedStrength": result["meta"].get("observed_strength"),
            "ceiling": result["meta"].get("score_ceiling"),
        },
        "signals": _nested_signals(result["breakdown"]),
        "dataCoverage": data_coverage,
        "dataSources": data_sources,
        "growthSignals": growth_signals,
        "sourceAttempts": source_attempts,
        "licensedData": {
            "connected": licensed_data_enabled(),
            "status": "configured" if licensed_data_enabled() else "not_connected",
            "title": "Financial / Credit Data",
            "message": (
                "Licensed gateway configured; consult each signal for retrieved evidence."
                if licensed_data_enabled()
                else "Licensed credit, payment, cash-flow, and legal datasets are not currently connected."
            ),
            "availableIn": "Enterprise/paid data mode",
            "architectureReady": True,
        },
        "metadata": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "modelVersion": result["meta"]["model_version"],
            "scoringConfigHash": scoring_config_hash(),
            "dataVersion": result["meta"]["model_version"],
        },
        "meta": {
            **result["meta"],
            "cached": False,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "input_snapshot_hash": snapshot_hash,
            "legal_disclaimer": DISCLAIMER,
            "partial_source_failure": bool(collection.get("partial_failure")),
            "warnings": warnings,
            "retry_available": True,
            "effective_data_mode": settings.effective_data_mode,
        },
        "elapsed_seconds": elapsed,
        "resolution": resolved.resolution_payload(),
    }
    response["reproducibility"] = {"signals": signals, "configuration": scoring_configuration(), "resolution_confidence": resolved.resolution_confidence, "model_release_stage": settings.MODEL_RELEASE_STAGE}
    response["report"] = build_company_report(response)
    await score_cache.set(cache_key, response)
    logger.info("[Report] Generated successfully for %r score=%s", response["company_name"], response["private_score"])
    return response


def build_company_report(score_data: dict[str, Any]) -> dict[str, Any]:
    raw_score = score_data.get("private_score")
    score = int(raw_score) if raw_score is not None else None
    scoring_status = score_data.get("scoring_status") or score_data.get("meta", {}).get("scoring_status", "rated")
    rating_status = risk_level(score, scoring_status)
    breakdown = score_data.get("breakdown", [])
    live = [item for item in breakdown if item.get("availability_status") in {"live", "verified"} or (
        not item.get("is_simulated", True) and item.get("availability_status") not in {"unavailable", "not_applicable", "modelled"}
    )]
    unavailable = [item for item in breakdown if item.get("availability_status") == "unavailable" or (
        item.get("is_simulated", True) and item.get("availability_status") not in {"modelled", "not_applicable", "live"}
    )]
    scored = [item for item in breakdown if item.get("used_in_score", False)]
    strongest = sorted(scored, key=lambda item: item.get("raw_score") or 0, reverse=True)[:3]
    weakest = sorted(scored, key=lambda item: item.get("raw_score") if item.get("raw_score") is not None else 100)[:3]
    company_name = score_data.get("company_name")

    if scoring_status == "validation_hold":
        headline = f"{company_name} has sufficient evidence, but the model is awaiting validation approval."
    elif scoring_status == "needs_disambiguation":
        headline = f"{company_name} matches more than one company. Choose the intended company."
    elif scoring_status == "limited":
        headline = (
            f"{company_name} has a {rating_status.lower()} research profile based on limited public evidence. "
            "The score is not a complete financial assessment."
        )
    elif scoring_status not in PUBLISHED_SCORE_STATUSES:
        headline = (
            f"{company_name}: insufficient public evidence. "
            "PrivateLens could not obtain enough reliable external evidence to calculate a meaningful PrivateScore."
        )
        if scoring_status == "insufficient_data":
            headline = f"{company_name} is unrated because required evidence gates were not met."
    else:
        headline = f"{company_name} has a {rating_status.lower()} research risk profile."

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
                "weight": value.get("weight_coverage"),
                "signal_count": value.get("signal_count"),
                "evidenceQuality": value.get("evidence_quality") or value.get("evidenceQuality"),
                "coverage": value.get("coverage"),
                "explanation": value.get("explanation"),
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
            "evidence_quality": score_data.get("meta", {}).get("evidence_quality"),
            "scored_weight": score_data.get("meta", {}).get("scored_weight", 0),
            "providers_used": score_data.get("meta", {}).get("providers_used", []),
            "gates": score_data.get("meta", {}).get("gates", {}),
            "input_snapshot_hash": score_data.get("meta", {}).get("input_snapshot_hash"),
            "live_sources": [item.get("signal") for item in live],
            "unavailable_sources": [item.get("signal") for item in unavailable],
        },
        "recommended_next_steps": [
            "Confirm the legal entity using its registration number and registered address.",
            "Review live source records before material exposure.",
            "Treat this Public PrivateScore as research context, not a credit-bureau rating.",
        ],
        "limitations": [
            "Missing and not-applicable sources are excluded from the score; they are never treated as positive or as zero.",
            "GLEIF, Census industry context, and Wikipedia identity cannot manufacture a high PrivateScore by themselves.",
            "Census figures are national industry statistics, not this company's own employment or revenue.",
            "Absence of SEC filings, an LEI, or job postings is not negative financial evidence.",
            "Licensed credit, cash-flow, and legal evidence stay unavailable until a real gateway is configured.",
        ],
        "growth_signals": score_data.get("growthSignals") or [],
        "data_sources": score_data.get("dataSources") or [],
        "last_updated": score_data.get("metadata", {}).get("generatedAt") or score_data.get("meta", {}).get("computed_at"),
        "model_version": score_data.get("meta", {}).get("model_version") or score_data.get("metadata", {}).get("modelVersion"),
        "data_version": score_data.get("metadata", {}).get("dataVersion") or score_data.get("meta", {}).get("model_version"),
        "disclaimer": DISCLAIMER,
    }

def scoring_configuration():
    from services.evidence import SIGNAL_SPECS
    from services import scorer
    import hashlib
    from pathlib import Path
    return {"signals": SIGNAL_SPECS, "quality": scorer.QUALITY_MULTIPLIER,
            "supporting_cap": scorer.MAX_SUPPORTING_SHARE, "public_max": scorer.PUBLIC_ONLY_MAX,
            "ceiling_floor": scorer.CEILING_FLOOR, "ceiling_exponent": scorer.CEILING_EXP,
            "scorer_sha256": hashlib.sha256(Path(scorer.__file__).read_bytes()).hexdigest()}

def scoring_config_hash():
    import hashlib, json
    return hashlib.sha256(json.dumps(scoring_configuration(),sort_keys=True).encode()).hexdigest()

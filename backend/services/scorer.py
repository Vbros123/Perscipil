"""PrivateLens scoring engine v5: public track plus licensed overlay."""
from __future__ import annotations

import logging
import math
from typing import Any

from services.evidence import SIGNAL_SPECS

logger = logging.getLogger("privatelens.scorer")

LICENSED_WEIGHTS = {
    name: spec["weight"]
    for name, spec in SIGNAL_SPECS.items()
    if spec.get("track", "licensed") == "licensed"
}
PUBLIC_WEIGHTS = {
    name: spec["weight"]
    for name, spec in SIGNAL_SPECS.items()
    if spec.get("track") == "public"
}
WEIGHTS = {**LICENSED_WEIGHTS, **PUBLIC_WEIGHTS}
LICENSED_WEIGHT_TOTAL = sum(LICENSED_WEIGHTS.values())
PUBLIC_WEIGHT_TOTAL = sum(PUBLIC_WEIGHTS.values())

USABLE_STATUSES = frozenset({"live", "modelled", "verified"})
PUBLISHED_SCORE_STATUSES = frozenset({"rated", "limited"})
LIMITED_COVERAGE_THRESHOLD = 0.40

CATEGORY_LABELS = {
    "financial": "Financial Health",
    "operational": "Operational Signals",
    "legal": "Legal & Regulatory",
    "sentiment": "Market Sentiment",
    "digital": "Digital Presence",
}

RATING_BANDS = [
    (850, "Exceptional", "#00E5A0", "Verified evidence is consistently strong across the covered risk domains."),
    (700, "Strong", "#00C896", "Verified evidence is strong, with limited adverse indicators in the covered domains."),
    (550, "Adequate", "#4F98A3", "Verified evidence is mixed and warrants normal follow-up diligence."),
    (400, "Weak", "#E8AF34", "Verified evidence contains multiple elevated-risk indicators."),
    (250, "Distressed", "#BB653B", "Verified evidence indicates material financial or legal stress."),
    (0, "Critical", "#D163A7", "Verified evidence indicates severe stress requiring independent review."),
]

MIN_RATING_COVERAGE = 0.70
MIN_PROVIDER_DIVERSITY = 2
PRELIMINARY_COLOR = "#64748B"

# Returned in place of a rating when no evidence is scored. It is deliberately
# not a mid-range number, so a placeholder can never be mistaken for a score if
# it leaks into a database row, an export, or an API consumer.
UNRATED_SCORE = None


def _finite(value: Any) -> float | None:
    """Coerce to a finite float, or None if the value is unusable.

    Guards against NaN in particular: `max(0, min(100, nan))` evaluates to 100 in
    Python, which would silently promote corrupt provider data to a perfect score.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_score(value: Any) -> float | None:
    """Coerce a raw signal score to a finite float clamped to 0-100."""
    number = _finite(value)
    return None if number is None else max(0.0, min(100.0, number))


def _rating(score: int) -> tuple[str, str, str]:
    for threshold, label, color, summary in RATING_BANDS:
        if score >= threshold:
            return label, color, summary
    return RATING_BANDS[-1][1], RATING_BANDS[-1][2], RATING_BANDS[-1][3]


def _availability_status(signal: dict[str, Any]) -> str:
    status = signal.get("availability_status")
    if status == "verified":
        return "live"
    if status:
        return status
    if signal.get("is_simulated", True):
        return "unavailable"
    return "live"


def _track_for(name: str) -> str | None:
    spec = SIGNAL_SPECS.get(name)
    return spec.get("track") if spec else None


def compute_score(
    signals: list[dict[str, Any]],
    model_release_stage: str = "shadow",
    resolution_confidence: int | None = None,
) -> dict[str, Any]:
    scored_weight = 0.0
    weighted_sum = 0.0
    public_usable_weight = 0.0
    licensed_usable_weight = 0.0
    public_unavailable_weight = 0.0
    licensed_unavailable_weight = 0.0
    modelled_weight = 0.0
    breakdown: list[dict[str, Any]] = []
    category_scores: dict[str, list[tuple[float, float]]] = {}
    risk_flags: list[str] = []
    providers: set[str] = set()
    match_confidences: list[float] = []
    freshness_factors: list[float] = []
    unusable_signals: list[str] = []

    for signal in signals:
        name = signal.get("signal", "")
        spec = SIGNAL_SPECS.get(name, {})
        weight = spec.get("weight", WEIGHTS.get(name, 0.0))
        track = spec.get("track")
        category = signal.get("category", spec.get("category", "operational"))
        status = _availability_status(signal)
        wants_score = bool(signal.get("is_scored", True))
        raw = _finite_score(signal.get("raw_score"))
        usable_value = raw is not None
        used = bool(
            weight
            and wants_score
            and status in USABLE_STATUSES
            and usable_value
        )
        if wants_score and weight and status in USABLE_STATUSES and not usable_value:
            logger.warning("scorer.unusable_raw_score signal=%s value=%r", name, signal.get("raw_score"))
            unusable_signals.append(name)
            used = False

        if used:
            weighted_sum += raw * weight
            scored_weight += weight
            category_scores.setdefault(category, []).append((raw, weight))
            if track == "public":
                public_usable_weight += weight
            elif track == "licensed":
                licensed_usable_weight += weight
            if status == "modelled":
                modelled_weight += weight
            if signal.get("provider_key"):
                providers.add(signal["provider_key"])
            confidence = _finite(signal.get("entity_match_confidence", 0)) or 0.0
            match_confidences.append(max(0.0, min(1.0, confidence)))
            max_age = spec.get("max_age_days", 365)
            freshness = _finite(signal.get("freshness_days"))
            freshness_days = max_age if freshness is None else max(0.0, freshness)
            freshness_factors.append(max(0.0, 1 - freshness_days / (max_age * 2)))
        elif weight and status == "unavailable":
            if track == "public":
                public_unavailable_weight += weight
            elif track == "licensed":
                licensed_unavailable_weight += weight

        display_raw = round(raw, 1) if usable_value else None
        breakdown.append({
            **{key: value for key, value in signal.items() if key not in {"is_scored"}},
            "signal": name,
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category.title()),
            "raw_score": display_raw,
            "weight": weight,
            "weight_pct": f"{weight * 100:.0f}%" if weight else "Context",
            "effective_weight": weight if used else 0.0,
            "weighted_contribution": round(raw * weight, 2) if used else 0.0,
            "used_in_score": used,
            "value_usable": usable_value,
            "availability_status": status,
            "status": status,
            "track": track,
        })

        if used and raw < 30 and weight >= 0.15:
            risk_flags.append(f"{name}: verified evidence is in the severe-risk range ({raw:.0f}/100)")

    normalized = weighted_sum / scored_weight if scored_weight else None
    model_output_score = (
        max(0, min(1000, int(round(normalized * 10)))) if normalized is not None else None
    )
    licensed_coverage = (
        licensed_usable_weight / LICENSED_WEIGHT_TOTAL if LICENSED_WEIGHT_TOTAL else 0.0
    )
    public_coverage_den = public_usable_weight + public_unavailable_weight
    if licensed_usable_weight:
        public_coverage_den += licensed_usable_weight
    public_coverage = (
        (public_usable_weight + licensed_usable_weight) / public_coverage_den
        if public_coverage_den
        else 0.0
    )
    identity_verified = any(
        item.get("signal") == "Business Identity & Standing" and item.get("used_in_score")
        for item in breakdown
    )
    provider_diversity = len(providers)

    gates = {
        "coverage": licensed_coverage >= MIN_RATING_COVERAGE,
        "entity_identity": identity_verified,
        "provider_diversity": provider_diversity >= MIN_PROVIDER_DIVERSITY,
        "model_approval": model_release_stage == "validated",
    }
    evidence_ready = all(gates[key] for key in ("coverage", "entity_identity", "provider_diversity"))

    public_track = public_usable_weight > 0
    if public_track:
        scoring_track = "public"
        coverage = public_coverage
        scoring_status = "limited" if coverage < LIMITED_COVERAGE_THRESHOLD else "rated"
        rating, color, band_summary = _rating(model_output_score)
        if scoring_status == "limited":
            summary = (
                "Limited data coverage. Score uses the available public "
                f"(and licensed, if present) signals covering {coverage:.0%} of retrieved inputs."
            )
        else:
            summary = band_summary
        private_score = model_output_score
        public_confidence = (
            public_usable_weight / PUBLIC_WEIGHT_TOTAL if PUBLIC_WEIGHT_TOTAL else 0.0
        )
        if resolution_confidence is not None and resolution_confidence < 50:
            public_confidence *= 0.55
        elif resolution_confidence is not None and resolution_confidence < 75:
            public_confidence *= 0.80
        modelled_fraction = modelled_weight / scored_weight if scored_weight else 0.0
        if modelled_fraction >= 0.5:
            public_confidence *= 0.70
        evidence_confidence = max(0.0, min(1.0, public_confidence))
        model_version = "public-v1" if not licensed_usable_weight else "public-v1+licensed-v4"
    elif licensed_usable_weight > 0:
        scoring_track = "licensed"
        coverage = licensed_coverage
        if not evidence_ready:
            scoring_status = "insufficient_data"
            rating = "Preliminary"
            color = PRELIMINARY_COLOR
            failed = [key.replace("_", " ") for key, passed in gates.items() if key != "model_approval" and not passed]
            summary = "No rating was issued. Required evidence gates not met: " + ", ".join(failed) + "."
        elif model_release_stage != "validated":
            scoring_status = "validation_hold"
            rating = "Validation hold"
            color = PRELIMINARY_COLOR
            summary = "Evidence gates passed, but the model is in shadow mode pending documented out-of-time validation and approval."
        else:
            scoring_status = "rated"
            rating, color, summary = _rating(model_output_score)
        private_score = model_output_score if scoring_status == "rated" else UNRATED_SCORE
        average_match = sum(match_confidences) / len(match_confidences) if match_confidences else 0
        average_freshness = sum(freshness_factors) / len(freshness_factors) if freshness_factors else 0
        evidence_confidence = coverage * min(1, provider_diversity / MIN_PROVIDER_DIVERSITY) * average_match * average_freshness
        model_version = "v4.0"
    else:
        scoring_track = "none"
        coverage = 0.0
        scoring_status = "unrated"
        rating = "Unrated"
        color = PRELIMINARY_COLOR
        summary = "No rating was issued because no usable live or modelled signals were available."
        private_score = UNRATED_SCORE
        evidence_confidence = 0.0
        model_version = "public-v1"
        model_output_score = None

    category_summary: dict[str, dict[str, Any]] = {}
    for category, scores in category_scores.items():
        category_weight = sum(weight for _, weight in scores)
        average = sum(score * weight for score, weight in scores) / category_weight
        category_summary[category] = {
            "label": CATEGORY_LABELS.get(category, category.title()),
            "score": round(average, 1),
            "signal_count": len(scores),
            "weight_coverage": round(category_weight, 4),
        }

    real_count = sum(1 for signal in signals if not signal.get("is_simulated", True))
    scored_count = sum(1 for item in breakdown if item.get("used_in_score"))
    simulated_count = len(signals) - real_count
    live_count = sum(1 for item in breakdown if item.get("availability_status") == "live")
    modelled_count = sum(1 for item in breakdown if item.get("availability_status") == "modelled")
    unavailable_count = sum(1 for item in breakdown if item.get("availability_status") == "unavailable")
    not_applicable_count = sum(1 for item in breakdown if item.get("availability_status") == "not_applicable")

    breakdown.sort(key=lambda item: (item["weight"], item["signal"]), reverse=True)
    return {
        "private_score": private_score,
        "scoring_status": scoring_status,
        "rating": rating,
        "color": color,
        "summary": summary,
        "breakdown": breakdown,
        "category_summary": category_summary,
        "risk_flags": risk_flags,
        "meta": {
            "total_signals": len(signals),
            "real_signals": real_count,
            "scored_signals": scored_count,
            "simulated_signals": simulated_count,
            "confidence": round(evidence_confidence, 4),
            "evidence_coverage": round(coverage, 4),
            "scored_weight": round(scored_weight, 4),
            "minimum_rating_coverage": MIN_RATING_COVERAGE,
            "minimum_provider_diversity": MIN_PROVIDER_DIVERSITY,
            "provider_diversity": provider_diversity,
            "providers_used": sorted(providers),
            "identity_verified": identity_verified,
            "gates": gates,
            "scoring_status": scoring_status,
            "scoring_track": scoring_track,
            "model_release_stage": model_release_stage,
            "model_version": model_version,
            "model_output_score": model_output_score,
            "unusable_signals": unusable_signals,
            "resolution_confidence": resolution_confidence,
            "data_coverage": {
                "live": live_count,
                "modelled": modelled_count,
                "unavailable": unavailable_count,
                "notApplicable": not_applicable_count,
            },
            "disclaimer": (
                f"{scored_count} usable signal(s) cover {coverage:.0%} of retrieved inputs. "
                "Unavailable and not-applicable sources are excluded from the published score."
            ),
        },
    }

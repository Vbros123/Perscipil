"""PrivateLens scoring engine v4 with explicit evidence and release gates."""
from __future__ import annotations

from typing import Any

from services.evidence import SIGNAL_SPECS

WEIGHTS = {name: spec["weight"] for name, spec in SIGNAL_SPECS.items()}

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


def _rating(score: int) -> tuple[str, str, str]:
    for threshold, label, color, summary in RATING_BANDS:
        if score >= threshold:
            return label, color, summary
    return RATING_BANDS[-1][1], RATING_BANDS[-1][2], RATING_BANDS[-1][3]


def compute_score(signals: list[dict[str, Any]], model_release_stage: str = "shadow") -> dict[str, Any]:
    scored_weight = 0.0
    weighted_sum = 0.0
    breakdown: list[dict[str, Any]] = []
    category_scores: dict[str, list[tuple[float, float]]] = {}
    risk_flags: list[str] = []
    providers: set[str] = set()
    match_confidences: list[float] = []
    freshness_factors: list[float] = []
    configured_weight_total = sum(WEIGHTS.values())

    for signal in signals:
        name = signal.get("signal", "")
        raw = max(0, min(100, float(signal.get("raw_score", 50))))
        weight = WEIGHTS.get(name, 0.0)
        category = signal.get("category", "operational")
        is_simulated = signal.get("is_simulated", True)
        is_scored = bool(weight and not is_simulated and signal.get("is_scored", True))

        if is_scored:
            weighted_sum += raw * weight
            scored_weight += weight
            category_scores.setdefault(category, []).append((raw, weight))
            if signal.get("provider_key"):
                providers.add(signal["provider_key"])
            match_confidences.append(float(signal.get("entity_match_confidence", 0)))
            max_age = SIGNAL_SPECS[name]["max_age_days"]
            freshness_days = max(0, float(signal.get("freshness_days", max_age)))
            freshness_factors.append(max(0, 1 - freshness_days / (max_age * 2)))

        breakdown.append({
            **{key: value for key, value in signal.items() if key not in {"is_scored"}},
            "signal": name,
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category.title()),
            "raw_score": round(raw, 1),
            "weight": weight,
            "weight_pct": f"{weight * 100:.0f}%" if weight else "Context",
            "effective_weight": weight if is_scored else 0.0,
            "weighted_contribution": round(raw * weight, 2) if is_scored else 0.0,
            "used_in_score": is_scored,
        })

        if is_scored and raw < 30 and weight >= 0.15:
            risk_flags.append(f"{name}: verified evidence is in the severe-risk range ({raw:.0f}/100)")

    normalized = weighted_sum / scored_weight if scored_weight else 50
    private_score = max(0, min(1000, int(round(normalized * 10))))
    coverage = scored_weight / configured_weight_total if configured_weight_total else 0.0
    identity_verified = any(
        item.get("signal") == "Business Identity & Standing" and item.get("used_in_score")
        for item in breakdown
    )
    provider_diversity = len(providers)

    gates = {
        "coverage": coverage >= MIN_RATING_COVERAGE,
        "entity_identity": identity_verified,
        "provider_diversity": provider_diversity >= MIN_PROVIDER_DIVERSITY,
        "model_approval": model_release_stage == "validated",
    }
    evidence_ready = all(gates[key] for key in ("coverage", "entity_identity", "provider_diversity"))
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
        rating, color, summary = _rating(private_score)

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
    average_match = sum(match_confidences) / len(match_confidences) if match_confidences else 0
    average_freshness = sum(freshness_factors) / len(freshness_factors) if freshness_factors else 0
    evidence_confidence = coverage * min(1, provider_diversity / MIN_PROVIDER_DIVERSITY) * average_match * average_freshness

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
            "model_release_stage": model_release_stage,
            "model_version": "v4.0",
            "disclaimer": (
                f"{scored_count} verified signals cover {coverage:.0%} of model weight across "
                f"{provider_diversity} licensed provider(s). Unavailable and context-only inputs are excluded."
            ),
        },
    }

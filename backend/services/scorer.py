"""PrivateLens scoring engine v6: evidence-weighted PrivateScore.

PrivateScore measures the polarity of *available* evidence. It is not a count
of internet mentions. Missing inputs stay missing: they do not become 100, 50,
or any other invented strength.

Published score
    quality-weighted mean of usable signals, then capped by an evidence ceiling.

Ceiling
    1000 * (CEILING_FLOOR + (1 - CEILING_FLOOR) * coverage ** CEILING_EXP)
    * quality_mix_factor, then public-only max.

    coverage = sum(spec_weight * quality_multiplier) / sum(applicable spec weights)

    not_applicable (e.g. SEC for a private company) is excluded from the
    denominator so absence of an inapplicable source is neither good nor bad.

    quality_mix_factor = 0.70 + 0.30 * (high+medium effective / scored effective)
    so a report built only from low-quality keyword hits cannot reach the
    ceiling implied by coverage alone.

Confidence is a separate quantity: how much reliable evidence was actually
retrieved. A 700 with 20% confidence is not the same as a 700 with 90%.
"""
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
SUPPORTING_CATEGORIES = frozenset({"digital", "sentiment"})
MAX_SUPPORTING_SHARE = 0.30

# Quality multipliers applied to spec weight before the signal can move the score.
# Modelled estimates are first-class labelled inputs, never equal to verified live.
QUALITY_MULTIPLIER = {
    "high": 1.00,
    "medium": 0.70,
    "low": 0.40,
    "modelled": 0.25,
    "unavailable": 0.0,
    "not_applicable": 0.0,
}

# Ceiling curve. At coverage=0 the model does not publish; the floor only
# applies once at least one usable signal exists. 0.32 means a single perfect
# weak signal cannot exceed roughly a third of the scale even before the
# quality mix and public-only haircuts.
CEILING_FLOOR = 0.32
CEILING_EXP = 1.05
# Internet-only reports cannot claim a perfect PrivateScore. Licensed verified
# evidence is required to unlock the top of the scale.
PUBLIC_ONLY_MAX = 820
# 1000 requires broad, mostly high-quality coverage — not one strong keyword hit.
PERFECT_COVERAGE = 0.85
PERFECT_HIGH_QUALITY_SHARE = 0.50

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


def _evidence_quality(signal: dict[str, Any], status: str, spec: dict[str, Any]) -> str:
    explicit = signal.get("evidence_quality") or signal.get("evidenceQuality")
    allowed = set(QUALITY_MULTIPLIER)
    if isinstance(explicit, str) and explicit in allowed:
        return explicit
    if status == "modelled":
        return "modelled"
    if status == "unavailable":
        return "unavailable"
    if status == "not_applicable":
        return "not_applicable"
    hint = spec.get("quality_hint")
    if hint in allowed:
        return hint
    if spec.get("track") == "licensed":
        return "high"
    return "low"


def _evidence_role(status: str, raw: float | None) -> str:
    if status == "unavailable":
        return "missing"
    if status == "not_applicable":
        return "not_applicable"
    if status == "modelled":
        return "modelled"
    if raw is None:
        return "missing"
    if raw >= 70:
        return "positive"
    if raw <= 40:
        return "negative"
    return "neutral"


def _quality_label(high: float, medium: float, low: float, modelled: float, scored: float) -> str:
    if scored <= 0:
        return "unavailable"
    if high / scored >= 0.50:
        return "high"
    if (high + medium) / scored >= 0.45:
        return "medium"
    if modelled / scored >= 0.50:
        return "modelled"
    return "low"


def _category_explanation(category: str, used: list[dict[str, Any]], missing: list[str], quality: str) -> str:
    names = ", ".join(item["signal"] for item in used) if used else "no scored inputs"
    if not used:
        if category == "financial":
            return (
                "Verified financial information is unavailable. Missing filings or credit files "
                "are not treated as proof of strength or of distress."
            )
        if category == "legal":
            return (
                "No legal-standing evidence was scored. Absence of a public litigation feed "
                "is not evidence that no legal risk exists."
            )
        if category == "digital":
            return "No digital-identity source was resolved, so web presence did not affect the score."
        if category == "sentiment":
            return "No usable news polarity was retrieved, so sentiment did not affect the score."
        return "No operational evidence was scored for this category."
    if category == "digital":
        return (
            f"Digital presence ({names}) is a supporting identity signal, not a financial-health "
            f"measure. Evidence quality: {quality}."
        )
    if category == "sentiment":
        return (
            f"Market sentiment ({names}) uses public keyword context and cannot dominate the score. "
            f"Evidence quality: {quality}."
        )
    if category == "financial":
        extra = f" Unscored financial inputs: {', '.join(missing)}." if missing else ""
        return f"Financial evidence uses {names}.{extra} Evidence quality: {quality}."
    if missing:
        return (
            f"Available {CATEGORY_LABELS.get(category, category).lower()} evidence uses {names}. "
            f"Unscored in this category: {', '.join(missing)}. Evidence quality: {quality}."
        )
    return f"Available evidence uses {names}. Evidence quality: {quality}."


def _public_summary(observed: float, score: int, coverage: float, quality: str, limited: bool) -> str:
    if limited or coverage < LIMITED_COVERAGE_THRESHOLD:
        return (
            "Limited public evidence is available. The score reflects the polarity of retrieved "
            "signals, not a complete financial picture, and confidence stays low until more "
            "verified sources are present."
        )
    if quality in {"low", "modelled"}:
        return (
            "Available operational and market signals are mostly low-reliability public sources. "
            "They are not a substitute for verified credit, cash-flow, or legal evidence."
        )
    if observed >= 70:
        return (
            f"Available evidence is comparatively constructive (observed strength {observed:.0f}/100), "
            f"with {coverage:.0%} applicable coverage and {quality} evidence quality."
        )
    if observed <= 40:
        return (
            f"Available evidence leans negative (observed strength {observed:.0f}/100). "
            "Treat this as a research flag, not a bureau rating."
        )
    return (
        f"Available evidence is mixed (observed strength {observed:.0f}/100; published {score}/1000). "
        "Public financial evidence remains limited, which keeps confidence below a full underwrite."
    )


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
    category_scores: dict[str, list[tuple[float, float, str]]] = {}
    category_missing: dict[str, list[str]] = {}
    risk_flags: list[str] = []
    providers: set[str] = set()
    match_confidences: list[float] = []
    freshness_factors: list[float] = []
    unusable_signals: list[str] = []
    used_rows: list[dict[str, Any]] = []
    quality_weight = {"high": 0.0, "medium": 0.0, "low": 0.0, "modelled": 0.0}
    public_applicable = 0.0
    licensed_applicable = 0.0
    effective_scored = 0.0

    for signal in signals:
        name = signal.get("signal", "")
        spec = SIGNAL_SPECS.get(name, {})
        weight = spec.get("weight", WEIGHTS.get(name, 0.0))
        track = spec.get("track")
        category = signal.get("category", spec.get("category", "operational"))
        status = _availability_status(signal)
        quality = _evidence_quality(signal, status, spec)
        wants_score = bool(signal.get("is_scored", True))
        raw = _finite_score(signal.get("raw_score"))
        usable_value = raw is not None
        role = spec.get("role") or ("supporting" if category in SUPPORTING_CATEGORIES else "core")
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

        quality_mult = QUALITY_MULTIPLIER.get(quality, 0.0)
        if status == "modelled":
            quality_mult = min(quality_mult, QUALITY_MULTIPLIER["modelled"])
            quality = "modelled"
        effective = weight * quality_mult if used else 0.0

        if status != "not_applicable" and weight:
            if track == "licensed":
                licensed_applicable += weight
            else:
                public_applicable += weight

        if used:
            used_rows.append({
                "signal": name,
                "raw": raw,
                "weight": weight,
                "effective": effective,
                "category": category,
                "quality": quality,
                "role": role,
                "status": status,
                "track": track,
            })
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
            if quality in quality_weight:
                quality_weight[quality] += effective
        elif weight and status == "unavailable":
            if track == "public":
                public_unavailable_weight += weight
            elif track == "licensed":
                licensed_unavailable_weight += weight
            category_missing.setdefault(category, []).append(name)

        evidence_role = _evidence_role(status, raw if used else None)
        display_raw = round(raw, 1) if usable_value else None
        breakdown.append({
            **{key: value for key, value in signal.items() if key not in {"is_scored"}},
            "signal": name,
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category.title()),
            "raw_score": display_raw,
            "weight": weight,
            "weight_pct": f"{weight * 100:.0f}%" if weight else "Context",
            "effective_weight": effective,
            "weighted_contribution": 0.0,
            "used_in_score": used,
            "value_usable": usable_value,
            "availability_status": status,
            "status": status,
            "track": track,
            "evidence_quality": quality,
            "evidenceQuality": quality,
            "evidence_role": evidence_role,
            "signal_role": role,
        })

    licensed_used = any(row["track"] == "licensed" for row in used_rows)
    applicable_weight = public_applicable + (licensed_applicable if licensed_used else 0.0)

    supporting = [row for row in used_rows if row["role"] == "supporting" or row["category"] in SUPPORTING_CATEGORIES]
    core = [row for row in used_rows if row not in supporting]
    supporting_effective = sum(row["effective"] for row in supporting)
    core_effective = sum(row["effective"] for row in core)
    total_effective = supporting_effective + core_effective
    if core_effective > 0 and total_effective > 0 and supporting_effective / total_effective > MAX_SUPPORTING_SHARE:
        scale = (MAX_SUPPORTING_SHARE * core_effective) / (supporting_effective * (1 - MAX_SUPPORTING_SHARE))
        for row in supporting:
            row["effective"] *= scale
        total_effective = sum(row["effective"] for row in used_rows)

    for row in used_rows:
        weighted_sum += row["raw"] * row["effective"]
        scored_weight += row["weight"]
        effective_scored += row["effective"]
        category_scores.setdefault(row["category"], []).append((row["raw"], row["effective"], row["quality"]))
        if row["raw"] < 30 and row["weight"] >= 0.15:
            quality = row["quality"]
            if quality in {"low", "modelled"}:
                risk_flags.append(
                    f"{row['signal']}: available public evidence is in a weak range "
                    f"({row['raw']:.0f}/100). Treat as a research flag, not a verified finding."
                )
            else:
                risk_flags.append(
                    f"{row['signal']}: available evidence is in the severe-risk range ({row['raw']:.0f}/100)"
                )

    contribution_by_name = {
        row["signal"]: round(row["raw"] * row["effective"], 2) for row in used_rows
    }
    effective_by_name = {row["signal"]: row["effective"] for row in used_rows}
    for item in breakdown:
        item["effective_weight"] = effective_by_name.get(item["signal"], 0.0)
        item["weighted_contribution"] = contribution_by_name.get(item["signal"], 0.0)

    observed = weighted_sum / effective_scored if effective_scored else None
    coverage = effective_scored / applicable_weight if applicable_weight else 0.0
    high_share = quality_weight["high"] / effective_scored if effective_scored else 0.0
    medium_share = quality_weight["medium"] / effective_scored if effective_scored else 0.0
    quality_mix = 0.70 + 0.30 * min(1.0, high_share + medium_share)
    overall_quality = _quality_label(
        quality_weight["high"],
        quality_weight["medium"],
        quality_weight["low"],
        quality_weight["modelled"],
        effective_scored,
    )

    # Evidence ceiling: thin or low-quality evidence cannot publish 1000 even
    # when the few retrieved signals happen to be numerically high.
    if observed is None:
        ceiling = 0.0
        uncapped = None
        model_output_score = None
    else:
        ceiling = 1000.0 * (CEILING_FLOOR + (1.0 - CEILING_FLOOR) * (coverage ** CEILING_EXP)) * quality_mix
        if licensed_usable_weight <= 0:
            ceiling = min(ceiling, float(PUBLIC_ONLY_MAX))
        if coverage < PERFECT_COVERAGE or high_share < PERFECT_HIGH_QUALITY_SHARE:
            ceiling = min(ceiling, 950.0)
        uncapped = max(0, min(1000, int(round(observed * 10))))
        model_output_score = max(0, min(1000, int(round(min(observed * 10, ceiling)))))

    licensed_coverage = (
        licensed_usable_weight / LICENSED_WEIGHT_TOTAL if LICENSED_WEIGHT_TOTAL else 0.0
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

    public_track = public_usable_weight > 0 and licensed_usable_weight == 0
    mixed_track = public_usable_weight > 0 and licensed_usable_weight > 0
    if public_track or mixed_track:
        scoring_track = "public" if public_track else "public+licensed"
        scoring_status = "limited" if coverage < LIMITED_COVERAGE_THRESHOLD else "rated"
        rating, color, band_summary = _rating(model_output_score)
        summary = _public_summary(observed or 0, model_output_score or 0, coverage, overall_quality, scoring_status == "limited")
        if scoring_status != "limited" and licensed_usable_weight:
            summary = band_summary
        private_score = model_output_score
        live_fraction = 1.0 - (modelled_weight / scored_weight if scored_weight else 0.0)
        public_confidence = coverage * (0.45 + 0.55 * live_fraction) * quality_mix
        if licensed_usable_weight <= 0:
            public_confidence *= 0.72  # public internet sources cannot claim underwriting confidence
        if resolution_confidence is not None and resolution_confidence < 50:
            public_confidence *= 0.55
        elif resolution_confidence is not None and resolution_confidence < 75:
            public_confidence *= 0.80
        evidence_confidence = max(0.0, min(1.0, public_confidence))
        model_version = "public-v2" if public_track else "public-v2+licensed-v4"
    elif licensed_usable_weight > 0:
        scoring_track = "licensed"
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
        scoring_track = "licensed"
    else:
        scoring_track = "none"
        scoring_status = "unrated"
        rating = "Insufficient public evidence"
        color = PRELIMINARY_COLOR
        summary = "PrivateLens could not obtain enough reliable external evidence to calculate a meaningful PrivateScore for this company."
        private_score = UNRATED_SCORE
        evidence_confidence = 0.0
        model_version = "public-v2"
        model_output_score = None
        observed = None

    category_summary: dict[str, dict[str, Any]] = {}
    for category, scores in category_scores.items():
        category_weight = sum(weight for _, weight, _ in scores)
        average = sum(score * weight for score, weight, _ in scores) / category_weight
        qualities = [quality for _, _, quality in scores]
        if "high" in qualities:
            cat_quality = "high"
        elif "medium" in qualities:
            cat_quality = "medium"
        elif "modelled" in qualities:
            cat_quality = "modelled"
        else:
            cat_quality = "low"
        used_names = [row for row in used_rows if row["category"] == category]
        category_summary[category] = {
            "label": CATEGORY_LABELS.get(category, category.title()),
            "score": round(average, 1),
            "signal_count": len(scores),
            "weight_coverage": round(category_weight, 4),
            "evidence_quality": cat_quality,
            "evidenceQuality": cat_quality,
            "coverage": round(category_weight / applicable_weight, 4) if applicable_weight else 0.0,
            "explanation": _category_explanation(
                category,
                used_names,
                category_missing.get(category, []),
                cat_quality,
            ),
        }
    for category, missing in category_missing.items():
        if category in category_summary:
            continue
        category_summary[category] = {
            "label": CATEGORY_LABELS.get(category, category.title()),
            "score": None,
            "signal_count": 0,
            "weight_coverage": 0.0,
            "evidence_quality": "unavailable",
            "evidenceQuality": "unavailable",
            "coverage": 0.0,
            "explanation": _category_explanation(category, [], missing, "unavailable"),
        }

    real_count = sum(1 for signal in signals if not signal.get("is_simulated", True))
    scored_count = sum(1 for item in breakdown if item.get("used_in_score"))
    simulated_count = len(signals) - real_count
    live_count = sum(1 for item in breakdown if item.get("availability_status") == "live")
    modelled_count = sum(1 for item in breakdown if item.get("availability_status") == "modelled")
    unavailable_count = sum(1 for item in breakdown if item.get("availability_status") == "unavailable")
    not_applicable_count = sum(1 for item in breakdown if item.get("availability_status") == "not_applicable")
    coverage_percent = round(coverage * 100)

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
            "evidence_quality": overall_quality,
            "observed_strength": round(observed, 2) if observed is not None else None,
            "score_ceiling": round(ceiling) if observed is not None else None,
            "uncapped_score": uncapped,
            "scored_weight": round(scored_weight, 4),
            "effective_scored_weight": round(effective_scored, 4),
            "applicable_weight": round(applicable_weight, 4),
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
                "totalSignals": len(signals),
                "live": live_count,
                "liveSignals": live_count,
                "modelled": modelled_count,
                "modelledSignals": modelled_count,
                "unavailable": unavailable_count,
                "unavailableSignals": unavailable_count,
                "notApplicable": not_applicable_count,
                "notApplicableSignals": not_applicable_count,
                "coveragePercent": coverage_percent,
            },
            "disclaimer": (
                f"{scored_count} usable signal(s) cover {coverage:.0%} of applicable inputs after "
                "evidence-quality weighting. Unavailable and not-applicable sources are excluded "
                "from the published score and are never treated as positive evidence."
            ),
        },
    }

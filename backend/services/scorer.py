"""
PrivateLens Scoring Engine v3
- Weighted multi-signal model
- Confidence based on verified, score-eligible weight coverage
- Category-level sub-scores
- Risk flag detection
- Human-readable narrative generation
"""
from typing import List, Dict, Any

# Signal weights — higher = more predictive of financial distress
# Based on academic literature on private company financial health indicators
WEIGHTS: dict[str, float] = {
    "Open Banking Payment Flows":       0.13,
    "B2B Payment Behavior":             0.12,
    "Job Posting Velocity":             0.11,
    "UCC Filings & Lien Activity":      0.10,
    "Court Records & Litigation":       0.09,
    "News & Media Sentiment":           0.08,
    "Employee & Customer Reviews":      0.07,
    "Insider & Employee Sentiment":     0.06,
    "Web Traffic Trends":               0.06,
    "Brand Legitimacy & Web Presence":  0.05,
    "SEC / Regulatory Filings":         0.05,
    "Social Media Activity":            0.04,
    "Supply Chain & Vendor Signals":    0.03,
    "Government Contract Awards":       0.01,
}

CATEGORY_LABELS = {
    "financial":    "Financial Health",
    "operational":  "Operational Signals",
    "legal":        "Legal & Regulatory",
    "sentiment":    "Market Sentiment",
    "digital":      "Digital Presence",
}

RATING_BANDS = [
    (850, "Exceptional", "#00E5A0", "This company exhibits outstanding financial health across nearly all signal categories. Very low risk profile — strong candidate for lending, investment, or partnership."),
    (700, "Strong",      "#00C896", "Strong fundamentals with minor areas to monitor. Low risk overall. Suitable for most financial and operational engagements."),
    (550, "Adequate",    "#4F98A3", "Solid baseline with some mixed signals. Moderate risk — worth deeper due diligence before significant commitments."),
    (400, "Weak",        "#E8AF34", "Multiple warning indicators present. Elevated risk. Proceed with caution and require additional documentation."),
    (250, "Distressed",  "#BB653B", "Significant distress signals across several categories. High risk — conservative position recommended."),
    (0,   "Critical",    "#D163A7", "Severe multi-category distress signals. Extreme risk — do not proceed without comprehensive independent verification."),
]

MIN_RATING_COVERAGE = 0.50
PRELIMINARY_COLOR = "#64748B"


def _rating(score: int) -> tuple[str, str, str]:
    for threshold, label, color, summary in RATING_BANDS:
        if score >= threshold:
            return label, color, summary
    return RATING_BANDS[-1][1], RATING_BANDS[-1][2], RATING_BANDS[-1][3]


def compute_score(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored_weight = 0.0
    weighted_sum = 0.0
    breakdown = []
    category_scores: dict[str, list[tuple[float, float]]] = {}
    risk_flags = []
    configured_weight_total = sum(WEIGHTS.values())

    for sig in signals:
        name = sig.get("signal", "")
        raw = float(sig.get("raw_score", 50))
        weight = WEIGHTS.get(name, 0.03)
        cat = sig.get("category", "operational")
        is_simulated = sig.get("is_simulated", True)
        is_scored = not is_simulated and sig.get("is_scored", True)

        if is_scored:
            weighted_sum += raw * weight
            scored_weight += weight
            category_scores.setdefault(cat, []).append((raw, weight))

        bd = {
            "signal": name,
            "icon": sig.get("icon", "📊"),
            "category": cat,
            "category_label": CATEGORY_LABELS.get(cat, cat.title()),
            "raw_score": round(raw, 1),
            "weight": weight,
            "weight_pct": f"{weight * 100:.0f}%",
            "effective_weight": weight if is_scored else 0.0,
            "weighted_contribution": round(raw * weight, 2) if is_scored else 0.0,
            "display": sig.get("display", ""),
            "insight": sig.get("insight", ""),
            "is_simulated": is_simulated,
            "used_in_score": is_scored,
            "source_url": sig.get("source_url", ""),
        }
        breakdown.append(bd)

        # Flag severe signals
        if is_scored and raw < 30 and weight >= 0.08:
            risk_flags.append(f"⚠️ {name}: score {raw:.0f}/100 — high-weight signal in distress range")

    # The score summarizes only score-eligible observed data. Unavailable inputs are excluded.
    normalized = (weighted_sum / scored_weight) if scored_weight > 0 else 50
    private_score = max(0, min(1000, int(round(normalized * 10))))
    coverage = round(scored_weight / configured_weight_total, 4) if configured_weight_total else 0.0
    scoring_status = "rated" if coverage >= MIN_RATING_COVERAGE else "insufficient_data"

    if scoring_status == "rated":
        rating, color, summary = _rating(private_score)
    else:
        rating = "Preliminary"
        color = PRELIMINARY_COLOR
        summary = (
            f"Verified score coverage is {coverage:.0%}, below the {MIN_RATING_COVERAGE:.0%} "
            "minimum required for a financial-health rating. The displayed evidence score uses "
            "observed inputs only and must not be used as a standalone decision."
        )

    # Category sub-scores
    category_summary = {}
    for cat, scores in category_scores.items():
        category_weight = sum(weight for _, weight in scores)
        avg = sum(score * weight for score, weight in scores) / category_weight
        category_summary[cat] = {
            "label": CATEGORY_LABELS.get(cat, cat.title()),
            "score": round(avg, 1),
            "signal_count": len(scores),
            "weight_coverage": round(category_weight, 4),
        }

    # Distinguish live context from live data that is sufficiently resolved to affect the score.
    real_count = sum(1 for s in signals if not s.get("is_simulated", True))
    sim_count = len(signals) - real_count
    scored_count = sum(
        1 for s in signals
        if not s.get("is_simulated", True) and s.get("is_scored", True)
    )

    # Sort breakdown: highest weight first
    breakdown.sort(key=lambda x: x["weight"], reverse=True)

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
            "simulated_signals": sim_count,
            "confidence": coverage,
            "scored_weight": round(scored_weight, 4),
            "minimum_rating_coverage": MIN_RATING_COVERAGE,
            "scoring_status": scoring_status,
            "model_version": "v3.0",
            "disclaimer": (
                f"{scored_count} of {len(signals)} signals are observed and score-eligible, "
                f"covering {coverage:.0%} of configured model weight. {sim_count} unavailable "
                "signals are excluded from the score."
            ),
        },
    }

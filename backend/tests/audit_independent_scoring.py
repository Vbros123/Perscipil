"""Independent re-derivation of PrivateLens scoring, written from the documented
model rather than from services.scorer, so the two can be cross-checked.

Run: PYTHONPATH=. python tests/audit_independent_scoring.py
"""
from __future__ import annotations

import itertools
import math
import random
from datetime import datetime, timedelta, timezone

from services.evidence import (
    CompanyIdentity,
    EntityMatch,
    EvidenceBundle,
    GatewayEvidenceResponse,
    Observation,
    ProviderDescriptor,
    build_licensed_signals,
)
from services.scorer import compute_score

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)

# Independently transcribed from README / ops docs, NOT imported from the app.
EXPECTED_WEIGHTS = {
    "Commercial Credit Risk": 0.30,
    "B2B Payment Behavior": 0.20,
    "Cash Flow & Liquidity": 0.20,
    "Business Identity & Standing": 0.15,
    "Liens, Bankruptcy & Litigation": 0.15,
}
EXPECTED_MAX_AGE = {
    "Commercial Credit Risk": 120,
    "B2B Payment Behavior": 120,
    "Cash Flow & Liquidity": 45,
    "Business Identity & Standing": 180,
    "Liens, Bankruptcy & Litigation": 120,
}
EXPECTED_BANDS = [
    (850, "Exceptional"), (700, "Strong"), (550, "Adequate"),
    (400, "Weak"), (250, "Distressed"), (0, "Critical"),
]

failures: list[str] = []
checks = 0


def check(condition: bool, label: str, detail: str = "") -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(f"{label}{(' :: ' + detail) if detail else ''}")


def independent_score(scored: list[tuple[str, float, float]]) -> dict:
    """scored = [(signal_name, raw_0_100, freshness_days)]. Pure re-derivation."""
    total_cfg = sum(EXPECTED_WEIGHTS.values())
    wsum = sum(raw * EXPECTED_WEIGHTS[n] for n, raw, _ in scored)
    wgt = sum(EXPECTED_WEIGHTS[n] for n, _, _ in scored)
    normalized = wsum / wgt if wgt else 50.0
    score = max(0, min(1000, int(round(normalized * 10))))
    coverage = wgt / total_cfg
    rating = next(label for thr, label in EXPECTED_BANDS if score >= thr)
    return {"score": score, "coverage": coverage, "rating": rating, "normalized": normalized}


# ── Builders ──────────────────────────────────────────────────────────────────

IDENT = CompanyIdentity(legal_name="Acme Manufacturing LLC", country_code="US",
                        registration_number="A-123")


def obs(metric, value, days_old=1, **kw):
    return Observation(evidence_id=f"e:{metric}:{days_old}:{value}", metric=metric, value=value,
                       observed_at=NOW - timedelta(days=days_old), fetched_at=NOW,
                       source_ref=f"urn:{metric}", **kw)


def bund(provider, observations, confidence=0.99, status="exact",
         matched_fields=("legal_name", "registration_number")):
    return EvidenceBundle(
        provider=ProviderDescriptor(key=provider, name=provider.title(),
                                    license_reference=f"contract-{provider}",
                                    permitted_use=["company_intelligence"]),
        entity_match=EntityMatch(provider_entity_id=f"{provider}-1", legal_name="Acme Manufacturing LLC",
                                 country_code="US", registration_number="A-123",
                                 match_status=status, confidence=confidence,
                                 matched_fields=list(matched_fields)),
        observations=observations)


def resp(*bundles):
    return GatewayEvidenceResponse(schema="privatelens.evidence.v2", request_id="request-abcdefgh",
                                   generated_at=NOW, bundles=list(bundles))


def run(*bundles, stage="validated"):
    signals, audit = build_licensed_signals(resp(*bundles), IDENT, now=NOW)
    return compute_score(signals, model_release_stage=stage), audit


# ── 1. Transform-level verification (independent recomputation) ───────────────

def t_credit_transform():
    for value, smin, smax, hib, expected in [
        (82, 0, 100, True, 82.0), (0, 0, 100, True, 0.0), (100, 0, 100, True, 100.0),
        (50, 0, 100, False, 50.0), (20, 0, 100, False, 80.0),
        (1, 1, 100, True, 0.0), (100, 1, 100, True, 100.0),
        (300, 0, 100, True, 100.0),      # above scale -> clamp
        (-50, 0, 100, True, 0.0),        # below scale -> clamp
        (450, 0, 700, True, 450 / 700 * 100),
    ]:
        r, _ = run(bund("creditsafe", [obs("creditsafe.credit_score", value, scale_min=smin,
                                           scale_max=smax, higher_is_better=hib)]))
        got = next(i for i in r["breakdown"] if i["signal"] == "Commercial Credit Risk")["raw_score"]
        check(abs(got - round(expected, 2)) < 0.02,
              "credit transform", f"value={value} scale=[{smin},{smax}] hib={hib} expected={expected:.2f} got={got}")


def t_payment_transform():
    # days_beyond_terms -> 100 - days*2.5, clamped
    for days, expected in [(0, 100.0), (4, 90.0), (10, 75.0), (40, 0.0), (100, 0.0), (-5, 100.0)]:
        r, _ = run(bund("creditsafe", [obs("creditsafe.days_beyond_terms", days, unit="days")]))
        got = next(i for i in r["breakdown"] if i["signal"] == "B2B Payment Behavior")["raw_score"]
        check(abs(got - expected) < 0.02, "payment dbt transform",
              f"days={days} expected={expected} got={got}")
    # payment_index takes precedence over days_beyond_terms
    r, _ = run(bund("creditsafe", [
        obs("creditsafe.payment_index", 30, scale_min=0, scale_max=100, higher_is_better=True),
        obs("creditsafe.days_beyond_terms", 0)]))
    got = next(i for i in r["breakdown"] if i["signal"] == "B2B Payment Behavior")["raw_score"]
    check(abs(got - 30.0) < 0.02, "payment index precedence", f"expected 30 got {got}")


def t_identity_transform():
    for status, expected in [("active", 100), ("registered", 95), ("inactive", 25),
                             ("dissolved", 10), ("revoked", 5), ("ACTIVE", 100), ("  Active  ", 100)]:
        r, _ = run(bund("middesk", [obs("middesk.registration_status", status)]))
        got = next(i for i in r["breakdown"] if i["signal"] == "Business Identity & Standing")["raw_score"]
        check(abs(got - expected) < 0.02, "identity transform",
              f"status={status!r} expected={expected} got={got}")
    # unknown status must NOT be scored
    r, _ = run(bund("middesk", [obs("middesk.registration_status", "pending")]))
    sig = next(i for i in r["breakdown"] if i["signal"] == "Business Identity & Standing")
    check(sig["used_in_score"] is False, "unknown reg status unscored", f"got {sig}")


def t_legal_transform():
    cases = [
        (0, 0, 0, 0, 100.0), (1, 0, 0, 0, 0.0), (0, 1, 0, 0, 88.0),
        (0, 0, 1, 0, 75.0), (0, 0, 0, 1, 93.0), (0, 4, 0, 0, 55.0),  # lien penalty caps at 45
        (0, 10, 0, 0, 55.0),   # liens penalty caps at 45
        (0, 0, 5, 0, 40.0),    # tax lien penalty caps at 60
        (0, 0, 0, 20, 65.0),   # litigation penalty caps at 35
        (0, 10, 5, 20, 0.0),   # 45+60+35 = 140 -> clamp 0
        (2, 0, 0, 0, 0.0),
    ]
    for bk, li, tx, lit, expected in cases:
        r, _ = run(bund("middesk", [
            obs("middesk.active_bankruptcy_count", bk),
            obs("middesk.recent_lien_count_12m", li),
            obs("middesk.active_tax_lien_count", tx),
            obs("middesk.defendant_litigation_count_24m", lit)]))
        got = next(i for i in r["breakdown"] if i["signal"] == "Liens, Bankruptcy & Litigation")["raw_score"]
        # independent recomputation
        exp = max(0.0, min(100.0, 100 - min(100, bk * 100) - min(45, li * 12)
                           - min(60, tx * 25) - min(35, lit * 7)))
        check(abs(got - exp) < 0.02 and abs(exp - expected) < 0.02, "legal transform",
              f"bk={bk} li={li} tx={tx} lit={lit} expected={expected} indep={exp} got={got}")
    # fewer than 3 metrics -> not scored
    r, _ = run(bund("middesk", [obs("middesk.active_bankruptcy_count", 0),
                                obs("middesk.recent_lien_count_12m", 0)]))
    sig = next(i for i in r["breakdown"] if i["signal"] == "Liens, Bankruptcy & Litigation")
    check(sig["used_in_score"] is False, "legal <3 metrics unscored")


def t_cashflow_transform():
    def indep(cr=None, dscr=None, ocf=None, mc=None, rg=None):
        comps = []
        if cr is not None:
            comps.append(max(0, min(100, cr / 2 * 100)))
        if dscr is not None:
            comps.append(max(0, min(100, dscr / 2 * 100)))
        if ocf is not None:
            comps.append(max(0, min(100, (ocf + 0.10) / 0.35 * 100)))
        if mc is not None:
            comps.append(max(0, min(100, mc / 12 * 100)))
        if rg is not None:
            comps.append(max(0, min(100, (rg + 0.20) / 0.70 * 100)))
        return sum(comps) / len(comps) if len(comps) >= 3 else None

    cases = [
        dict(cr=1.5, dscr=1.4, mc=8), dict(cr=2.0, dscr=2.0, mc=12),
        dict(cr=0.0, dscr=0.0, mc=0), dict(cr=5.0, dscr=9.0, mc=48),
        dict(cr=1.0, dscr=1.0, ocf=0.0, mc=6, rg=0.0),
        dict(cr=1.0, dscr=1.0, ocf=-0.50, mc=6, rg=-0.90),
        dict(cr=1.0, dscr=1.0, ocf=0.25, mc=6, rg=0.50),
        dict(cr=-3.0, dscr=-1.0, mc=-5),
    ]
    metric_of = {"cr": "codat.current_ratio", "dscr": "codat.debt_service_coverage_ratio",
                 "ocf": "codat.operating_cash_flow_margin", "mc": "codat.months_cash_on_hand",
                 "rg": "codat.revenue_growth_yoy"}
    for kwargs in cases:
        r, _ = run(bund("codat", [obs(metric_of[k], v) for k, v in kwargs.items()]))
        sig = next(i for i in r["breakdown"] if i["signal"] == "Cash Flow & Liquidity")
        exp = indep(**kwargs)
        if exp is None:
            check(sig["used_in_score"] is False, "cashflow <3 comps unscored", str(kwargs))
        else:
            # compute_score reports raw_score rounded to 1dp for display.
            check(abs(sig["raw_score"] - round(exp, 1)) < 0.051, "cashflow transform",
                  f"{kwargs} expected={exp:.4f} got={sig['raw_score']}")


# ── 2. Aggregate score cross-check against independent implementation ─────────

def t_aggregate_matches_independent():
    rng = random.Random(20260807)
    for _ in range(200):
        credit = rng.randint(0, 100)
        dbt = rng.randint(0, 60)
        status = rng.choice(["active", "registered", "inactive", "dissolved", "revoked"])
        bk, li, tx, lit = rng.randint(0, 2), rng.randint(0, 6), rng.randint(0, 3), rng.randint(0, 8)
        cr, dscr, mc = rng.uniform(0, 4), rng.uniform(0, 4), rng.uniform(0, 24)

        r, _ = run(
            bund("creditsafe", [obs("creditsafe.credit_score", credit, scale_min=0, scale_max=100,
                                    higher_is_better=True),
                                obs("creditsafe.days_beyond_terms", dbt)]),
            bund("middesk", [obs("middesk.registration_status", status),
                             obs("middesk.active_bankruptcy_count", bk),
                             obs("middesk.recent_lien_count_12m", li),
                             obs("middesk.active_tax_lien_count", tx),
                             obs("middesk.defendant_litigation_count_24m", lit)]),
            bund("codat", [obs("codat.current_ratio", cr),
                           obs("codat.debt_service_coverage_ratio", dscr),
                           obs("codat.months_cash_on_hand", mc)]),
        )
        # Independent raws
        raw_credit = round(max(0, min(100, credit)), 2)
        raw_pay = round(max(0, min(100, 100 - max(0, dbt) * 2.5)), 2)
        raw_id = {"active": 100, "registered": 95, "inactive": 25, "dissolved": 10, "revoked": 5}[status]
        raw_legal = round(max(0, min(100, 100 - min(100, bk * 100) - min(45, li * 12)
                                     - min(60, tx * 25) - min(35, lit * 7))), 2)
        comps = [max(0, min(100, cr / 2 * 100)), max(0, min(100, dscr / 2 * 100)),
                 max(0, min(100, mc / 12 * 100))]
        raw_cash = round(sum(comps) / 3, 2)

        exp = independent_score([
            ("Commercial Credit Risk", raw_credit, 1), ("B2B Payment Behavior", raw_pay, 1),
            ("Cash Flow & Liquidity", raw_cash, 1), ("Business Identity & Standing", raw_id, 1),
            ("Liens, Bankruptcy & Litigation", raw_legal, 1)])

        check(r["private_score"] == exp["score"], "aggregate score",
              f"expected={exp['score']} got={r['private_score']} inputs=credit{credit} dbt{dbt} {status} "
              f"bk{bk} li{li} tx{tx} lit{lit}")
        check(r["rating"] == exp["rating"], "aggregate rating",
              f"score={r['private_score']} expected={exp['rating']} got={r['rating']}")
        check(abs(r["meta"]["evidence_coverage"] - 1.0) < 1e-9, "full coverage")


# ── 3. Boundary / extremum behaviour ──────────────────────────────────────────

def t_boundaries():
    # All signals at maximum -> must reach exactly 1000
    r, _ = run(
        bund("creditsafe", [obs("creditsafe.credit_score", 100, scale_min=0, scale_max=100, higher_is_better=True),
                            obs("creditsafe.days_beyond_terms", 0)]),
        bund("middesk", [obs("middesk.registration_status", "active"),
                         obs("middesk.active_bankruptcy_count", 0),
                         obs("middesk.recent_lien_count_12m", 0),
                         obs("middesk.active_tax_lien_count", 0),
                         obs("middesk.defendant_litigation_count_24m", 0)]),
        bund("codat", [obs("codat.current_ratio", 2), obs("codat.debt_service_coverage_ratio", 2),
                       obs("codat.months_cash_on_hand", 12)]))
    check(r["private_score"] == 1000, "max score reaches 1000", f"got {r['private_score']}")
    check(r["rating"] == "Exceptional", "max rating", f"got {r['rating']}")

    # All signals at minimum -> must reach exactly 0
    r, _ = run(
        bund("creditsafe", [obs("creditsafe.credit_score", 0, scale_min=0, scale_max=100, higher_is_better=True),
                            obs("creditsafe.days_beyond_terms", 100)]),
        bund("middesk", [obs("middesk.registration_status", "revoked"),
                         obs("middesk.active_bankruptcy_count", 5),
                         obs("middesk.recent_lien_count_12m", 20),
                         obs("middesk.active_tax_lien_count", 20),
                         obs("middesk.defendant_litigation_count_24m", 50)]),
        bund("codat", [obs("codat.current_ratio", 0), obs("codat.debt_service_coverage_ratio", 0),
                       obs("codat.months_cash_on_hand", 0)]))
    # identity 'revoked' = 5 so min is not literally 0; recompute independently
    exp = independent_score([("Commercial Credit Risk", 0, 1), ("B2B Payment Behavior", 0, 1),
                             ("Cash Flow & Liquidity", 0, 1), ("Business Identity & Standing", 5, 1),
                             ("Liens, Bankruptcy & Litigation", 0, 1)])
    check(r["private_score"] == exp["score"], "min score", f"expected {exp['score']} got {r['private_score']}")
    check(0 <= r["private_score"] <= 1000, "score in range")

    # Band edges
    for target in [0, 249, 250, 399, 400, 549, 550, 699, 700, 849, 850, 1000]:
        raw = target / 10
        r2 = compute_score([{"signal": "Commercial Credit Risk", "raw_score": raw, "category": "financial",
                             "is_simulated": False, "is_scored": True, "provider_key": "creditsafe",
                             "entity_match_confidence": 1.0, "freshness_days": 0},
                            {"signal": "B2B Payment Behavior", "raw_score": raw, "category": "financial",
                             "is_simulated": False, "is_scored": True, "provider_key": "creditsafe",
                             "entity_match_confidence": 1.0, "freshness_days": 0},
                            {"signal": "Cash Flow & Liquidity", "raw_score": raw, "category": "financial",
                             "is_simulated": False, "is_scored": True, "provider_key": "codat",
                             "entity_match_confidence": 1.0, "freshness_days": 0},
                            {"signal": "Business Identity & Standing", "raw_score": raw, "category": "legal",
                             "is_simulated": False, "is_scored": True, "provider_key": "middesk",
                             "entity_match_confidence": 1.0, "freshness_days": 0},
                            {"signal": "Liens, Bankruptcy & Litigation", "raw_score": raw, "category": "legal",
                             "is_simulated": False, "is_scored": True, "provider_key": "middesk",
                             "entity_match_confidence": 1.0, "freshness_days": 0}],
                           model_release_stage="validated")
        expected_label = next(label for thr, label in EXPECTED_BANDS if target >= thr)
        check(r2["private_score"] == target, "band edge score", f"target={target} got={r2['private_score']}")
        check(r2["rating"] == expected_label, "band edge label",
              f"target={target} expected={expected_label} got={r2['rating']}")


# ── 4. Monotonicity / sensitivity ─────────────────────────────────────────────

def t_monotonicity():
    def score_with(credit):
        r, _ = run(
            bund("creditsafe", [obs("creditsafe.credit_score", credit, scale_min=0, scale_max=100,
                                    higher_is_better=True), obs("creditsafe.days_beyond_terms", 5)]),
            bund("middesk", [obs("middesk.registration_status", "active"),
                             obs("middesk.active_bankruptcy_count", 0),
                             obs("middesk.recent_lien_count_12m", 0),
                             obs("middesk.active_tax_lien_count", 0),
                             obs("middesk.defendant_litigation_count_24m", 0)]),
            bund("codat", [obs("codat.current_ratio", 1.5), obs("codat.debt_service_coverage_ratio", 1.5),
                           obs("codat.months_cash_on_hand", 9)]))
        return r["private_score"]

    prev = -1
    for credit in range(0, 101, 5):
        s = score_with(credit)
        check(s >= prev, "credit monotonic non-decreasing", f"credit={credit} score={s} prev={prev}")
        prev = s
    # 30% weight * 100 points * 10 = 300 point swing expected
    check(score_with(100) - score_with(0) == 300, "credit sensitivity magnitude",
          f"delta={score_with(100) - score_with(0)} expected 300")

    # Growth decreasing must not increase score
    prev = 1e9
    for rg in [1.0, 0.5, 0.2, 0.0, -0.2, -0.5]:
        r, _ = run(
            bund("creditsafe", [obs("creditsafe.credit_score", 70, scale_min=0, scale_max=100,
                                    higher_is_better=True), obs("creditsafe.days_beyond_terms", 5)]),
            bund("middesk", [obs("middesk.registration_status", "active"),
                             obs("middesk.active_bankruptcy_count", 0),
                             obs("middesk.recent_lien_count_12m", 0),
                             obs("middesk.active_tax_lien_count", 0),
                             obs("middesk.defendant_litigation_count_24m", 0)]),
            bund("codat", [obs("codat.current_ratio", 1.5), obs("codat.debt_service_coverage_ratio", 1.5),
                           obs("codat.months_cash_on_hand", 9), obs("codat.revenue_growth_yoy", rg)]))
        s = r["private_score"]
        check(s <= prev, "growth monotonic non-increasing", f"rg={rg} score={s} prev={prev}")
        prev = s


# ── 5. Adversarial / malformed inputs ─────────────────────────────────────────

def t_adversarial():
    base = {"category": "financial", "is_simulated": False, "is_scored": True,
            "provider_key": "creditsafe", "entity_match_confidence": 1.0, "freshness_days": 0}
    # Unusable values must be excluded, never coerced into a number. A single
    # signal is below the coverage gate anyway, so private_score is None; the
    # model's internal output is checked for range and for NaN promotion.
    unusable = {"NaN": float("nan"), "+Inf": float("inf"), "-Inf": float("-inf"),
                "None": None, "dict": {}, "list": [], "text": "abc"}
    for label, raw in unusable.items():
        try:
            r = compute_score([{**base, "signal": "Commercial Credit Risk", "raw_score": raw}],
                              model_release_stage="validated")
            check(r["private_score"] is None, f"adversarial {label} publishes no score", f"got {r['private_score']}")
            check(r["meta"]["model_output_score"] is None,
                  f"adversarial {label} produces no model output", f"got {r['meta']['model_output_score']}")
            check(r["meta"]["scored_signals"] == 0, f"adversarial {label} excluded from scoring")
            check(label in r["meta"]["unusable_signals"] or "Commercial Credit Risk" in r["meta"]["unusable_signals"],
                  f"adversarial {label} reported as unusable")
        except Exception as exc:
            check(False, f"adversarial raw_score {label} raised", f"{type(exc).__name__}: {exc}")

    # Finite but out-of-range values must be clamped, not rejected.
    for label, raw, expected in [("huge", 1e308, 100.0), ("negative", -1e6, 0.0), ("string-num", "77", 77.0)]:
        r = compute_score([{**base, "signal": "Commercial Credit Risk", "raw_score": raw}],
                          model_release_stage="validated")
        got = r["breakdown"][0]["raw_score"]
        check(got == expected, f"adversarial {label} clamped", f"expected {expected} got {got}")
        check(r["meta"]["scored_signals"] == 1, f"adversarial {label} still scored")

    # A NaN in one signal must not affect the others, and must not reach 1000.
    r = compute_score([
        {**base, "signal": "Commercial Credit Risk", "raw_score": float("nan")},
        {**base, "signal": "B2B Payment Behavior", "raw_score": 40},
        {**base, "signal": "Cash Flow & Liquidity", "raw_score": 40, "provider_key": "codat"},
        {**base, "signal": "Business Identity & Standing", "raw_score": 40, "provider_key": "middesk",
         "category": "legal"},
        {**base, "signal": "Liens, Bankruptcy & Litigation", "raw_score": 40, "provider_key": "middesk",
         "category": "legal"},
    ], model_release_stage="validated")
    check(r["meta"]["model_output_score"] == 400, "NaN excluded, peers unaffected",
          f"got {r['meta']['model_output_score']}")
    check(abs(r["meta"]["evidence_coverage"] - 0.70) < 1e-9, "NaN removes its own weight from coverage",
          f"got {r['meta']['evidence_coverage']}")

    # Missing weight / unknown signal name must not be scored
    r = compute_score([{**base, "signal": "Totally Unknown Signal", "raw_score": 100}],
                      model_release_stage="validated")
    check(r["meta"]["scored_signals"] == 0, "unknown signal not scored")

    # Confidence outside [0,1] should not push evidence confidence above 1
    r = compute_score([{**base, "signal": "Commercial Credit Risk", "raw_score": 80,
                        "entity_match_confidence": 99.0}], model_release_stage="validated")
    check(r["meta"]["confidence"] <= 1.0, "evidence confidence bounded", f"got {r['meta']['confidence']}")


# ── 6. Missing-data / gate behaviour ──────────────────────────────────────────

def t_gates_and_missing():
    # Zero providers
    r = compute_score([], model_release_stage="validated")
    check(r["scoring_status"] == "unrated", "empty signals unrated")
    check(r["meta"]["evidence_coverage"] == 0, "empty coverage 0")

    # Exactly at the 70% coverage threshold (credit .30 + payment .20 + cash .20 = .70)
    r, _ = run(bund("creditsafe", [obs("creditsafe.credit_score", 80, scale_min=0, scale_max=100,
                                       higher_is_better=True), obs("creditsafe.days_beyond_terms", 0)]),
               bund("codat", [obs("codat.current_ratio", 1.5), obs("codat.debt_service_coverage_ratio", 1.5),
                              obs("codat.months_cash_on_hand", 9)]))
    check(abs(r["meta"]["evidence_coverage"] - 0.70) < 1e-9, "coverage exactly 0.70",
          f"got {r['meta']['evidence_coverage']}")
    check(r["meta"]["gates"]["coverage"] is True, "coverage gate passes at exactly 70%")
    check(r["meta"]["identity_verified"] is False, "identity gate fails without middesk")
    check(r["scoring_status"] == "insufficient_data", "no rating without identity")

    # Just below threshold
    r, _ = run(bund("creditsafe", [obs("creditsafe.credit_score", 80, scale_min=0, scale_max=100,
                                       higher_is_better=True), obs("creditsafe.days_beyond_terms", 0)]),
               bund("middesk", [obs("middesk.registration_status", "active")]))
    check(abs(r["meta"]["evidence_coverage"] - 0.65) < 1e-9, "coverage 0.65",
          f"got {r['meta']['evidence_coverage']}")
    check(r["meta"]["gates"]["coverage"] is False, "coverage gate fails below 70%")

    # Freshness at exact max age boundary
    for days, should_score in [(119, True), (120, True), (121, False)]:
        r, _ = run(bund("creditsafe", [obs("creditsafe.credit_score", 80, days_old=days, scale_min=0,
                                           scale_max=100, higher_is_better=True)]))
        sig = next(i for i in r["breakdown"] if i["signal"] == "Commercial Credit Risk")
        check(sig["used_in_score"] == should_score, "freshness boundary",
              f"days={days} expected_scored={should_score} got={sig['used_in_score']}")

    # Future-dated observation must be rejected beyond 1-day skew
    r, _ = run(bund("creditsafe", [obs("creditsafe.credit_score", 80, days_old=-30, scale_min=0,
                                       scale_max=100, higher_is_better=True)]))
    sig = next(i for i in r["breakdown"] if i["signal"] == "Commercial Credit Risk")
    check(sig["used_in_score"] is False, "future-dated observation rejected")


# ── 7. Determinism ────────────────────────────────────────────────────────────

def t_determinism():
    bundles = (
        bund("creditsafe", [obs("creditsafe.credit_score", 82, scale_min=0, scale_max=100,
                                higher_is_better=True), obs("creditsafe.days_beyond_terms", 4)]),
        bund("middesk", [obs("middesk.registration_status", "active"),
                         obs("middesk.active_bankruptcy_count", 0),
                         obs("middesk.recent_lien_count_12m", 1),
                         obs("middesk.active_tax_lien_count", 0),
                         obs("middesk.defendant_litigation_count_24m", 2)]),
        bund("codat", [obs("codat.current_ratio", 1.5), obs("codat.debt_service_coverage_ratio", 1.4),
                       obs("codat.months_cash_on_hand", 8)]),
    )
    results = [run(*bundles)[0] for _ in range(10)]
    check(all(x == results[0] for x in results), "10 runs identical")
    # Bundle ordering must not change the score
    import itertools as it
    scores = {run(*perm)[0]["private_score"] for perm in it.permutations(bundles)}
    check(len(scores) == 1, "bundle order independent", f"got {scores}")


def main():
    for fn in [t_credit_transform, t_payment_transform, t_identity_transform, t_legal_transform,
               t_cashflow_transform, t_aggregate_matches_independent, t_boundaries, t_monotonicity,
               t_adversarial, t_gates_and_missing, t_determinism]:
        try:
            fn()
        except Exception as exc:
            failures.append(f"{fn.__name__} CRASHED :: {type(exc).__name__}: {exc}")

    print(f"\nchecks run: {checks}")
    print(f"failures:   {len(failures)}\n")
    for f in failures:
        print("  FAIL:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

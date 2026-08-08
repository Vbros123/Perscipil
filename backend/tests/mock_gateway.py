"""Mock licensed evidence gateway for exercising the rated/scored code path.

Serves the v2 evidence contract with controllable per-company profiles so the
full pipeline (gateway -> transforms -> gates -> rating) can be validated.
"""
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request

app = FastAPI()

# Company profiles keyed by lowercase legal name.
PROFILES = {
    # Healthy, profitable, growing
    "healthy corp": dict(credit=92, dbt=0, status="active", bk=0, li=0, tx=0, lit=0,
                         cr=2.4, dscr=2.2, ocf=0.22, mc=18, rg=0.45),
    # Distressed: bankrupt, liens, no cash
    "distressed corp": dict(credit=8, dbt=75, status="dissolved", bk=1, li=6, tx=3, lit=12,
                            cr=0.3, dscr=0.2, ocf=-0.35, mc=0.5, rg=-0.55),
    # Middling
    "average corp": dict(credit=55, dbt=12, status="active", bk=0, li=1, tx=0, lit=2,
                         cr=1.2, dscr=1.1, ocf=0.05, mc=6, rg=0.10),
    # Unprofitable but fast growing startup
    "burn startup": dict(credit=48, dbt=5, status="active", bk=0, li=0, tx=0, lit=0,
                         cr=1.8, dscr=0.4, ocf=-0.28, mc=14, rg=0.90),
    # Profitable but declining
    "declining corp": dict(credit=70, dbt=18, status="active", bk=0, li=2, tx=1, lit=3,
                           cr=1.6, dscr=1.5, ocf=0.12, mc=9, rg=-0.30),
}
DEFAULT = PROFILES["average corp"]


def _iso(days_old: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()


def _obs(eid, metric, value, days_old=2, **extra):
    return {"evidence_id": eid, "metric": metric, "value": value,
            "observed_at": _iso(days_old), "fetched_at": _iso(0),
            "source_ref": f"urn:mock:{metric}", "quality_flags": [], **extra}


def _match(entity, provider):
    return {
        "provider_entity_id": f"{provider}-{abs(hash(entity['legal_name'])) % 100000}",
        "legal_name": entity["legal_name"],
        "country_code": entity.get("country_code", "US"),
        "registration_number": entity.get("registration_number"),
        "match_status": "exact", "confidence": 0.99,
        "matched_fields": ["legal_name", "registration_number"]
             if entity.get("registration_number") else ["legal_name", "postal_code"],
    }


@app.post("/evidence")
async def evidence(request: Request):
    payload = await request.json()
    entity = payload["entity"]
    profile = PROFILES.get(entity["legal_name"].strip().lower(), DEFAULT)
    days = float(request.query_params.get("age_days", 2))

    def provider(key):
        return {"key": key, "name": key.title(), "license_reference": f"mock-{key}-2026",
                "permitted_use": ["company_intelligence"]}

    bundles = [
        {"provider": provider("creditsafe"), "entity_match": _match(entity, "creditsafe"),
         "observations": [
             _obs("cs-1", "creditsafe.credit_score", profile["credit"], days,
                  scale_min=0, scale_max=100, higher_is_better=True),
             _obs("cs-2", "creditsafe.days_beyond_terms", profile["dbt"], days, unit="days"),
         ]},
        {"provider": provider("middesk"), "entity_match": _match(entity, "middesk"),
         "observations": [
             _obs("md-1", "middesk.registration_status", profile["status"], days),
             _obs("md-2", "middesk.active_bankruptcy_count", profile["bk"], days),
             _obs("md-3", "middesk.recent_lien_count_12m", profile["li"], days),
             _obs("md-4", "middesk.active_tax_lien_count", profile["tx"], days),
             _obs("md-5", "middesk.defendant_litigation_count_24m", profile["lit"], days),
         ]},
        {"provider": provider("codat"), "entity_match": _match(entity, "codat"),
         "observations": [
             _obs("cd-1", "codat.current_ratio", profile["cr"], days, unit="ratio"),
             _obs("cd-2", "codat.debt_service_coverage_ratio", profile["dscr"], days, unit="ratio"),
             _obs("cd-3", "codat.operating_cash_flow_margin", profile["ocf"], days, unit="ratio"),
             _obs("cd-4", "codat.months_cash_on_hand", profile["mc"], days, unit="months"),
             _obs("cd-5", "codat.revenue_growth_yoy", profile["rg"], days, unit="ratio"),
         ]},
    ]
    return {"schema": "privatelens.evidence.v2", "request_id": payload["request_id"],
            "generated_at": _iso(0), "bundles": bundles}


@app.post("/evidence-error")
async def evidence_error():
    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "upstream exploded"}, status_code=500)


@app.post("/evidence-malformed")
async def evidence_malformed():
    return {"schema": "privatelens.evidence.v2", "request_id": "short", "bundles": "not-a-list"}


@app.post("/evidence-empty")
async def evidence_empty(request: Request):
    payload = await request.json()
    return {"schema": "privatelens.evidence.v2", "request_id": payload["request_id"],
            "generated_at": _iso(0), "bundles": []}

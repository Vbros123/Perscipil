"""Company evidence and scoring endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.limiter import rate_limiter
from core.security import get_optional_user
from models.user import User
from schemas.company import CompanyScoreRequest
from services.evidence import CompanyIdentity, PROVIDER_CATALOG, SIGNAL_SPECS
from services.history import history_store, store_company_event
from services.licensed_data import enabled as licensed_data_enabled
from services.reports import score_company

router = APIRouter(prefix="/api", tags=["Score"])
logger = logging.getLogger("privatelens.score")


async def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await rate_limiter.is_allowed(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


async def _run_score(
    request: Request,
    identity: CompanyIdentity,
    current_user: User | None,
    db: Session,
):
    await _check_rate_limit(request)
    try:
        response = await score_company(identity.legal_name, identity=identity)
    except Exception:
        logger.exception("score.pipeline_failed company=%s", identity.legal_name)
        raise HTTPException(status_code=500, detail="The evidence pipeline could not complete this request.")

    if current_user is not None:
        store_company_event(db, current_user, response, query_type="score")
    else:
        history_store.add(identity.legal_name, response["private_score"], response["rating"], response["color"])
    return response


@router.get("/score")
async def get_score(
    request: Request,
    company: str = Query(..., min_length=2, max_length=180),
    country_code: str = Query(default="US", min_length=2, max_length=2),
    registration_number: str | None = Query(default=None, max_length=80),
    postal_code: str | None = Query(default=None, max_length=24),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Backward-compatible company check with optional entity identifiers."""
    identity = CompanyIdentity(
        legal_name=company,
        country_code=country_code,
        registration_number=registration_number,
        postal_code=postal_code,
    )
    return await _run_score(request, identity, current_user, db)


@router.post("/score")
async def post_score(
    payload: CompanyScoreRequest,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Company check using the richer legal-entity identity contract."""
    identity = CompanyIdentity.model_validate(payload.model_dump())
    return await _run_score(request, identity, current_user, db)


@router.get("/cache/stats")
async def cache_stats():
    from core.cache import score_cache

    return score_cache.stats()


@router.get("/signals")
async def list_signals():
    signals = [
        {
            "name": name,
            "status": "licensed" if licensed_data_enabled() else "unavailable",
            "weight": f"{spec['weight'] * 100:.0f}%",
            "providers": [PROVIDER_CATALOG[key]["name"] for key in spec["providers"]],
            "max_age_days": spec["max_age_days"],
        }
        for name, spec in SIGNAL_SPECS.items()
    ]
    signals.extend([
        {"name": "Job Posting Velocity", "status": "context-only", "weight": "Context", "source": "Indeed"},
        {"name": "News & Media Sentiment", "status": "context-only", "weight": "Context", "source": "DuckDuckGo + HackerNews"},
        {"name": "Brand Legitimacy & Web Presence", "status": "context-only", "weight": "Context", "source": "Wikipedia"},
        {"name": "SEC / Regulatory Filings", "status": "context-only", "weight": "Context", "source": "SEC EDGAR"},
        {"name": "Government Contract Awards", "status": "context-only", "weight": "Context", "source": "USASpending.gov"},
    ])
    return {"signals": signals, "provider_catalog": list(PROVIDER_CATALOG.values())}


@router.get("/providers")
async def list_providers():
    return {
        "gateway_configured": licensed_data_enabled(),
        "providers": [
            {
                "key": key,
                **provider,
                "gateway_connected": licensed_data_enabled(),
                "status": "gateway-connected; provider readiness reported by gateway" if licensed_data_enabled() else "contract-and-credentials-required",
            }
            for key, provider in PROVIDER_CATALOG.items()
        ],
    }

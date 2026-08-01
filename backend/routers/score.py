"""Score router — main PrivateScore endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.limiter import rate_limiter
from core.security import get_optional_user
from models.user import User
from services.history import history_store, store_company_event
from services.reports import score_company

router = APIRouter(prefix="/api", tags=["Score"])


@router.get("/score")
async def get_score(
    request: Request,
    company: str = Query(..., min_length=2, max_length=120),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get PrivateScore for any US private company."""
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await rate_limiter.is_allowed(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)}
        )

    company_clean = company.strip()
    if len(company_clean) < 2:
        raise HTTPException(status_code=400, detail="Company name too short.")

    try:
        response = await score_company(company_clean)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring pipeline error: {str(e)}")

    if current_user is not None:
        store_company_event(db, current_user, response, query_type="score")
    else:
        history_store.add(company_clean, response["private_score"], response["rating"], response["color"])

    return response


@router.get("/cache/stats")
async def cache_stats():
    """Cache statistics for monitoring."""
    from core.cache import score_cache

    return score_cache.stats()


@router.get("/signals")
async def list_signals():
    """List all 14 signal types with data source status."""
    return {
        "signals": [
            {"name": "Open Banking Payment Flows",    "status": "unavailable", "weight": "13%", "unlocks_with": "Section 1033 API"},
            {"name": "B2B Payment Behavior",          "status": "unavailable", "weight": "12%", "unlocks_with": "D&B Paydex API"},
            {"name": "Job Posting Velocity",          "status": "context-only", "weight": "11%", "source": "Indeed"},
            {"name": "UCC Filings & Lien Activity",   "status": "unavailable", "weight": "10%", "unlocks_with": "State UCC APIs"},
            {"name": "Court Records & Litigation",    "status": "unavailable", "weight": "9%",  "unlocks_with": "PACER / CourtListener"},
            {"name": "News & Media Sentiment",        "status": "context-only", "weight": "8%",  "source": "DuckDuckGo + HackerNews"},
            {"name": "Employee & Customer Reviews",   "status": "unavailable", "weight": "7%",  "unlocks_with": "Glassdoor API"},
            {"name": "Insider & Employee Sentiment",  "status": "unavailable", "weight": "6%",  "unlocks_with": "Glassdoor API"},
            {"name": "Web Traffic Trends",            "status": "unavailable", "weight": "6%",  "unlocks_with": "SimilarWeb API"},
            {"name": "Brand Legitimacy",              "status": "context-only", "weight": "5%",  "source": "Wikipedia API"},
            {"name": "SEC / Regulatory Filings",      "status": "context-only", "weight": "5%",  "source": "SEC EDGAR"},
            {"name": "Social Media Activity",         "status": "unavailable", "weight": "4%",  "unlocks_with": "Twitter/LinkedIn API"},
            {"name": "Supply Chain & Vendor Signals", "status": "unavailable", "weight": "3%",  "unlocks_with": "RiskMethods API"},
            {"name": "Government Contract Awards",    "status": "context-only", "weight": "1%",  "source": "USASpending.gov"},
        ]
    }

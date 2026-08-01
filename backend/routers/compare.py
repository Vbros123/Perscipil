"""Company comparison routes."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.limiter import rate_limiter
from core.security import get_optional_user
from models.user import User
from services.history import store_company_event
from services.reports import score_company

router = APIRouter(prefix="/api", tags=["Compare"])


@router.get("/compare")
async def compare(
    request: Request,
    companies: str = Query(..., description="Comma-separated list of 2-4 company names"),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    names = [name.strip() for name in companies.split(",") if name.strip()]
    if len(names) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 company names.")
    if len(names) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 companies per comparison.")

    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await rate_limiter.is_allowed(ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Try again in {retry_after}s.")

    results = await asyncio.gather(*[score_company(name) for name in names], return_exceptions=True)
    valid = [result for result in results if isinstance(result, dict)]
    if not valid:
        raise HTTPException(status_code=500, detail="Failed to score any companies.")

    if current_user is not None:
        for result in valid:
            store_company_event(db, current_user, result, query_type="compare")

    rated = [result for result in valid if result.get("scoring_status") == "rated"]
    if len(rated) == len(valid):
        winner = max(rated, key=lambda item: item["private_score"])
        low = min(result["private_score"] for result in rated)
        winner_name = winner["company_name"]
        winner_score = winner["private_score"]
        analysis = (
            f"{winner_name} leads this peer set with a PrivateScore of "
            f"{winner_score}/1000 ({winner['rating']}). Gap vs lowest: "
            f"{winner_score - low} points."
        )
    else:
        winner_name = None
        winner_score = None
        analysis = (
            "No peer ranking was produced because one or more companies are below the verified-data "
            "coverage, entity, provider-diversity, and model-approval gates required for a rating."
        )
    return {
        "companies": valid,
        "winner": winner_name,
        "winner_score": winner_score,
        "analysis": analysis,
        "disclaimer": "PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.",
    }

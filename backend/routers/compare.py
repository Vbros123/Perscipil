"""Company comparison routes."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.limiter import rate_limiter
from core.security import get_optional_user
from models.user import User
from services.history import store_company_event
from services.reports import normalize_company, score_company
from services.scorer import PUBLISHED_SCORE_STATUSES

router = APIRouter(prefix="/api", tags=["Compare"])
logger = logging.getLogger("privatelens.compare")


@router.get("/compare")
async def compare(
    request: Request,
    companies: str = Query(..., max_length=724, description="Comma-separated list of 2-4 company names"),
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    from services.licensed_data import enabled
    if enabled() and current_user is None:
        raise HTTPException(401, "Authentication required for licensed reports")
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in companies.split(","):
        name = " ".join(raw_name.split())
        if len(name) < 2:
            continue
        # Comparing a company with itself is not a peer set, and it would make the
        # winner arbitrary and the peer gap a meaningless zero.
        key = normalize_company(name)
        if key in seen:
            continue
        seen.add(key)
        names.append(name)

    if len(names) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 distinct company names.")
    if len(names) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 companies per comparison.")

    ip = request.client.host if request.client else "unknown"
    # Charge one token per company so a comparison cannot be used to run four
    # scored lookups for the price of one.
    allowed, retry_after = await rate_limiter.is_allowed(ip, cost=len(names))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    results = await asyncio.gather(*[score_company(name) for name in names], return_exceptions=True)
    valid = [result for result in results if isinstance(result, dict)]
    failed = [name for name, result in zip(names, results) if not isinstance(result, dict)]
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.warning("compare.company_failed company=%s error_type=%s", name, type(result).__name__)
    if not valid:
        raise HTTPException(status_code=500, detail="Failed to score any companies.")

    if current_user is not None:
        for result in valid:
            store_company_event(db, current_user, result, query_type="compare")

    rated = [result for result in valid if result.get("scoring_status") in PUBLISHED_SCORE_STATUSES]
    # A peer set needs at least two peers that were actually scored. Ranking a
    # lone survivor of a failed batch would present it as the winner of a
    # comparison that never happened.
    if len(rated) >= 2 and len(rated) == len(valid) and not failed:
        winner = max(rated, key=lambda item: item["private_score"])
        low = min(result["private_score"] for result in rated)
        winner_name = winner["company_name"]
        winner_score = winner["private_score"]
        analysis = (
            f"{winner_name} leads this peer set with a Perspicil Score of "
            f"{winner_score}/1000 ({winner['rating']}). Gap vs lowest: "
            f"{winner_score - low} points."
        )
    else:
        winner_name = None
        winner_score = None
        if failed:
            analysis = (
                f"No peer ranking was produced because {len(failed)} of {len(names)} companies could not be "
                f"analysed: {', '.join(failed)}."
            )
        else:
            analysis = (
                "No peer ranking was produced because one or more companies are below the verified-data "
                "coverage, entity, provider-diversity, and model-approval gates required for a rating."
            )
    return {
        "companies": valid,
        "requested": names,
        "failed": failed,
        "complete": not failed,
        "rated_count": len(rated),
        "winner": winner_name,
        "winner_score": winner_score,
        "analysis": analysis,
        "disclaimer": "Perspicil is a research tool and does not provide credit, investment, legal, or lending advice.",
    }

"""Isolated gateway for licensed provider credentials and normalized evidence."""
from datetime import datetime, timezone
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException

from config import get_settings
from models import EvidenceRequest, EvidenceResponse
from providers.creditsafe import CreditsafeAdapter

settings = get_settings()
settings.validate_runtime()
creditsafe = CreditsafeAdapter(settings)

app = FastAPI(title="PrivateLens Provider Gateway", version="2.0.0")


def authorize(authorization: str = Header(default="")) -> None:
    provided = authorization.removeprefix("Bearer ").strip()
    if not provided or not secrets.compare_digest(provided, settings.GATEWAY_SHARED_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "creditsafe": {"enabled": creditsafe.enabled},
        "middesk": {"enabled": False, "reason": "requires completed business IDs and contract credentials"},
        "codat": {"enabled": False, "reason": "requires company-consented connection IDs"},
    }


@app.post("/v2/evidence", response_model=EvidenceResponse, dependencies=[Depends(authorize)])
async def evidence(payload: EvidenceRequest):
    bundles = []
    if "creditsafe" in payload.providers:
        bundle = await creditsafe.fetch(payload.entity, payload.request_id)
        if bundle is not None:
            bundles.append(bundle)
    return EvidenceResponse(
        request_id=payload.request_id,
        generated_at=datetime.now(timezone.utc),
        bundles=bundles,
    )

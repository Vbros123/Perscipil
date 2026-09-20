"""Fail-closed client for the PrivateLens licensed evidence gateway."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from pydantic import ValidationError

from core.config import get_settings
from services.evidence import CompanyIdentity, GatewayEvidenceResponse, build_licensed_signals

settings = get_settings()
logger = logging.getLogger("privatelens.licensed_data")


def enabled() -> bool:
    settings = get_settings()
    return bool(
        settings.effective_data_mode in {"licensed", "hybrid"}
        and settings.licensed_credentials_present
        and bool(__import__("services.permissions", fromlist=["allowed_providers"]).allowed_providers())
    )


async def fetch_evidence(identity: CompanyIdentity) -> GatewayEvidenceResponse | None:
    if not enabled():
        return None

    request_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "schema": "privatelens.evidence.request.v2",
        "request_id": request_id,
        "entity": identity.model_dump(mode="json", exclude_none=True),
        "providers": __import__("services.permissions", fromlist=["allowed_providers"]).allowed_providers(),
        "required_permitted_use": "company_intelligence",
    }
    headers = {
        "Authorization": f"Bearer {settings.LICENSED_DATA_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "PrivateLens/4.0 licensed-evidence-client",
        "X-Request-ID": request_id,
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.LICENSED_DATA_TIMEOUT,
            follow_redirects=False,
        ) as client:
            response = await client.post(settings.LICENSED_DATA_GATEWAY_URL, json=payload, headers=headers)
        if response.status_code in {404, 409, 422}:
            logger.info("licensed_data.no_resolved_evidence request_id=%s status=%s", request_id, response.status_code)
            return None
        response.raise_for_status()
        parsed = GatewayEvidenceResponse.model_validate(response.json())
    except ValidationError as exc:
        logger.warning("licensed_data.contract_rejected request_id=%s errors=%s", request_id, len(exc.errors()))
        return None
    except Exception as exc:
        logger.warning("licensed_data.fetch_failed request_id=%s error_type=%s", request_id, type(exc).__name__)
        return None

    if parsed.request_id != request_id:
        logger.warning("licensed_data.request_id_mismatch request_id=%s", request_id)
        return None
    from services.permissions import allowed_providers
    parsed.bundles = [b for b in parsed.bundles if b.provider.key in allowed_providers()]
    return parsed


async def collect_licensed_signals(identity: CompanyIdentity) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    response = await fetch_evidence(identity)
    signals, audit = build_licensed_signals(response, identity)
    audit["gateway_enabled"] = enabled()
    audit["data_mode"] = settings.DATA_MODE
    return signals, audit

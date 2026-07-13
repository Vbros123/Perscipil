"""Licensed data gateway integration.

PrivateLens expects licensed vendor data to be normalized by a gateway service.
That gateway owns vendor-specific contracts, credentials, schemas, and rate limits.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from core.config import get_settings

settings = get_settings()
logger = logging.getLogger("privatelens.licensed_data")


def enabled() -> bool:
    return bool(settings.LICENSED_DATA_GATEWAY_URL and settings.LICENSED_DATA_API_KEY)


async def fetch_signal(company: str, provider_key: str, fallback_signal: dict[str, Any]) -> dict[str, Any] | None:
    if not enabled():
        return None

    payload = {
        "company_name": company,
        "provider_key": provider_key,
        "signal": fallback_signal["signal"],
        "expected_schema": "privatelens.signal.v1",
    }
    headers = {
        "Authorization": f"Bearer {settings.LICENSED_DATA_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "PrivateLens/3.1 licensed-data-client",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.LICENSED_DATA_TIMEOUT) as client:
            response = await client.post(settings.LICENSED_DATA_GATEWAY_URL, json=payload, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("licensed_data.fetch_failed provider=%s company=%s error=%s", provider_key, company, exc)
        return None

    if data.get("schema") != "privatelens.signal.v1":
        logger.warning("licensed_data.invalid_schema provider=%s company=%s", provider_key, company)
        return None

    raw_score = data.get("raw_score")
    if raw_score is None:
        return None

    return {
        **fallback_signal,
        "display": data.get("display") or fallback_signal.get("display"),
        "raw_score": max(0, min(100, float(raw_score))),
        "is_simulated": False,
        "source_url": data.get("source_url") or fallback_signal.get("source_url"),
        "insight": data.get("insight") or fallback_signal.get("insight"),
        "licensed_provider": data.get("provider_name") or provider_key,
        "license_reference": data.get("license_reference"),
    }


async def apply_licensed_overrides(company: str, simulated_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_map = {
        "UCC Filings & Lien Activity": "ucc",
        "Court Records & Litigation": "court_records",
        "Open Banking Payment Flows": "open_banking",
        "Employee & Customer Reviews": "reviews",
        "Web Traffic Trends": "web_traffic",
        "Social Media Activity": "social",
        "Supply Chain & Vendor Signals": "supply_chain",
        "B2B Payment Behavior": "b2b_payments",
        "Insider & Employee Sentiment": "employee_sentiment",
    }
    out = []
    for signal in simulated_signals:
        provider_key = provider_map.get(signal["signal"])
        licensed = await fetch_signal(company, provider_key, signal) if provider_key else None
        out.append(licensed or signal)
    return out

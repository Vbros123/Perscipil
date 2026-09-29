"""Provider contracts. Scoring consumes standardized signals, not vendor payloads.

Licensed credit, cash-flow, and legal feeds stay unavailable until a real
gateway URL and API key are configured. This package does not invent those
observations.
"""
from __future__ import annotations

from typing import Any, Protocol

from services.evidence import CompanyIdentity


class LicensedDataProvider(Protocol):
    key: str
    name: str

    def configured(self) -> bool: ...

    async def get_financial_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]: ...

    async def get_cashflow_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]: ...

    async def get_credit_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]: ...

    async def get_legal_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]: ...


def unavailable_licensed_signal(name: str, category: str, source: str) -> dict[str, Any]:
    return {
        "signal": name,
        "name": name,
        "category": category,
        "value": None,
        "score": None,
        "raw_score": None,
        "status": "unavailable",
        "availability_status": "unavailable",
        "evidence_quality": "unavailable",
        "evidenceQuality": "unavailable",
        "source": source,
        "sourceUrl": None,
        "retrievedAt": None,
        "explanation": (
            "Licensed evidence is not configured. Perspicil does not invent credit, "
            "cash-flow, or legal records."
        ),
        "weight": 0,
        "is_scored": False,
        "is_simulated": True,
    }

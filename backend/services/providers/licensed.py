"""Licensed gateway adapter. Returns unavailable unless a real gateway is configured."""
from __future__ import annotations

from typing import Any

from core.config import get_settings
from services.evidence import CompanyIdentity, SIGNAL_SPECS
from services.licensed_data import collect_licensed_signals, enabled as gateway_enabled
from services.providers.base import unavailable_licensed_signal

settings = get_settings()

CREDIT_SIGNALS = ("Commercial Credit Risk", "B2B Payment Behavior")
CASHFLOW_SIGNALS = ("Cash Flow & Liquidity",)
LEGAL_SIGNALS = ("Business Identity & Standing", "Liens, Bankruptcy & Litigation")


class GatewayLicensedProvider:
    """Creditsafe / Middesk / Codat via the v2 evidence gateway.

    How to connect a real provider later:
    1. Deploy `provider_gateway/` with vendor credentials (never in this repo).
    2. Set LICENSED_DATA_GATEWAY_URL to the HTTPS gateway evidence endpoint.
    3. Set LICENSED_DATA_API_KEY to the shared bearer token.
    4. Set DATA_MODE=hybrid (public fallback) or DATA_MODE=licensed.
    5. Keep MODEL_RELEASE_STAGE=shadow until a validation packet is approved.
    The gateway must return privatelens.evidence.v2 observations, not vendor composite scores.
    """

    key = "licensed_gateway"
    name = "Licensed evidence gateway"

    def configured(self) -> bool:
        return gateway_enabled()

    async def _collect(self, company: CompanyIdentity) -> list[dict[str, Any]]:
        if not self.configured():
            return []
        signals, _audit = await collect_licensed_signals(company)
        return [item for item in signals if item.get("is_scored")]

    async def get_credit_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]:
        return await self._named(company, CREDIT_SIGNALS, "creditsafe")

    async def get_cashflow_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]:
        return await self._named(company, CASHFLOW_SIGNALS, "codat")

    async def get_legal_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]:
        return await self._named(company, LEGAL_SIGNALS, "middesk")

    async def get_financial_signals(self, company: CompanyIdentity) -> list[dict[str, Any]]:
        credit = await self.get_credit_signals(company)
        cash = await self.get_cashflow_signals(company)
        return credit + cash

    async def _named(self, company: CompanyIdentity, names: tuple[str, ...], source: str) -> list[dict[str, Any]]:
        live = {item.get("signal"): item for item in await self._collect(company)}
        out: list[dict[str, Any]] = []
        for name in names:
            if name in live:
                out.append(live[name])
            else:
                spec = SIGNAL_SPECS.get(name, {})
                out.append(unavailable_licensed_signal(name, spec.get("category", "financial"), source))
        return out

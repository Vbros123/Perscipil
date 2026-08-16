"""Provider registry: public collectors plus licensed gateway (if configured)."""
from __future__ import annotations

from typing import Any

from core.config import get_settings
from services.licensed_data import enabled as gateway_enabled
from services.providers.licensed import GatewayLicensedProvider

settings = get_settings()

PUBLIC_PROVIDERS = (
    {"key": "gleif", "name": "GLEIF", "track": "public", "quality": "high", "scored": False},
    {"key": "sec", "name": "SEC EDGAR", "track": "public", "quality": "high", "scored": False},
    {"key": "wikipedia", "name": "Wikipedia", "track": "public", "quality": "low", "scored": True},
    {"key": "news", "name": "DuckDuckGo / Hacker News", "track": "public", "quality": "low", "scored": True},
    {"key": "jobs", "name": "Indeed", "track": "public", "quality": "low", "scored": True},
    {"key": "usaspending", "name": "USASpending", "track": "public", "quality": "high", "scored": True},
)

LICENSED_PROVIDERS = (
    {"key": "creditsafe", "name": "Creditsafe", "track": "licensed", "quality": "high", "signals": "credit / payment"},
    {"key": "middesk", "name": "Middesk", "track": "licensed", "quality": "high", "signals": "identity / legal"},
    {"key": "codat", "name": "Codat", "track": "licensed", "quality": "high", "signals": "cash flow"},
)


class ProviderRegistry:
    def __init__(self) -> None:
        self._licensed = GatewayLicensedProvider()
        self._extra: list[Any] = []

    def register(self, provider: Any) -> None:
        """Plug in a future licensed provider without changing the scorer."""
        self._extra.append(provider)

    def licensed_provider(self) -> GatewayLicensedProvider:
        return self._licensed

    def get_available_providers(self) -> list[dict[str, Any]]:
        rows = []
        for item in PUBLIC_PROVIDERS:
            rows.append({**item, "configured": True, "status": "public"})
        licensed_on = self._licensed.configured()
        for item in LICENSED_PROVIDERS:
            rows.append({
                **item,
                "configured": licensed_on,
                "status": "live" if licensed_on else "unavailable",
            })
        for provider in self._extra:
            configured = provider.configured() if hasattr(provider, "configured") else False
            rows.append({
                "key": getattr(provider, "key", "custom"),
                "name": getattr(provider, "name", "Custom provider"),
                "track": "licensed",
                "quality": "high",
                "configured": configured,
                "status": "live" if configured else "unavailable",
            })
        return rows

    def get_provider_status(self) -> dict[str, Any]:
        return {
            "data_mode": settings.DATA_MODE,
            "effective_data_mode": settings.effective_data_mode,
            "licensed_gateway_configured": gateway_enabled(),
            "licensed_credentials_present": settings.licensed_credentials_present,
            "providers": self.get_available_providers(),
            "note": (
                "Licensed credit, cash-flow, and legal evidence stay unavailable until "
                "LICENSED_DATA_GATEWAY_URL and LICENSED_DATA_API_KEY point at a real gateway. "
                "PrivateLens does not fabricate those records."
            ),
        }


_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry

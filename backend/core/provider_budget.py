"""Aggregate request budgets across API and worker processes (shared DB)."""

import logging, time
import httpx
from core.config import get_settings
from core.limiter import DatabaseLimiter

logger = logging.getLogger("privatelens.providers")


async def before_request(request):
    s = get_settings()
    if not s.PROVIDER_BUDGETS_ENABLED:
        return
    host = request.url.host
    group = "sec" if host.endswith(".sec.gov") or host == "sec.gov" else host
    limit = 5 if group == "sec" else 2
    allowed, retry = await DatabaseLimiter(limit, 1, "provider").is_allowed(group)
    if not allowed:
        logger.warning(
            "provider_budget_denied provider=%s retry_after=%d", group, retry
        )
        response = httpx.Response(
            429, request=request, headers={"Retry-After": str(retry)}
        )
        raise httpx.HTTPStatusError(
            "Provider request budget exhausted", request=request, response=response
        )
    request.extensions["pl_started"] = time.monotonic()


async def after_response(response):
    started = response.request.extensions.get("pl_started")
    if started is not None:
        logger.info(
            "provider_response host=%s status=%d latency_ms=%d",
            response.request.url.host,
            response.status_code,
            int((time.monotonic() - started) * 1000),
        )


HOOKS = {"request": [before_request], "response": [after_response]}


class ProviderClient(httpx.AsyncClient):
    """Two simultaneous buffered requests per provider across all processes.

    A request is cancelled after 90 seconds; leases expire at 120 seconds to
    recover capacity after process death. Rate hooks still apply per redirect.
    """
    async def send(self, request, **kwargs):
        import asyncio, hashlib
        from core.leases import acquire, release
        if not get_settings().PROVIDER_BUDGETS_ENABLED:
            return await super().send(request, **kwargs)
        if kwargs.get("stream"):
            raise ValueError("Provider streaming is not supported")
        host = request.url.host
        group = "sec" if host.endswith(".sec.gov") or host == "sec.gov" else host
        prefix = "provider:" + hashlib.sha256(group.encode()).hexdigest()[:40]
        owned = None
        for slot in range(2):
            key = prefix + ":" + str(slot)
            token = await asyncio.to_thread(acquire, key, 120)
            if token:
                owned = (key, token)
                break
        if owned is None:
            response = httpx.Response(429, request=request, headers={"Retry-After":"2"})
            raise httpx.HTTPStatusError("Provider concurrency exhausted", request=request, response=response)
        try:
            return await asyncio.wait_for(super().send(request, **kwargs), timeout=90)
        finally:
            await asyncio.shield(asyncio.to_thread(release, *owned))

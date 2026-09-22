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

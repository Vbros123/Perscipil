"""
Simple sliding window rate limiter.
Prevents abuse without needing Redis.
"""
import time
import asyncio
from collections import defaultdict, deque

from core.config import get_settings

settings = get_settings()


class SlidingWindowLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, identifier: str, cost: int = 1) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds).

        `cost` lets an endpoint that performs several scored lookups consume the
        matching number of tokens, so a batch endpoint cannot be used to bypass
        the per-company limit.
        """
        cost = max(1, int(cost))
        async with self._lock:
            now = time.time()
            q = self._requests[identifier]

            # Remove expired entries
            while q and now - q[0] > self._window:
                q.popleft()

            if not q:
                # Avoid retaining an entry for every IP ever seen.
                self._requests.pop(identifier, None)
                q = self._requests[identifier]

            if len(q) + cost > self._max:
                oldest = q[0] if q else now
                retry_after = int(self._window - (now - oldest)) + 1
                return False, max(1, retry_after)

            for _ in range(cost):
                q.append(now)
            return True, 0


rate_limiter = SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)

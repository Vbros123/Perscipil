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
            if len(self._requests) >= 10000:
                expired = [key for key, values in self._requests.items() if not values or now-values[-1]>self._window]
                for key in expired: self._requests.pop(key, None)
                if identifier not in self._requests and len(self._requests)>=10000:
                    return False, self._window
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

class DatabaseLimiter:
    """Atomic fixed-window quota shared across instances; fails closed on DB failure."""
    def __init__(self, max_requests=30, window_seconds=60, namespace='score'):
        self._max, self._window, self.namespace = max_requests, window_seconds, namespace

    async def is_allowed(self, identifier, cost=1):
        import hashlib
        from sqlalchemy import delete
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from core.database import SessionLocal
        from models.workflows import RateBucket
        now = int(time.time())
        window = now // self._window
        cost = max(1, int(cost))
        if cost > self._max:
            return False, self._window
        key = self.namespace + ':' + hashlib.sha256(identifier.encode()).hexdigest()
        try:
            with SessionLocal.begin() as db:
                insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
                statement = insert(RateBucket).values(key=key, window=window, count=cost)
                statement = statement.on_conflict_do_update(
                    index_elements=['key', 'window'],
                    set_={'count': RateBucket.count + cost},
                    where=RateBucket.count + cost <= self._max,
                ).returning(RateBucket.count)
                allowed = db.execute(statement).scalar_one_or_none() is not None
                db.execute(delete(RateBucket).where(RateBucket.key == key, RateBucket.window < window - 1))
            return allowed, 0 if allowed else self._window - now % self._window
        except Exception:
            return False, self._window

if settings.RATE_LIMIT_BACKEND == 'database':
    rate_limiter = DatabaseLimiter(settings.RATE_LIMIT_PER_MINUTE)
auth_limiter = (DatabaseLimiter(30, 60, 'auth') if settings.RATE_LIMIT_BACKEND == 'database'
                else SlidingWindowLimiter(30, 60))

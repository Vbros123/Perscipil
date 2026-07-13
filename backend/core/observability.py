"""Logging, Sentry, and lightweight metrics."""
from __future__ import annotations

from collections import defaultdict
import json
import logging
import time
from threading import Lock
from typing import Any

from core.config import get_settings

settings = get_settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]


def configure_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError as exc:
        raise RuntimeError("sentry-sdk is required when SENTRY_DSN is configured.") from exc

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"privatelens-api@{settings.APP_VERSION}",
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._latency_count: dict[tuple[str, str], int] = defaultdict(int)

    def observe(self, method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
        route = path if path.startswith("/api/") else "/"
        key = (method, route, status_code)
        latency_key = (method, route)
        with self._lock:
            self._requests[key] += 1
            self._latency_sum[latency_key] += elapsed_seconds
            self._latency_count[latency_key] += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP privatelens_http_requests_total Total HTTP requests.",
            "# TYPE privatelens_http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status), count in sorted(self._requests.items()):
                lines.append(
                    f'privatelens_http_requests_total{{method="{method}",route="{route}",status="{status}"}} {count}'
                )
            lines.extend([
                "# HELP privatelens_http_request_duration_seconds_avg Average request duration.",
                "# TYPE privatelens_http_request_duration_seconds_avg gauge",
            ])
            for (method, route), total in sorted(self._latency_sum.items()):
                count = self._latency_count[(method, route)] or 1
                lines.append(
                    f'privatelens_http_request_duration_seconds_avg{{method="{method}",route="{route}"}} {total / count:.6f}'
                )
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()

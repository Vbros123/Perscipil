"""Production readiness and compliance status routes."""
from fastapi import APIRouter

from core.config import get_settings

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])
settings = get_settings()


@router.get("/status")
def compliance_status():
    return {
        "environment": settings.ENVIRONMENT,
        "managed_postgres": settings.DATABASE_URL.startswith(("postgres://", "postgresql://")),
        "email_delivery": settings.EMAIL_DELIVERY_MODE,
        "observability": {
            "sentry": bool(settings.SENTRY_DSN),
            "metrics": bool(settings.METRICS_TOKEN),
        },
        "backups": {
            "runbook": "/ops/backup_runbook.md",
            "requires_managed_postgres": True,
        },
        "licensed_data_gateway": bool(settings.LICENSED_DATA_GATEWAY_URL and settings.LICENSED_DATA_API_KEY),
        "legal_notice": "PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.",
    }

"""
PrivateLens API v4
Private company financial health research platform.
"""
from contextlib import asynccontextmanager
import logging
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from core.config import get_settings
from core.database import init_db
from core.observability import configure_logging, configure_sentry, metrics
from routers.auth import router as auth_router
from routers.compliance import router as compliance_router
from routers.compare import router as compare_router
from routers.history import router as history_router
from routers.score import router as score_router
from routers.settings import router as settings_router
from routers.users import router as users_router
from routers.watchlist import router as watchlist_router

configure_logging()
configure_sentry()
logger = logging.getLogger("privatelens")

settings = get_settings()
settings.validate_runtime()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        init_db()
    yield


app = FastAPI(
    title="PrivateLens API",
    description="Private company financial health scoring, watchlists, reports, and user workspaces.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

cors_origins = settings.cors_origins
trusted_hosts = settings.trusted_hosts
if trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    ms = round(elapsed * 1000, 1)
    metrics.observe(request.method, request.url.path, response.status_code, elapsed)
    response.headers["X-Response-Time"] = f"{ms}ms"
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(auth_router)
app.include_router(compliance_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(watchlist_router)
app.include_router(history_router)
app.include_router(score_router)
app.include_router(compare_router)


@app.get("/")
def root():
    return {
        "product": "PrivateLens",
        "tagline": "Private company financial health intelligence",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "endpoints": [
            "/api/auth/signup",
            "/api/auth/login",
            "/api/auth/me",
            "/api/score",
            "/api/compare",
            "/api/watchlist",
            "/api/history",
            "/api/settings",
            "/api/signals",
        ],
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "postgres" if settings.DATABASE_URL.startswith(("postgres://", "postgresql://")) else "sqlite",
        "email": settings.EMAIL_DELIVERY_MODE,
        "observability": {"sentry": bool(settings.SENTRY_DSN), "metrics": bool(settings.METRICS_TOKEN)},
        "data_mode": settings.DATA_MODE,
        "licensed_data": bool(settings.LICENSED_DATA_GATEWAY_URL and settings.LICENSED_DATA_API_KEY),
        "model_release_stage": settings.MODEL_RELEASE_STAGE,
    }


@app.get("/api/metrics", response_class=PlainTextResponse)
def get_metrics(request: Request):
    provided = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if settings.METRICS_TOKEN and secrets.compare_digest(provided, settings.METRICS_TOKEN):
        return metrics.render_prometheus()
    return PlainTextResponse("not found\n", status_code=404)

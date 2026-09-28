"""
Perspicil API v4
Private company financial health research platform.
"""
from contextlib import asynccontextmanager
import logging
import os
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from core.brand import NAME
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
    title=settings.APP_NAME,
    description="Evidence-weighted company research, saved reports, and individual accounts.",
    version=settings.APP_VERSION,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

from core.body_limit import BodyLimitMiddleware
app.add_middleware(BodyLimitMiddleware)

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
    request_id = secrets.token_hex(12)
    if request.url.path in {"/api/cache/stats", "/api/providers", "/api/compliance/status"} and settings.is_production:
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not settings.METRICS_TOKEN or not secrets.compare_digest(supplied, settings.METRICS_TOKEN):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins and settings.cors_origins != ["*"]:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        if settings.COOKIE_AUTH and request.cookies.get(settings.SESSION_COOKIE_NAME) and not origin:
            return JSONResponse(status_code=403, content={"detail": "Origin required for cookie requests"})
    if request.url.path.startswith("/api/auth/") and request.method == "POST":
        from core.limiter import auth_limiter
        allowed, retry = await auth_limiter.is_allowed(request.client.host if request.client else "unknown")
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "Too many authentication attempts"}, headers={"Retry-After": str(retry)})
    from core.observability import request_id_context
    context_token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(context_token)
    elapsed = time.perf_counter() - start
    ms = round(elapsed * 1000, 1)
    metrics.observe(request.method, getattr(request.scope.get("route"), "path", "/unmatched"), response.status_code, elapsed)
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'" if settings.is_production else "default-src 'self' https: 'unsafe-inline'"
    response.headers["Cache-Control"] = "no-store"
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
    logger.error("Unhandled error type=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


from routers.workflows import router as workflows_router
from routers.organizations import router as organizations_router
from routers.mfa import router as mfa_router
app.include_router(mfa_router)
from routers.customer import router as customer_router
app.include_router(customer_router)
app.include_router(organizations_router)
app.include_router(workflows_router)
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
        "product": NAME,
        "tagline": "Evidence-weighted company research",
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
    return {"status": "ok"}


@app.get("/api/metrics", response_class=PlainTextResponse)
def get_metrics(request: Request):
    provided = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if settings.METRICS_TOKEN and secrets.compare_digest(provided, settings.METRICS_TOKEN):
        from services.operations import queue_metrics
        return metrics.render_prometheus() + queue_metrics()
    return PlainTextResponse("not found\n", status_code=404)

@app.get("/.well-known/security.txt", response_class=PlainTextResponse)
def security_txt():
    from datetime import datetime, timezone
    try:
        expiry = datetime.fromisoformat(settings.SECURITY_EXPIRES.replace("Z", "+00:00"))
        valid = expiry > datetime.now(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid or not settings.SECURITY_CONTACT or not settings.SECURITY_CONTACT.startswith(("mailto:", "https://")) or "\n" in settings.SECURITY_CONTACT or "\r" in settings.SECURITY_CONTACT:
        return PlainTextResponse("Not configured\n", status_code=404)
    return f"Contact: {settings.SECURITY_CONTACT}\nExpires: {settings.SECURITY_EXPIRES}\nPreferred-Languages: en\n"

@app.get("/api/capabilities")
def capabilities():
    from core.capabilities import PRODUCT
    return PRODUCT


@app.get("/api/ready")
def readiness():
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from core.database import engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503,content={"status":"unavailable","dependency":"database"})
    return {"status":"ready"}

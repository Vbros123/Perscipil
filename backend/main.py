"""
PrivateLens API v3
Private company financial health research platform.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.database import init_db
from routers.auth import router as auth_router
from routers.compare import router as compare_router
from routers.history import router as history_router
from routers.score import router as score_router
from routers.settings import router as settings_router
from routers.users import router as users_router
from routers.watchlist import router as watchlist_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("privatelens")

settings = get_settings()

app = FastAPI(
    title="PrivateLens API",
    description="Private company financial health scoring, watchlists, reports, and user workspaces.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Response-Time"] = f"{ms}ms"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(auth_router)
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
    return {"status": "ok", "version": settings.APP_VERSION}

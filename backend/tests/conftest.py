import os
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_privatelens_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-value-that-is-long-enough-for-production-checks")
os.environ.setdefault("AUTH_TOKEN_RETURN_IN_RESPONSE", "true")
os.environ.setdefault("HTTP_TIMEOUT", "0.1")
os.environ.setdefault("PROVIDER_BUDGETS_ENABLED", "false")

db_url = os.environ["DATABASE_URL"]
if db_url.startswith("sqlite:///./"):
    Path(db_url.replace("sqlite:///./", "", 1)).unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture()
def api():
    with TestClient(app) as test_client:
        yield test_client


def strong_password(prefix: str = "Password") -> str:
    return f"{prefix}123!Secure"


@pytest.fixture(autouse=True)
def isolate_memory_auth_budget():
    """Each test is an independent client population; keep limits active within it."""
    from core.limiter import auth_limiter, SlidingWindowLimiter
    if isinstance(auth_limiter, SlidingWindowLimiter):
        auth_limiter._requests.clear()
    yield

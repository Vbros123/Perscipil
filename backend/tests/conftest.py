import os
from pathlib import Path

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_privatelens_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-value-that-is-long-enough-for-production-checks")
os.environ.setdefault("AUTH_TOKEN_RETURN_IN_RESPONSE", "true")
os.environ.setdefault("HTTP_TIMEOUT", "0.1")

TEST_DB = Path("test_privatelens_pytest.db")
TEST_DB.unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture()
def api():
    with TestClient(app) as test_client:
        yield test_client


def strong_password(prefix: str = "Password") -> str:
    return f"{prefix}123!Secure"

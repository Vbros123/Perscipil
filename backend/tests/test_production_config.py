import pytest

from core.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql://user:password@example.com/privatelens",
        "JWT_SECRET": "j" * 48,
        "ALLOWED_ORIGINS": "https://privatelens.vercel.app",
        "ALLOWED_HOSTS": "privatelens.onrender.com",
        "EMAIL_DELIVERY_MODE": "resend",
        "RESEND_API_KEY": "re_test_key",
        "SMTP_FROM_EMAIL": "security@example.com",
        "METRICS_TOKEN": "m" * 32,
        "DATA_MODE": "public",
    }
    values.update(overrides)
    return Settings(**values)


def test_free_production_stack_is_valid():
    production_settings().validate_runtime()


def test_licensed_mode_requires_gateway_credentials():
    settings = production_settings(DATA_MODE="licensed")

    try:
        settings.validate_runtime()
    except RuntimeError as exc:
        assert "Licensed data gateway" in str(exc)
    else:
        raise AssertionError("Licensed mode accepted missing gateway credentials")


def test_validated_release_requires_documented_approval():
    settings = production_settings(
        DATA_MODE="licensed",
        LICENSED_DATA_GATEWAY_URL="https://gateway.example.com/v2/evidence",
        LICENSED_DATA_API_KEY="g" * 32,
        MODEL_RELEASE_STAGE="validated",
    )

    with pytest.raises(RuntimeError, match="validation reference and approver"):
        settings.validate_runtime()


def test_validated_release_accepts_governance_metadata():
    settings = production_settings(
        DATA_MODE="licensed",
        LICENSED_DATA_GATEWAY_URL="https://gateway.example.com/v2/evidence",
        LICENSED_DATA_API_KEY="g" * 32,
        MODEL_RELEASE_STAGE="validated",
        MODEL_VALIDATION_REFERENCE="validation-2026-001",
        MODEL_VALIDATION_SHA256="a" * 64,
        MODEL_APPROVED_BY="Model Risk Committee",
    )
    settings.validate_runtime()

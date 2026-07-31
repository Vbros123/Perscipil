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

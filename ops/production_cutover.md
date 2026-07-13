# Production Cutover Checklist

## Infrastructure

- Managed Postgres provisioned and connected via `DATABASE_URL`.
- Render backend deployed from latest `main`.
- Vercel frontend deployed from latest `main`.
- `alembic upgrade head` runs during backend deploy.
- `AUTO_CREATE_TABLES=false` in production.

## Secrets

- `JWT_SECRET`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SENTRY_DSN`
- `METRICS_TOKEN`
- `LICENSED_DATA_GATEWAY_URL`
- `LICENSED_DATA_API_KEY`

## Verification

- `/api/health` reports Postgres, SMTP, Sentry, metrics, and licensed data enabled.
- Signup sends email verification.
- Forgot-password sends reset email.
- `/api/metrics` returns metrics only with the bearer metrics token.
- Backup script runs successfully.
- Restore drill passes in staging.
- External security review is scheduled or completed.
- Counsel has reviewed terms, privacy, and compliance positioning.

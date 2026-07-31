# Production Cutover Checklist

## Infrastructure

- Managed Postgres provisioned and connected via `DATABASE_URL`.
- Render backend deployed from latest `main`.
- Vercel frontend deployed from latest `main`.
- `alembic upgrade head` runs during backend deploy.
- `AUTO_CREATE_TABLES=false` in production.

## Secrets

- `JWT_SECRET`
- `RESEND_API_KEY`
- `SMTP_FROM_EMAIL`
- `METRICS_TOKEN`
- `SENTRY_DSN` (recommended, optional)
- `LICENSED_DATA_GATEWAY_URL` and `LICENSED_DATA_API_KEY` only for `DATA_MODE=licensed`

## Verification

- `/api/health` reports Postgres, Resend, metrics, and `data_mode=public`.
- Signup sends email verification.
- Forgot-password sends reset email.
- `/api/metrics` returns metrics only with the bearer metrics token.
- Backup script runs successfully.
- Encrypted scheduled backup workflow succeeds.
- Restore drill passes in staging.
- External security review is scheduled or completed.
- Counsel has reviewed terms, privacy, and compliance positioning.

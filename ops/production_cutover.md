> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

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
- `MODEL_RELEASE_STAGE=shadow` until independent validation approval
- `MODEL_VALIDATION_REFERENCE`, `MODEL_VALIDATION_SHA256`, and `MODEL_APPROVED_BY` only after approval

## Verification

- `/api/health` reports Postgres, Resend, metrics, and `data_mode=public`.
- `/api/health` reports `model_release_stage=shadow` before the licensed-data validation period.
- Signup sends email verification.
- Forgot-password sends reset email.
- `/api/metrics` returns metrics only with the bearer metrics token.
- Backup script runs successfully.
- Encrypted scheduled backup workflow succeeds.
- Restore drill passes in staging.
- External security review is scheduled or completed.
- Counsel has reviewed terms, privacy, and compliance positioning.

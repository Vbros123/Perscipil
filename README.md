# PrivateLens

PrivateLens is a full-stack private-company financial health research workspace. It combines a FastAPI scoring API with an authenticated React dashboard for company reports, peer comparison, watchlists, search history, account settings, pricing, and developer documentation.

Live frontend: https://privatelens.vercel.app

Backend docs: https://privatelens.onrender.com/docs

PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.

## Product Surface

- Account signup, login, JWT sessions, and `/api/auth/me`
- Password reset, password change, email verification scaffolding, and auth audit events
- SMTP transactional email delivery for password reset and email verification
- PrivateScore company reports with live/modelled signal labels
- User-specific history and saved company watchlists
- Peer comparison for two to four companies
- Workspace settings, account profile, pricing, and developer pages
- Alembic migrations, SQLite locally, and Postgres-ready `DATABASE_URL` support
- Sentry-ready observability, protected metrics, backup/restore scripts, and licensed data gateway contract

## Repository Structure

```text
backend/
  main.py
  core/
    config.py
    database.py
    limiter.py
    cache.py
    security.py
  alembic/
    env.py
    versions/
  models/
    user.py
    company.py
    settings.py
  routers/
    auth.py
    score.py
    compare.py
    history.py
    watchlist.py
    settings.py
    users.py
  schemas/
    auth.py
    company.py
    settings.py
  services/
    collectors.py
    licensed_data.py
    scorer.py
    history.py
    reports.py
ops/
  backup_postgres.sh
  restore_postgres.sh
  backup_runbook.md
  compliance_controls.md
  external_security_review.md
  licensed_data_gateway_contract.md
  production_cutover.md

frontend/
  src/
    api/
    components/
    context/
    pages/
    styles/
```

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend API docs run at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Vite runs on `http://localhost:3001`.

## Environment Variables

### Backend

| Name | Required | Default | Notes |
|---|---:|---|---|
| `DATABASE_URL` | Yes in production | `sqlite:///./privatelens.db` | Must be managed Postgres in production. |
| `JWT_SECRET` | Yes in production | `change-this-in-production` | Set a long random secret. |
| `JWT_EXPIRES_MINUTES` | No | `10080` | Default is seven days. |
| `AUTH_TOKEN_RETURN_IN_RESPONSE` | No | `false` | Test/dev only. Never enable in production. |
| `EMAIL_DELIVERY_MODE` | Yes in production | `console` | Use `resend` on Render Free or `smtp` where SMTP egress is supported. |
| `RESEND_API_KEY` | With `EMAIL_DELIVERY_MODE=resend` | | Resend HTTPS API key. |
| `SMTP_HOST` | With `EMAIL_DELIVERY_MODE=smtp` | | SMTP provider host. |
| `SMTP_PORT` | No | `587` | SMTP provider port. |
| `SMTP_USERNAME` | With `EMAIL_DELIVERY_MODE=smtp` | | SMTP username/API user. |
| `SMTP_PASSWORD` | With `EMAIL_DELIVERY_MODE=smtp` | | SMTP password/API key. |
| `SMTP_FROM_EMAIL` | Yes in production | `security@privatelens.com` | Verified sender. |
| `APP_PUBLIC_URL` | Yes in production | `http://localhost:5173` | Used for reset/verification links. |
| `SENTRY_DSN` | Recommended | | Enables optional Sentry error capture and traces. |
| `METRICS_TOKEN` | Yes in production | | Bearer token for `/api/metrics`. |
| `DATA_MODE` | No | `public` | Use `public` for open-data collectors or `licensed` for paid-provider overrides. |
| `LICENSED_DATA_GATEWAY_URL` | In licensed mode | | Normalization gateway for paid data feeds. |
| `LICENSED_DATA_API_KEY` | In licensed mode | | Bearer token for the gateway. |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated origins, for example `https://privatelens.vercel.app`. |
| `FRONTEND_URL` | No | `http://localhost:5173` | Added to CORS when `ALLOWED_ORIGINS` is not `*`. |
| `ALLOWED_HOSTS` | No | `*` | Set to `privatelens.onrender.com` in production. |
| `AUTO_CREATE_TABLES` | No | `true` | Use `false` in production and run Alembic migrations instead. |
| `HTTP_TIMEOUT` | No | `8.0` | External collector timeout. |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | Per-IP score/compare rate limit. |

### Frontend

| Name | Required | Example |
|---|---:|---|
| `VITE_API_URL` | Yes in production | `https://privatelens.onrender.com` |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/signup` | Create account and return bearer token |
| `POST` | `/api/auth/login` | Log in and return bearer token |
| `POST` | `/api/auth/logout` | Record logout audit event |
| `POST` | `/api/auth/change-password` | Change password and invalidate sessions |
| `POST` | `/api/auth/request-password-reset` | Issue reset token through configured delivery |
| `POST` | `/api/auth/reset-password` | Reset password with token |
| `POST` | `/api/auth/request-email-verification` | Issue email verification token |
| `POST` | `/api/auth/verify-email` | Verify email with token |
| `GET` | `/api/auth/me` | Current authenticated user |
| `GET` | `/api/compliance/status` | Readiness and compliance integration status |
| `GET` | `/api/metrics` | Protected Prometheus-style metrics |
| `PATCH` | `/api/users/me` | Update profile |
| `GET` | `/api/score?company=NAME` | Score a company and return a report |
| `GET` | `/api/compare?companies=A,B` | Compare two to four companies |
| `GET` | `/api/watchlist` | List saved companies |
| `POST` | `/api/watchlist` | Save or update a company |
| `PATCH` | `/api/watchlist/{id}` | Update saved notes/tags |
| `DELETE` | `/api/watchlist/{id}` | Remove saved company |
| `GET` | `/api/history` | Authenticated search history |
| `DELETE` | `/api/history` | Clear history |
| `DELETE` | `/api/history/{id}` | Delete one history row |
| `GET` | `/api/settings` | Get workspace settings |
| `PATCH` | `/api/settings` | Update workspace settings |
| `GET` | `/api/signals` | Signal library |
| `GET` | `/api/health` | Health check |

Authenticated endpoints use:

```bash
Authorization: Bearer <token>
```

## Deployment

### Render Backend

The included `render.yaml` deploys the API on Render Free. Use a Neon Free pooled Postgres connection for `DATABASE_URL`; Render Free Postgres expires after 30 days and has no backups.

1. Root directory: `backend`
2. Build command: `pip install -r requirements.txt && alembic upgrade head`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set all `sync: false` secrets in Render.
5. Keep `AUTO_CREATE_TABLES=false`.

SQLite works locally only. Production startup intentionally fails unless `DATABASE_URL` points to managed Postgres, metrics are protected, and email uses Resend or SMTP. Licensed gateway credentials are required only when `DATA_MODE=licensed`.

### Vercel Frontend

1. Root directory: `frontend`
2. Build command: `npm run build`
3. Output directory: `dist`
4. Environment variable: `VITE_API_URL=https://privatelens.onrender.com`
5. `frontend/vercel.json` rewrites all app routes to `index.html` for React Router.

## Data Sources And Limits

Live/free collectors currently include SEC EDGAR, Wikipedia, DuckDuckGo, HackerNews, and USASpending.gov. Some external pages such as job boards may block automated requests, in which case PrivateLens falls back to deterministic modelled signals.

`DATA_MODE=public` uses the built-in public/open-data collectors and keeps modelled signals visibly labeled. Paid data can later be enabled with `DATA_MODE=licensed` and `LICENSED_DATA_GATEWAY_URL`; the gateway must return the normalized schema documented in `ops/licensed_data_gateway_contract.md`. When a licensed signal is returned, PrivateLens includes provider/license metadata.

## Operational Readiness

- Backup and restore runbook: `ops/backup_runbook.md`
- External security review scope: `ops/external_security_review.md`
- Legal/compliance controls: `ops/compliance_controls.md`
- Licensed data gateway contract: `ops/licensed_data_gateway_contract.md`
- Production cutover checklist: `ops/production_cutover.md`

Free-tier backups are created by `.github/workflows/postgres-backup.yml` as encrypted, seven-day GitHub Actions artifacts. Add `PRODUCTION_DATABASE_URL` and `BACKUP_ENCRYPTION_KEY` as GitHub Actions secrets before enabling the workflow.

Manual backup example:

```bash
cd ops
DATABASE_URL="$PRODUCTION_DATABASE_URL" BACKUP_S3_URI="s3://your-private-bucket/privatelens" ./backup_postgres.sh
```

## Validation

Frontend:

```bash
cd frontend
npm run build
```

Backend smoke testing can be done with FastAPI `TestClient` or by running the server locally and calling signup, login, settings, watchlist, score, history, and compare endpoints.

Backend automated tests:

```bash
cd backend
ENVIRONMENT=test JWT_SECRET=test-secret-value-that-is-long-enough-for-production-checks AUTH_TOKEN_RETURN_IN_RESPONSE=true pytest -q
```

Migrations:

```bash
cd backend
alembic upgrade head
```

Metrics:

```bash
curl -H "Authorization: Bearer $METRICS_TOKEN" https://privatelens.onrender.com/api/metrics
```

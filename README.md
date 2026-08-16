# PrivateLens

PrivateLens is a full-stack private-company financial health research workspace. It combines a FastAPI scoring API with an authenticated React dashboard for company reports, peer comparison, watchlists, search history, account settings, pricing, and developer documentation.

Live frontend: https://privatelens.vercel.app

Backend docs: https://privatelens.onrender.com/docs

PrivateLens is a research tool and does not provide credit, investment, legal, or lending advice.

PrivateLens currently operates primarily on public and modelled signals. Licensed credit, cash-flow, and legal data integrations are architected but not enabled until legitimate provider agreements and credentials are available. Public collectors can be incomplete or unavailable. PrivateScore™ is a research/intelligence score and is not credit, investment, lending, legal, or financial advice.

## Product Surface

- Account signup, login, JWT sessions, and `/api/auth/me`
- Working password reset, password rotation, email verification, and auth audit flows
- SMTP transactional email delivery for password reset and email verification
- Evidence-gated company reports with observed, context-only, and unavailable-source labels
- Strict legal-entity resolution, licensed provider provenance, freshness checks, and reproducible input hashes
- Shadow-mode model governance that blocks ratings before independent validation approval
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
    evidence.py
    licensed_data.py
    scorer.py
    history.py
    reports.py
    providers/
      base.py
      public.py
      licensed.py
      registry.py
ops/
  backup_postgres.sh
  restore_postgres.sh
  backup_runbook.md
  compliance_controls.md
  external_security_review.md
  licensed_data_gateway_contract.md
  licensed_provider_plan.md
  model_validation_runbook.md
  production_cutover.md

provider_gateway/
  main.py
  providers/creditsafe.py
  tests/

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
| `DATA_MODE` | No | `public` | `public`, `licensed`, or `hybrid`. Missing licensed credentials fall back to public. |
| `LICENSED_DATA_GATEWAY_URL` | Optional | | HTTPS evidence gateway. Leave empty until a real provider is contracted. |
| `LICENSED_DATA_API_KEY` | Optional | | Bearer token for the gateway. Never commit a real key. |
| `MODEL_RELEASE_STAGE` | No | `shadow` | Use `validated` only after independent approval. |
| `MODEL_VALIDATION_REFERENCE` | With validated release | | Immutable validation packet ID. |
| `MODEL_VALIDATION_SHA256` | With validated release | | SHA-256 of the approved packet. |
| `MODEL_APPROVED_BY` | With validated release | | Independent reviewer or committee. |
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
| `GET` | `/api/score?company=NAME` | Backward-compatible company report request |
| `POST` | `/api/score` | Report request with legal name, country, registration number, postcode, and provider IDs |
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
| `GET` | `/api/providers` | Licensed provider catalog and gateway readiness |
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

SQLite works locally only. Production startup intentionally fails unless `DATABASE_URL` points to managed Postgres, metrics are protected, and email uses Resend or SMTP. Licensed gateway credentials are optional; if they are missing, `DATA_MODE=licensed` or `hybrid` falls back to public collectors instead of crashing.

### Vercel Frontend

1. Root directory: `frontend`
2. Build command: `npm run build`
3. Output directory: `dist`
4. Environment variable: `VITE_API_URL=https://privatelens.onrender.com`
5. `frontend/vercel.json` rewrites all app routes to `index.html` for the client-side Wouter router.

## Data Sources And Limits

PrivateLens currently operates primarily on public and modelled signals.

| Source | Quality when live | Notes |
|---|---|---|
| GLEIF | High | Free public LEI identity. No API key. Context only — never a PrivateScore input. Missing LEI is not negative. |
| SEC EDGAR | High | Context / not applicable for most private companies |
| USASpending | High | US federal awards only; a floor across retrieved pages |
| Wikipedia | Low | Identity and founding-year context |
| Indeed | Low | Job-count proxy; often blocked |
| DuckDuckGo / Hacker News | Low | Coarse keyword sentiment |
| Modelled signals | Modelled | Discounted; never treated as verified |
| Licensed credit / cash-flow / legal | High if configured | **Unavailable** until a real gateway and credentials exist |

Collectors run concurrently. One timeout cannot stop the rest. If every public collector fails, the report is **Insufficient public evidence** — no score is manufactured.

### DATA_MODE

- `public`: public collectors + clearly labelled modelled signals
- `licensed`: licensed gateway + public sources (requires `LICENSED_DATA_GATEWAY_URL` and `LICENSED_DATA_API_KEY`)
- `hybrid`: licensed when the gateway is configured, otherwise public fallback

Production currently uses `DATA_MODE=public`.

Licensed credit, cash-flow, and legal data integrations are architected in `backend/services/providers/` but not enabled. Connecting a real provider later:

1. Deploy `provider_gateway/` with vendor credentials (never in this repo).
2. Set `LICENSED_DATA_GATEWAY_URL` to the HTTPS evidence endpoint.
3. Set `LICENSED_DATA_API_KEY` to the shared bearer token.
4. Set `DATA_MODE=hybrid` or `licensed`.
5. Keep `MODEL_RELEASE_STAGE=shadow` until a validation packet is approved.

The gateway must return `privatelens.evidence.v2` observations. Vendor composite scores are rejected. PrivateLens does not invent financial, payment, credit, or legal records.

A licensed numeric rating still requires at least 70% licensed-weight coverage, verified legal identity, and two licensed providers, and remains blocked with `Validation hold` until `MODEL_RELEASE_STAGE=validated` plus `MODEL_VALIDATION_REFERENCE`, `MODEL_VALIDATION_SHA256`, and `MODEL_APPROVED_BY`.

## Licensed Data Architecture

```text
Company
   |
   +-- public collectors (GLEIF, SEC, Wikipedia, jobs, news, USASpending)
   +-- LicensedDataProvider (unavailable unless configured)
   |
Signal aggregator (standardized Signal objects)
   |
Scoring engine (does not care which vendor produced a signal)
   |
Report
```

See `ops/licensed_provider_plan.md` and `ops/licensed_data_gateway_contract.md`.

## Provider Gateway

The reference gateway currently implements Creditsafe authentication, exact entity matching, credit report retrieval, provider timestamp checks, and raw observation normalization.

```bash
cd provider_gateway
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8010
```

Keep `CREDITSAFE_ENABLED=false` until you have a signed contract, sandbox credentials, and a non-secret contract reference. Middesk requires a completed verification business ID and webhook flow. Codat requires a subject-company consent flow and connection ID.

## Operational Readiness

- Backup and restore runbook: `ops/backup_runbook.md`
- External security review scope: `ops/external_security_review.md`
- Legal/compliance controls: `ops/compliance_controls.md`
- Licensed data gateway contract: `ops/licensed_data_gateway_contract.md`
- Licensed provider and activation plan: `ops/licensed_provider_plan.md`
- Model validation and approval process: `ops/model_validation_runbook.md`
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

Provider gateway tests:

```bash
cd provider_gateway
PYTHONPATH=. pytest -q
```

Out-of-time model validation:

```bash
cd backend
PYTHONPATH=. python scripts/validate_model.py holdout.jsonl --output validation-result.json
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

## Known Limitations

- Production runs `DATA_MODE=public`. There is no live licensed credit, cash-flow, or legal feed.
- GLEIF is a free public identity source and requires no API key. A missing LEI is not evidence a company does not exist and does not change PrivateScore.
- Wikipedia, Indeed, and DuckDuckGo/Hacker News are coarse public collectors and are labelled low quality.
- Job boards and search engines may block or rate-limit automated requests.
- If every public collector times out, the result is Insufficient public evidence — not a guessed score.
- Company resolution uses public encyclopedic sources and can be ambiguous for common names.
- PrivateScore™ is not a credit bureau rating, investment recommendation, or lending decision.

## Roadmap

- Connect Creditsafe, Middesk, and Codat through the existing licensed gateway contract after signed agreements.
- Raise `MODEL_RELEASE_STAGE` to `validated` only after an independent out-of-time validation packet.
- Replace remaining low-quality public collectors as licensed coverage comes online.


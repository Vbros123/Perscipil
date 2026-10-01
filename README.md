# Perscipil

Private-company research MVP with account-owned pilot workflows. Perscipil and
PerpScore are temporary names pending brand review. The score is an
**evidence-weighted research score**, not a credit rating, lending decision,
default probability, or validated bankruptcy prediction.

Current status is defined in `product.json`, rendered by Pricing and exposed at
`GET /api/capabilities`. LIVE means implemented in this repository, not proof of
current deployment. No live infrastructure credentials were supplied for cleanup.

## Architecture

React 18 / Vite frontend; FastAPI API; SQLAlchemy and Alembic; Postgres in production,
SQLite for local work; optional vendor normalization gateway. Eleven weighted
signal definitions: six public-track definitions (including unavailable hiring)
and five licensed definitions. GLEIF and Census are context-only. Missing data
stays missing. Public coverage is not coverage of a company's full finances.

## Local setup

Use Python 3.12 and Node 22. From `backend`, create a virtual environment and run:

```sh
python -m pip install -r requirements.txt
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn main:app --port 8000
```

From `frontend`:

```sh
npm ci
npm run dev
```

Set `ALLOWED_ORIGINS=http://localhost:5173` in backend `.env` for credentialed browser
requests. `VITE_API_URL` defaults to `http://localhost:8000`. Bearer credentials stay
in memory and expire after 60 minutes: refresh requires sign-in. Optional cookie
sessions require `COOKIE_AUTH=true`, exact origins, and production HTTPS. There is
no automatic refresh token. Cross-site cookies on Vercel/Render require browser
verification; prefer same-site custom domains before enabling.

## Tests and scans

```sh
# backend
python -m pytest -q
python -m alembic upgrade head
# provider_gateway (separate working directory)
python -m pytest -q
# frontend
npm ci
npm run lint
npm run build
npm audit
```

`verification/` contains actual baseline and cleanup results, including skipped
live-source checks. Python lockfiles pin transitive versions; refresh intentionally
with pip-tools from `requirements.in`, then run tests and audit. These locks target
Python 3.12; they are not artifact-hash-verified supply-chain attestations.

## Pilot workflows

- Bulk screening: `/batches`, 100 CSV rows, 256 KiB, optional entity identifiers;
  duplicates removed, sequential steps, resumable stored progress, three attempts,
  review-required ambiguous matches, protected CSV exports. Keep page open while running.
- Customer API: `/developer`, hashed account-owned keys, score:read only,
  1,000-call lifetime pilot quota, revoke and rotate. `POST /api/v1/score` takes
  `X-API-Key`. Licensed redistribution disabled. No multi-user organizations.
- Corrections: `/research-review`, select owned report and submit issue. Trusted
  operator uses `backend/scripts/review_correction.py`; never automatic acceptance.
- Monitoring: saved subscriptions and in-app events; schedule
  `PYTHONPATH=. python scripts/run_monitoring.py` hourly from backend. Weekly per
  subscription, five-minute recovery lease. Deployment scheduler is not activated.
- Account export/deletion: `/account`. Reauthentication and typed confirmation;
  owned data removed, sessions/API keys invalidated, de-identified control history retained.
- Pilot metrics: `/api/pilot/reviews` and `/api/pilot/metrics`; self-reported paired
  analyst estimates, never fabricated ROI.

## Production deployment

Read `dataroom-prep/SECURITY_ARCHITECTURE.md` and `ops/cleanup_deployment.md`.
Back up and restore-test Postgres before applying migrations. Automatic migration
from Render build was removed; migrate deliberately before rollout. Production
requires exact CORS/hosts, strong JWT and metrics secrets, real email delivery,
and `RATE_LIMIT_BACKEND=database`. Do not use example contacts as real senders.

Run retention daily via `PYTHONPATH=. python scripts/retention.py`. Licensed
providers are fail-closed until permissions are explicitly configured. Codat stays
disabled pending per-account consent/cache isolation. No paid services were created.

## Diligence

Start with `PRE_FUNDRAISING_CLEANUP_REPORT.md` and `dataroom-prep/INDEX.md`.
Historical documents are preserved under `docs/historical/`; they are not current
validation evidence. Policy drafts require counsel review before publication.

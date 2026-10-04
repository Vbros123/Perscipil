# Perscipil

Private-company research MVP with account-owned pilot workflows. Perscipil is the
product brand and PerpScore is its research score. Legal entity and trademark
clearance remain subject to founder/counsel review. The score is an
**evidence-weighted research score**, not a credit rating, lending decision,
default probability, or validated bankruptcy prediction.

Current status is defined in `product.json`, rendered by Pricing and exposed at
`GET /api/capabilities`. LIVE means implemented in this repository, not proof of
current deployment. The Render connector is available; staging runtime secrets and verified email delivery
still require owner configuration. See `ops/STAGING_RENDER_SETUP.md`.

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

- Organizations: isolated owner/admin/member workspaces, verified-email invitations,
  revocation, role controls, password-confirmed ownership transfer and MFA policy.
- Bulk screening: durable jobs, 1,000 rows / 512 KiB, deduplication, idempotency,
  bounded retries/cancellation and protected formula-safe CSV exports. A supervised
  worker processes jobs independently of the browser.
- Customer API: versioned `/api/v1/workspace` routes, scoped/revocable hashed keys,
  tenant isolation, 10,000-new-request pilot lifetime quota and shared 120/minute limit.
  Older account-level `/api/v1/score` remains compatible. See `docs/CUSTOMER_API.md`.
- Corrections: report-scoped submissions, administrator review and immutable
  decision history; accepting a correction never changes historical evidence.
- Monitoring: weekly durable screenings with leases, retries, in-app events and
  operator-configured email/webhooks. Run `PYTHONPATH=. python scripts/run_worker.py`
  from `backend`; the worker also coordinates daily retention.
- Account export/deletion: reauthentication and typed confirmation, session/API-key
  invalidation and de-identified control history. Encrypted deletion-ledger replay
  is required after restoring older backups.
- Pilot metrics: self-reported paired analyst estimates, never fabricated ROI.

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

Start with `FINAL_AI_CLEANUP_REPORT.md` and `PERSPICIL_REBRAND_REPORT.md` and `dataroom-prep/INDEX.md`.
Historical documents are preserved under `docs/historical/`; they are not current
validation evidence. Policy drafts require counsel review before publication.

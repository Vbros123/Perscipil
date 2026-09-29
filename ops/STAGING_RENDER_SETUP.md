# Perspicil staging: Render dashboard steps

Prepared 2026-09-28 for `Vbros123/privatelens`, branch `final-pre-fundraising-cleanup`.
This creates isolated staging. Leave the existing `privatelens` production service and its database unchanged.

## 1. Reuse the staging database already created

Open https://dashboard.render.com/d/dpg-das6rme0tbcc73e2v1hg-a .
It is `privatelens-staging`, PostgreSQL 16, Oregon, available. Its free plan expires
2026-10-27. Under **Connections**, copy **Internal Database URL** directly into the
new service's `DATABASE_URL`. Do not paste it into chat or commit it. Keep external
network access disabled; the web service and worker must use the same workspace/region.

## 2. Create a new Web Service

Dashboard → **New + → Web Service** → connect existing GitHub repository.

| Field | Value |
|---|---|
| Repository | `Vbros123/privatelens` |
| Branch | `final-pre-fundraising-cleanup` |
| Name | `perspicil-staging-api` (if available; record the actual assigned URL) |
| Region | Oregon |
| Runtime | Python 3 |
| Root Directory | Leave blank; root `product.json` must be available |
| Build Command | `cd backend && pip install -r requirements.txt && alembic upgrade head && alembic check` |
| Start Command | `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance | Free for temporary staging API |
| Health Check Path | `/api/ready` |
| Auto-Deploy | Off; deploy the reviewed branch commit deliberately |

The build migration command is for this isolated staging database only. Do not copy
it onto production without its backup/migration rollout procedure.

## 3. Configure Environment before deploying

Use **Environment → Add Environment Variable**. No quotes are needed in the UI.
`ENVIRONMENT=production` deliberately turns on the application's production safety
checks, even though the Render service itself is isolated staging.

| Variable | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.14` |
| `ENVIRONMENT` | `production` |
| `APP_NAME` | `Perspicil API` |
| `DATABASE_URL` | Internal URL from step 1 |
| `AUTO_CREATE_TABLES` | `false` |
| `DEBUG` | `false` |
| `AUTH_TOKEN_RETURN_IN_RESPONSE` | `false` |
| `COOKIE_AUTH` | `false` |
| `RATE_LIMIT_BACKEND` | `database` |
| `DATA_MODE` | `public` |
| `MODEL_RELEASE_STAGE` | `shadow` |
| `POLICIES_PUBLISHED` | `false` |
| `POLICY_REACCEPTANCE_REQUIRED` | `false` |
| `ALLOWED_HOSTS` | Actual staging API hostname, without `https://` |
| `FRONTEND_URL` | `https://privatelens-git-final-pre-fundraisin-928d23-bruh-gangs-projects.vercel.app` |
| `APP_PUBLIC_URL` | Same exact frontend URL; used in verification/reset email links |
| `ALLOWED_ORIGINS` | Same exact frontend URL, without trailing slash; no wildcard |
| `SMTP_FROM_NAME` | `Perspicil Security` |
| `EMAIL_DELIVERY_MODE` | `resend`, or `smtp` if using an existing SMTP provider |
| `SMTP_FROM_EMAIL` | Existing provider-verified sender email; do not invent a domain |
| `RESEND_API_KEY` | Existing Resend key, only when mode is `resend` |
| `PUBLIC_DATA_USER_AGENT` | `Perspicil/4.0 (contact: vijithvelamuri@gmail.com)` |
| `SECURITY_CONTACT` | `mailto:vijithvelamuri@gmail.com` |
| `SECURITY_EXPIRES` | `2027-03-22T00:00:00Z` |

For SMTP mode instead, set `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, and `SMTP_USE_TLS=true`. Do not select console/disabled delivery:
real signup, verification and reset flows need a working sender.

Generate the following **new staging-only values** in your own terminal and copy
them directly to Render. Store a recovery copy securely. The three encryption keys
must be separate, and must remain stable across service restarts and restores.

```sh
python3 - <<'PY'
import base64, secrets
for key in ('JWT_SECRET', 'METRICS_TOKEN'):
    print(key + '=' + secrets.token_hex(32))
for key in ('MFA_ENCRYPTION_KEY', 'CONSENT_ENCRYPTION_KEY', 'DELETION_LEDGER_KEY'):
    print(key + '=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
PY
```

Do not reuse production secrets or paste the generated output into chat.
Leave licensed-provider and notification-webhook credentials unset until their
approved staging destinations are known.

## 4. Deploy and send back non-secret details

Click **Deploy Web Service**, then inspect build/runtime logs. The build must report
successful Alembic upgrade and no schema diff. Open `<actual-api-url>/api/ready`:
it must return HTTP 200. A 503 is a failed readiness check, not a successful deploy.

Send back **only the API URL and deploy commit SHA** (and any redacted error). I can
then configure/verify the Vercel preview connection using the exact origin. The
frontend needs branch-specific `VITE_API_URL=<actual-api-url>` and that exact host
in `frontend/vercel.json`'s `connect-src`; a new preview build is required. Do not
change the production Vercel environment variable.

## 5. Worker (required for queued jobs and monitoring)

Dashboard → **New + → Background Worker**, same repo/branch, Oregon, blank root.
Build: `cd backend && pip install -r requirements.txt`.
Start: `cd backend && PYTHONPATH=. python scripts/run_worker.py`.
Share the staging environment values and encryption keys from step 3, especially
`DATABASE_URL`. Use one worker instance initially. Set auto-deploy Off and deploy
exactly the API commit. Render workers need a paid instance: review the displayed
price before creating one. No paid worker has been purchased by this task.

Worker logs must show completed cycles. Browser verification must prove that a
submitted job completes, monitoring/delivery runs, and data stays tenant-scoped.
A passing API health check alone does not prove worker operation.

## 6. Backup and restore activation

Do not restore over either live database. The current `ops/cleanup_deployment.md` requires an approved private object-storage
destination, independently stored
backup/deletion-ledger encryption keys, scheduled backups and a separate disposable
restore target. The staging owner must choose and provision that destination;
credentials belong in the operator environment, not chat.

The older `ops/backup_runbook.md` is superseded; its direct plaintext S3-upload
example is disabled by the script and must not be used.

Then run the approved encrypted backup/restore procedure and deletion-ledger
replay against that disposable target. Record table/content fingerprint matches,
readiness after replay, worker behavior and measured recovery time. Keep access
closed while reconciling ownership/control history. CI's local Postgres drill is
useful evidence but does not replace this real-hosting restore.

## Completion gate

Staging must pass signup/verification, login/logout, reset, MFA/recovery, workspace
roles, search/report, bulk processing, monitoring, API keys, corrections and settings,
plus mobile/accessibility checks and restore verification. Only then promote through
PR #10 and the normal production workflow. No production promotion is claimed here.

Sources: https://render.com/docs/configure-environment-variables ,
https://render.com/docs/postgresql-creating-connecting ,
https://render.com/docs/web-services , https://render.com/docs/background-workers .

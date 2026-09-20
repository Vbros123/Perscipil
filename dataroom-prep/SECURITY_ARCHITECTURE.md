# Security architecture

## Authentication and sessions

PBKDF2-SHA256 salted password hashes remain. JWTs require issuer, audience, expiry,
issued-at, access type, numeric subject and token version. Default lifetime reduced
to 60 minutes. Password changes/reset/logout revoke all existing user JWTs through
a stored version. Browser bearer tokens now live only in memory; legacy
localStorage tokens are removed. There is deliberately no silent refresh.

Optional HttpOnly cookies use Secure and SameSite=None in production, Lax locally,
with exact-origin checks for writes and rejection of cookied writes without Origin.
Cookie mode is opt-in because unrelated Vercel/Render domains may be blocked as
third-party cookies. Verify actual browsers or use same-site custom domains.

## Authorization and data ownership

Every new workflow query is account-filtered. API keys are hashed with SHA256 of
high-entropy secrets, shown once, revocable, account-scoped and restricted to the
versioned scoring endpoint. They never authorize internal app endpoints. Individual
accounts are not organizations; team marketing is marked planned. Corrections
reference owned saved reports. Review tools require trusted server access.

## Abuse and network controls

Production refuses process-only limiting. Atomic database fixed-window counters
share score/auth quotas across workers and fail closed on database errors. Local
fallback is bounded process memory. Auth routes have a shared per-client quota;
existing account lockout remains. Score routes and workflows have per-IP/account
limits. CSV rows, bytes, requests, retries and outstanding batches are bounded.
Global vendor request-per-second budgets remain a scaling limitation.

Application auth no longer trusts X-Forwarded-For. Uvicorn must trust only the
sanitizing deployment proxy, never unrestricted forwarded headers. Configure
trusted proxy addresses and verify client IP behavior before public rollout.
Exact production CORS and TrustedHost are required. Frontend CSP restricts script,
API origin and framing; changing domains requires updating CSP. Backend CSP,
HSTS, nosniff, referrer and permissions headers are applied. API responses use
no-store. Production interactive docs are disabled; diagnostic routes require the
metrics bearer secret. Health returns only status.

## Storage and observability

Postgres encryption/backup protection depends on hosting configuration and has not
been verified here. Secrets remain environment values. Do not commit `.env`.
SQLite foreign keys are enabled locally. Structured logs use generated correlation
IDs, basic token/email redaction and scrubbed Sentry request/user/breadcrumb/extra
fields. Local variables are excluded from Sentry. Redaction is defense in depth,
not a reason to log provider payloads.

## Operations

Versioned migrations, dependency locks, CI build/tests, dependency audit, Bandit,
Ruff and ESLint are included. Security.txt needs a real Contact URI and future
expiry; it returns 404 until configured. Backup scripts verify dump structure and
checksums, enforce private local file permissions and reject direct plaintext S3
uploads. Existing encrypted GitHub-artifact workflow is short-term backup only.
No production restore drill or independent penetration test was performed.

Incident response: restrict compromised key/account, revoke sessions, preserve
minimal audit evidence, investigate scope, rotate affected credentials, restore
from tested backup if needed, and have the accountable operator/counsel determine
notification obligations. No compliance certification is asserted.

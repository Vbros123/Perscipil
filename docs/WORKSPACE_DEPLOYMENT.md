# Workspace branch activation

This branch adds backend tables and routes. A Vercel preview only deploys the frontend; it cannot activate the Render API or background worker.

1. Back up the backend database and prove restoration into isolated Postgres staging.
2. Deploy this branch to staging with public-only provider mode, shared database limiter, trusted frontend origins, and a durable MFA encryption key from secret management.
3. In staging run `alembic upgrade head`, `alembic check` and the full backend tests using a disposable test database. Never point pytest at customer data.
4. Start the supervised worker: `PYTHONPATH=. python scripts/run_worker.py`. Schedule `PYTHONPATH=. python scripts/retention.py` daily. Both use the same securely configured database as the API.
5. Set `NOTIFICATION_DESTINATIONS_JSON` only through operator-managed secrets. Configure organization ID, channel and delivery destination; webhook keys must be strong secrets. Verify deliveries and retries in staging.
6. Configure published policy text and versions before enabling required reacceptance. Configure legal-approved retention periods explicitly.
7. Point the preview frontend at staging, allow its origin in backend CORS, and exercise sign-in, MFA, tenant isolation, queue completion and notification history end to end.
8. Complete the remaining gates in `FINAL_AI_CLEANUP_REPORT.md` before production migration and promotion.

Do not rotate MFA encryption keys without a decrypt-and-reencrypt migration; losing the key prevents TOTP verification. Keep licensed providers disabled until permission and consent integration is complete.

## September 26 hardening

Upgrade through `ad421f560371` before starting API/worker. It adds a portable MFA recovery-code compare-and-swap counter, shared operation leases, and a minimal deletion ledger. Configure independent durable `MFA_ENCRYPTION_KEY` and `CONSENT_ENCRYPTION_KEY`; never rotate either without a migration plan. The provider client enforces two buffered requests per provider across processes, a 90-second total request timeout and 120-second crash-recovery leases. Daily retention is coordinated with a shared lease. Monitor `worker_cycle_failed`, retry exhaustion, stale worker cycles and provider errors in the existing structured logs.

Before opening a restored database, export the latest deletion ledger from the current source using `DELETION_LEDGER_KEY` and `PYTHONPATH=. python scripts/deletion_ledger.py export /secure/new-ledger.fernet`. Store it in a separate access-controlled, versioned destination. Replay with the same key and the isolated restore target's `DATABASE_URL`, using `... deletion_ledger.py replay /secure/new-ledger.fernet`. Replay is idempotent and matches hashed account identity plus creation time, not reused integer IDs. Do not reopen service when a newer ledger cannot be obtained. Hosting automation and freshness monitoring for this external destination require backend/storage access; the test drill is not proof that production backup storage is configured.

Ownership transfer now requires the acting owner's password. MFA enforcement requires the owner to enroll first. Corrections support administrator review history and terminal acceptance/rejection; accepting a correction never edits an immutable research report. Correct the source evidence and rescreen.

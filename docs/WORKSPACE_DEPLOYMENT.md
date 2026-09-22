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

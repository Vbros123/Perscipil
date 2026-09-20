# Cleanup rollout — current runbook

1. Review final report and versioned diff. No deployment credentials or original
   Git history were supplied; local commits begin with imported archive snapshot.
2. Provision/use approved Postgres. Take encrypted backup, validate checksum,
   restore into isolated test database and compare counts before migration.
3. Install Python 3.12 locked requirements. Set strong JWT/METRICS secrets, real
   email sender/provider, exact HTTPS FRONTEND_URL/APP_PUBLIC_URL/CORS, allowed
   backend hosts; RATE_LIMIT_BACKEND=database, AUTO_CREATE_TABLES=false,
   AUTH_TOKEN_RETURN_IN_RESPONSE=false, DEBUG=false. Never copy test secrets.
4. With a maintenance/recovery plan run `python -m alembic upgrade head`; verify
   `python -m alembic check`. Start API only after schema exists. The additive pilot
   migration imports frozen model declarations and reflects parent tables; execute
   online with database access, not offline SQL generation.
5. Frontend: npm ci, npm run lint, npm run build. Configure VITE_API_URL and align
   frontend CSP connect-src with the real API host. Local Vite uses port 5173.
6. Verify signup/login, reset email, verification, logout revocation, account export,
   batch upload/resume/export, foreign-account 404s, key revocation and deletion in
   staging. No production smoke check has been represented as passed here.
7. Default session mode is memory-only bearer. Cookie mode needs same-site domain
   or explicit supported-browser validation; do not enable it blindly across sites.
   Configure Uvicorn forwarded-allow-ips to the trusted proxy only; confirm edge
   sanitization and rate-limit client identity. Fail closed if this is not known.
8. Before licensed activation, complete vendor permissions AND verify daily
   retention scheduling/backup expiry. Codat stays disabled. Scheduled monitoring
   uses hourly run_monitoring.py; weekly reevaluation and in-app events only. No
   email/webhook delivery promises. Monitor worker failures and retention outcomes.
9. Configure security.txt with a real mailto/HTTPS contact and future ISO expiry.
   Have counsel review policy drafts, publish immutable approved versions, then
   enable policy acceptance support. Do not mark old users accepted automatically.
10. Rollback: preserve a pre-migration backup and previous deploy artifact. Stop
    new writes before restore; coordinate both app and database rollback. Never
    downgrade a populated pilot schema casually (it drops pilot data).

Encrypted CI artifacts are not disaster recovery. Durable offsite encrypted backup,
key custody, restore drill, retention enforcement and reapplication of deletion
requests after restore must be established before institutional production use.

# Perscipil staging worker — prepared, not deployed

This is a proposed additional Render Background Worker. Creating it incurs recurring compute charges and requires owner approval. No resource has been purchased or created by this plan.

| Setting | Value |
| --- | --- |
| Name | perscipil-staging-worker |
| Repository | Vbros123/Perscipil |
| Branch | final-pre-fundraising-cleanup |
| Region | Oregon, alongside the existing staging database |
| Runtime | Python 3.12.14 |
| Root directory | backend |
| Build command | pip install -r requirements.txt |
| Start command | PYTHONPATH=. python scripts/run_worker.py |
| Instances | 1 |
| Proposed compute | 512 MB / less than 1 CPU, listed at $7/month |
| Shutdown allowance | 300 seconds |
| Automatic deploy | Disabled during staging acceptance |

Reuse the staging API's configuration through Render's secure environment controls, particularly its internal DATABASE_URL, JWT_SECRET, METRICS_TOKEN, separate encryption keys, exact frontend origins, Resend credentials, sender and public-data identity. Never commit values or create new incompatible encryption keys for the worker. Preserve ENVIRONMENT=production, DEBUG=false, AUTO_CREATE_TABLES=false, RATE_LIMIT_BACKEND=database, AUTH_TOKEN_RETURN_IN_RESPONSE=false, COOKIE_AUTH=false, DATA_MODE=public and MODEL_RELEASE_STAGE=shadow. No Redis is needed: this worker uses the application's Postgres-backed queue.

Migrations run on the API build before starting the worker. Do not add competing migration commands to worker startup. Its current source supports SIGTERM draining and database leases for retention and job processing.

## Acceptance after activation

1. Verify worker startup validation and a successful worker_cycle log.
2. Submit a staging job through the authenticated frontend and verify terminal progress and tenant isolation.
3. Verify a scheduled monitoring cycle, real approved email delivery and retry behavior.
4. Verify the retention lease and retention_completed event; exercise safe fixture data only.
5. Verify restart recovery without duplicate job completion or delivery, and configure actionable failure alerts.

Price source: https://render.com/pricing, checked 2026-10-04 UTC. Confirm the displayed price and billing terms before creation. This compute charge does not include additional database, backup storage, or email charges. The current free staging database expires in late October and needs its own durability decision.

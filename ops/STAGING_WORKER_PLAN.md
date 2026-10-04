# Perscipil free background processing

The owner requires $0 hosting. Do not create a paid background-worker service.

Set EMBEDDED_WORKER_ENABLED=true on the existing staging web service. The API lifespan supervises the existing worker in a separate process on the same compute instance, so synchronous worker operations do not block the HTTP event loop. It inherits the API configuration and internal database connection. No separate account, compute plan or Redis is required.

Use one Uvicorn worker per free instance. The switch defaults to false, so activation is explicit. Shutdown sends SIGTERM, permits 20 seconds of draining, then kills and reaps a stuck child. Unexpected exits are logged and restarted with bounded backoff. Durable database queues and leases retain pending work across restarts.

## Free-tier behavior

This does not prevent Render from sleeping. While asleep, processing and scheduled monitoring pause. Due work is picked up after the service wakes. Cold starts, delayed deliveries and shared memory/CPU limits remain. There is no promise of exact-time scheduling or continuous monitoring. No artificial keep-alive traffic is configured.

Render free services share 750 monthly instance hours per workspace. Free Postgres expires after 30 days; the existing staging database still needs migration to a durable free database before expiry. No database replacement or backup activation is implied by this worker change.

## Verification

Tests exercise crash restart and forced shutdown/reaping. Before production activation, confirm worker_cycle and retention_completed logs in staging, complete an authenticated queue job and delivery test, inspect memory pressure, and verify retention policy settings. Enable production separately after those checks. Keep EMBEDDED_WORKER_ENABLED=false to disable processing without changing code.

Reference: https://render.com/docs/free

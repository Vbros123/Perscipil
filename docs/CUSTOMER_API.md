# Workspace API pilot

Create a key in Team workspaces as owner or admin. Store its once-shown value securely and send it in `X-API-Key`. Keys are workspace-specific and immediately revocable. A key never accesses another workspace's reports or jobs.

- `POST /api/v1/workspace/scores`, scope `score:read`: JSON `{"identity":{"legal_name":"Example company"},"idempotency_key":"unique-request-123"}`. Returns 202 with `job_id` and state. Reusing the key with different input returns 409. Poll job status; do not treat 202 as a finished score.
- `GET /api/v1/workspace/jobs/{id}`, scope `score:read`: pending, running, retry, complete, failed or cancelled state with report/error references.
- `GET /api/v1/workspace/reports?after=0&limit=50`, scope `reports:read`: `items` plus `next_cursor`. Continue while the cursor is non-null. Maximum limit 100.

All keys for one workspace share 120 requests per minute. Respect 429 and Retry-After; use exponential backoff with jitter. New score submissions share a 10,000-request pilot lifetime quota; idempotent retries do not create duplicate work. The outstanding queue is limited to 2,000. A worker must be activated before jobs complete. Licensed inputs are disabled for workspace jobs until contracted consent integration is activated.

Responses can have unavailable scores. This product does not provide a validated default probability or formal credit rating. The authoritative request/response schemas are generated in `/openapi.json`.

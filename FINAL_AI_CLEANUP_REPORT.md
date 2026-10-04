# Final AI cleanup report

Updated 2026-10-04 UTC. Current product brand: **Perscipil**, with **PerpScore** as the display label. Historical rebrand reports record earlier spellings. PR #10 is merged into main. The redesigned production frontend is live at https://perscipil.vercel.app/ and the production API readiness check passes. Operational verification remains incomplete; public availability does not certify the authenticated workflows. A frontend preview is not a full-stack staging deployment.

## 1. Executive Summary

Fixed the red SQLite migration and the Postgres quota-key overflow. Implemented the missing workspace security, monitoring/correction controls, customer API read limits, separate consent encryption, portable one-use recovery codes, shared provider concurrency limits, daily retention coordination, and deletion replay tooling. Completed the redesigned twelve-slide investor deck, with an actual research-terminal screenshot and explicitly labeled commercial hypotheses. Expanded CI to real PostgreSQL, encrypted restore verification and full-history Gitleaks scanning. Remaining environment-dependent technical gates are listed explicitly below; this report does not claim all engineering is finished.

## 2. Baseline and Git

The redesign/security cleanup was merged as `c468ac0465cecb1d1b7e3e3035d2e298ab883bca` through PR #10 after all five CI jobs passed. PR #22 adds opt-in background processing on existing free web compute; staging verification precedes production worker activation. Remote history has not been rewritten.

## 3. Organizations / RBAC

Isolated organizations, owner/admin/member roles, verified-email invitation acceptance, revocation, role controls, password-confirmed ownership transfer, tenant-scoped reports/jobs/keys/audits. Workspace MFA policy is now actively enforced. Account MFA settings remain accessible so unenrolled members can recover access. Personal data remains separate. Tests cover isolation, authorization, revocation, MFA policy and transfer reauthentication.

## 4. Monitoring and corrections

Weekly durable screening with leases, retries, fenced completion, idempotent material-change events, in-app delivery and operator-configured email/webhooks. Webhook signatures include timestamp, event ID and body; receivers must persist IDs to prevent repeated processing. Retry-After is honored for 429/503. UI supports scheduling/stopping monitors, delivery history, correction submission and administrator review with terminal decisions and append-only review history. Accepting a correction does not alter immutable report evidence.

## 5. Bulk screening and concurrency

1,000 rows / 512 KiB CSV, deduplication, idempotent batch submission, 2,000 outstanding jobs per workspace, bounded retry/cancellation, paginated progress and formula-safe CSV downloads. One active job per workspace across workers; cycle ordering considers the last service time across all workspace jobs. Real Postgres tests complete a 1,000-job fixture across 20 workspaces. This is deterministic fixture throughput, not a live-provider production capacity promise. Shared database rate budgets and two concurrent buffered requests per provider are enforced; timeout/cancellation releases capacity, with expiring leases after worker death.

## 6. Customer API

Versioned `/api/v1/workspace` routes, hashed/revocable scoped keys, isolated jobs/reports, idempotency, pagination, 10,000-new-request pilot lifetime quota and shared 120/minute request limit. Documentation: `docs/CUSTOMER_API.md`; generated schemas: `/openapi.json`. Workspace workers continue to reject licensed mode until the consented vendor integration is activated.

## 7. Provider / consent isolation

Tenant, subject, connection, expiry, revocation and boolean-purpose permissions guard encrypted payloads. Unknown or non-permission fields cannot authorize access. Separate `CONSENT_ENCRYPTION_KEY` is required, independent of MFA. Invalid encryption configuration and unavailable ciphertext fail closed. Vendor contracts/credentials are not supplied; no Codat activation or legal permission is implied.

## 8. Authentication / MFA / policies

Encrypted TOTP seed, manual setup key and authenticator URI, password reauthentication, TOTP replay protection, recovery-code atomic compare-and-swap on SQLite and Postgres, audit and session-version invalidation. Concurrent recovery-code test permits exactly one successful use. Required policy reacceptance has regression coverage and preserves account-management access. Approved policy text and durable encryption keys must be configured by the authorized infrastructure owner before activation.

## 9. Browser verification

The deployed preview homepage and login/MFA form were inspected in the browser. The prior preview had no application-origin console errors in these public routes; extension/Vercel sign-in messages were excluded. Authenticated workspace, MFA, correction, batch and delivery journeys remain unverified against a deployed backend. Cross-browser/mobile and full accessibility automation are still release gates. No fabricated browser success is claimed.

## 10. Deployment

The Vercel project is now named `perscipil`. Cleanup commit `031925cecd77dfac598a9abb2585f93380b6a4ce` built successfully after setting a branch-specific Preview `VITE_API_URL` to the isolated Render staging API. Render frontend/public URL and exact CORS origin were updated to match the new preview alias. The frontend CSP permits the staging API. Production frontend promotion is complete. The branded alias https://perscipil.vercel.app/ is verified and serves the redesign. Production Render startup was repaired by selecting the shared database rate limiter and a supported Python runtime; readiness returned HTTP 200 on 2026-10-04. Production public URL and CORS origins now include the branded alias.

The isolated API runs against hosted PostgreSQL; migration upgrade and schema-diff checks pass. Secure runtime keys are configured, and Render readiness probes have returned HTTP 200. Email credentials are configured, but the sender and actual delivery are not verified. The embedded worker is active in staging: commit `24d1bddd048ffcb698d98e95fe63062f1ce94c9a` logged successful retention and repeated worker cycles on 2026-10-04 at 15:47 UTC. The empty queue was healthy; real authenticated jobs and outbound delivery remain unverified. The offsite backup destination and real hosted restore remain outstanding. Direct connector SQL is unavailable because the database deliberately blocks external connections; its allowlist has not been weakened.

Vercel preview protection remains enabled. The owner explicitly approved temporary preview access, which was created and used successfully. Authenticated application workflows still require a staging account; preview access alone does not sign into Perscipil.

## 11. Backups / restore

CI run 36206441543 at cleanup SHA `f721a586bee1754508aef700bfae5c1dbbc08c31` passed the expanded encrypted Postgres restore: all 31 tables / 3,359 rows matched by content fingerprints, migrations and restored readiness passed, and a post-backup deletion replayed idempotently. Rebrand CI is tracked separately in the rebrand report. `scripts/deletion_ledger.py` exports/replays a separate encrypted minimal ledger. Production storage, current-ledger freshness, key custody, backup expiry, scheduling and restore RTO/RPO must be activated and measured in the real hosting environment. Ephemeral CI restore success is not a production backup certification.

## 12. Database / operations

Portable SQLite migrations through `ad421f560371` and schema diff check pass. PostgreSQL tests cover simultaneous enqueue/idempotency, single active claims, stale completion fencing, exact quotas, concurrent recovery use, 1,000 completed jobs and pool-exhaustion recovery. Postgres pool is bounded at 5 + 5 overflow with a five-second checkout timeout. `/api/health` is liveness; `/api/ready` checks database connectivity and returns 503 on database failure. Protected aggregate queue/delivery metrics supplement structured worker/provider logs. Daily retention uses a shared database lease. Runtime alert destinations remain unverified. Opt-in subprocess worker supervision is implemented on existing free compute and enabled in staging; production activation is a separate gate.

## 13. Security scans

CI runs dependency audits, Ruff correctness, Bandit high-severity checks, tracked-file scan and Gitleaks full reachable Git history plus working tree with redacted output. Run 35797477198 found no leaks across 35 commits. Subsequent pushed code also passed the secret-history job. No credential rotation is represented as completed or needed based on a detected real secret. External penetration testing remains independent human work.

## 14. Validation infrastructure

Entity-disjoint time partitions, leakage checks, ROC-AUC, average precision, Brier/calibration, error rates, subgroup metrics, bootstrap intervals, shift and baseline comparison. Optimized rank calculations and bootstrap support a 20,000-row fixture regression. Resolver collection now calls the production resolver and compares canonical/LEI/CIK/domain IDs to independent expected labels. `scripts/evaluate_cohort.py` provides a reproducible file-based CLI. Fixture categories exercise infrastructure; representativeness and real predictive validity are not established. **NOT VALIDATED ON REAL OUTCOMES.**

## 15. Corrected deck

The current deliverable is `Perscipil_Investor_Deck.pptx`: twelve editable slides using the new graphite/teal product screenshots within a clean investor presentation. All twelve slides were rendered and visually checked. Market context is sourced, pricing and pilot goals are hypotheses, and fictional demo companies are identified. This replaces the older seven-slide corrected PDF as the requested pitch deliverable; older PDFs are historical artifacts, not the latest deck.

## 16. Verification evidence

- Worker fix `24d1bddd048ffcb698d98e95fe63062f1ce94c9a`: PR CI run 37214219135 passed all five jobs, including PostgreSQL and encrypted restore. Local focused worker/config/delivery regressions: 15 passed. Hosted staging retention and worker cycles succeeded; readiness remained HTTP 200.

- Current cleanup commit `031925cecd77dfac598a9abb2585f93380b6a4ce`: CI run 37174459116 passed all five jobs (frontend, backend, PostgreSQL, provider gateway, secret history). This is the same code tree as `d8f879b3e20e05c02a42da35009533451001cac7`, rebuilt with the new staging configuration.
- Hosted Render migration/schema check passed on 2026-10-04 UTC. Hosted restore and authenticated browser journeys are still separate, incomplete gates.

Historical evidence:

- Previously green full CI: 35797477198 (five jobs).
- Expanded Postgres run 36206051904: 150 tests passed in 32.82s, including the 1,000 completed-job fixture; restore CLI then exposed a missing SQLAlchemy model registration, now fixed.
- Latest local full backend suite before the final additional regressions: 145 passed, five environment-specific skips. Focused policy/MFA/cohort regressions: 12 passed.
- Latest local frontend lint/build: passed. Fresh SQLite migration/schema check: passed. Ruff correctness: passed.
- Cleanup CI run 36206441543 at `f721a586bee1754508aef700bfae5c1dbbc08c31`: all five jobs passed; Postgres 155 tests passed with two warnings. Rebrand verification is recorded separately; do not infer its results from this earlier SHA.

## 17. Remaining technical release gates

1. Finish the staging worker and verify real email/delivery destinations. The isolated API, runtime keys, exact CORS/CSP configuration, migration startup and readiness checks are configured. The owner requires $0 hosting. An opt-in embedded worker uses existing web-service compute and respects free-service sleep; no paid worker is needed. See `ops/STAGING_WORKER_PLAN.md`. Production worker activation awaits hosted queue/delivery and retention checks.
2. Execute the deployed authenticated browser journeys, responsive/accessibility checks, staging migrations, worker/delivery verification, and an encrypted restore using the actual hosting/backup destination. CI proves code behavior, not this operational deployment.
3. Activate offsite encrypted backups, separate current deletion-ledger storage/freshness monitoring, retention and alerting. Verify ownership/control-history reconciliation after restoring older backups; do not reopen a restore with unresolved ownership state.
4. Review and remediate findings before declaring authenticated workflows operational. The public production frontend is already live.
5. Migrate staging PostgreSQL to a durable free database before the current Render free database expires on 2026-10-27 UTC; verify migration and restore before switching connections.

These remain technical work blocked on infrastructure access, not contractual/customer work. Do not label this release “human-only remaining” until these gates are completed.

## 18. Human / external requirements

Founder/counsel: approved policy text and retention periods, trademark/name clearance, incorporation and IP signatures. Vendors: contracts, granular permissions and securely configured credentials. Independent security firm: penetration testing and retest evidence. Pilot partners: actual customers, agreements and lawful representative outcome cohorts. Investors/founder: funding and signed commitments. No traction, permissions, legal approval or predictive validation has been invented.

## 19. Readiness

Implemented and inspectable research MVP; branded public production frontend available. Institutional staging verification remains gated on authenticated browser access, worker activation, verified delivery and an actual offsite backup/restore drill. Production frontend deployment is complete; there is no enterprise readiness certification. Updated capability metadata and deployment/API documentation describe implemented versus activated behavior explicitly.

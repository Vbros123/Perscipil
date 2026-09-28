# Final AI cleanup report

Updated 2026-09-28. Current product brand: Perspicil; see `PERSPICIL_REBRAND_REPORT.md`. Engineering work is on `final-pre-fundraising-cleanup`, draft PR #10. Production promotion remains gated on backend staging activation and authenticated browser verification. A frontend preview is not a full-stack staging deployment.

## 1. Executive Summary

Fixed the red SQLite migration and the Postgres quota-key overflow. Implemented the missing workspace security, monitoring/correction controls, customer API read limits, separate consent encryption, portable one-use recovery codes, shared provider concurrency limits, daily retention coordination, and deletion replay tooling. Completed the corrected seven-slide deck. Expanded CI to real PostgreSQL, encrypted restore verification and full-history Gitleaks scanning. Remaining environment-dependent technical gates are listed explicitly below; this report does not claim all engineering is finished.

## 2. Baseline and Git

Production baseline remains `3ed1df1d58e821c246a91b04982f5511ce22d250`. Changes are additive on the dedicated branch; production has not been promoted. Local imported history is synchronized through identical Git trees without rewriting remote history. PR: https://github.com/Vbros123/privatelens/pull/10.

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

Vercel builds the branch successfully. Verified preview for `fc0a9ad0de1c5467e6ea47f6399d6f1eeb58d4b8`: https://privatelens-kzgu41ie6-bruh-gangs-projects.vercel.app. Its frontend still references the existing Render API; this is not an isolated backend staging environment. The Render connector is available. Isolated PostgreSQL 16 database `dpg-das6rme0tbcc73e2v1hg-a` is available in Oregon (free expiry 2026-10-27). The user requested dashboard instructions for remaining Render configuration; see `ops/STAGING_RENDER_SETUP.md`. API/worker runtime secrets, verified mail and an approved backup destination are still unconfigured. A real founder contact from the supplied deck is published as frontend security.txt; backend contact remains configurable.

## 11. Backups / restore

CI run 36206441543 at cleanup SHA `f721a586bee1754508aef700bfae5c1dbbc08c31` passed the expanded encrypted Postgres restore: all 31 tables / 3,359 rows matched by content fingerprints, migrations and restored readiness passed, and a post-backup deletion replayed idempotently. Rebrand CI is tracked separately in the rebrand report. `scripts/deletion_ledger.py` exports/replays a separate encrypted minimal ledger. Production storage, current-ledger freshness, key custody, backup expiry, scheduling and restore RTO/RPO must be activated and measured in the real hosting environment. Ephemeral CI restore success is not a production backup certification.

## 12. Database / operations

Portable SQLite migrations through `ad421f560371` and schema diff check pass. PostgreSQL tests cover simultaneous enqueue/idempotency, single active claims, stale completion fencing, exact quotas, concurrent recovery use, 1,000 completed jobs and pool-exhaustion recovery. Postgres pool is bounded at 5 + 5 overflow with a five-second checkout timeout. `/api/health` is liveness; `/api/ready` checks database connectivity and returns 503 on database failure. Protected aggregate queue/delivery metrics supplement structured worker/provider logs. Daily retention uses a shared database lease. Runtime alert destinations and worker supervision are not activated without hosting access.

## 13. Security scans

CI runs dependency audits, Ruff correctness, Bandit high-severity checks, tracked-file scan and Gitleaks full reachable Git history plus working tree with redacted output. Run 35797477198 found no leaks across 35 commits. Subsequent pushed code also passed the secret-history job. No credential rotation is represented as completed or needed based on a detected real secret. External penetration testing remains independent human work.

## 14. Validation infrastructure

Entity-disjoint time partitions, leakage checks, ROC-AUC, average precision, Brier/calibration, error rates, subgroup metrics, bootstrap intervals, shift and baseline comparison. Optimized rank calculations and bootstrap support a 20,000-row fixture regression. Resolver collection now calls the production resolver and compares canonical/LEI/CIK/domain IDs to independent expected labels. `scripts/evaluate_cohort.py` provides a reproducible file-based CLI. Fixture categories exercise infrastructure; representativeness and real predictive validity are not established. **NOT VALIDATED ON REAL OUTCOMES.**

## 15. Corrected deck

`PrivateLens_Corrected_Deck.pdf` is complete as a separate saved copy, retaining seven original slide layouts. All slides were visually inspected; a leftover title glyph was removed. Updated signal counts and source availability, replaced stale screenshots, removed simulated-evidence and unsupported performance/activation implications, labeled target pricing/customers as proposed. Founder market figures retain a verification caveat. See `docs/DECK_CHANGELOG.md`.

## 16. Verification evidence

- Previously green full CI: 35797477198 (five jobs).
- Expanded Postgres run 36206051904: 150 tests passed in 32.82s, including the 1,000 completed-job fixture; restore CLI then exposed a missing SQLAlchemy model registration, now fixed.
- Latest local full backend suite before the final additional regressions: 145 passed, five environment-specific skips. Focused policy/MFA/cohort regressions: 12 passed.
- Latest local frontend lint/build: passed. Fresh SQLite migration/schema check: passed. Ruff correctness: passed.
- Cleanup CI run 36206441543 at `f721a586bee1754508aef700bfae5c1dbbc08c31`: all five jobs passed; Postgres 155 tests passed with two warnings. Rebrand verification is recorded separately; do not infer its results from this earlier SHA.

## 17. Remaining technical release gates

1. Complete the requested Render dashboard setup for an isolated staging API/worker using the already-created Postgres database. Configure secure runtime keys, exact CORS/CSP origins, approved mail/delivery destinations, migration startup and readiness checks.
2. Execute the deployed authenticated browser journeys, responsive/accessibility checks, staging migrations, worker/delivery verification, and an encrypted restore using the actual hosting/backup destination. CI proves code behavior, not this operational deployment.
3. Activate offsite encrypted backups, separate current deletion-ledger storage/freshness monitoring, retention and alerting. Verify ownership/control-history reconciliation after restoring older backups; do not reopen a restore with unresolved ownership state.
4. Review and remediate findings from those environment-specific checks before production promotion.

These remain technical work blocked on infrastructure access, not contractual/customer work. Do not label this release “human-only remaining” until these gates are completed.

## 18. Human / external requirements

Founder/counsel: approved policy text and retention periods, trademark/name clearance, incorporation and IP signatures. Vendors: contracts, granular permissions and securely configured credentials. Independent security firm: penetration testing and retest evidence. Pilot partners: actual customers, agreements and lawful representative outcome cohorts. Investors/founder: funding and signed commitments. No traction, permissions, legal approval or predictive validation has been invented.

## 19. Readiness

Implemented and inspectable research MVP; public frontend preview available. Institutional staging verification remains gated on secure backend access. No production promotion or enterprise readiness certification. Updated capability metadata and deployment/API documentation describe implemented versus activated behavior explicitly.

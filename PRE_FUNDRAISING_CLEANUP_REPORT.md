# PrivateLens pre-fundraising cleanup report

Date: 2026-09-20. Source: supplied ZIP snapshot `3060359ae6b7a55ff9384db8b36b7472c9634905` and seven-page pitch PDF.

## Executive Summary

The repository is materially improved: account/session hardening, restricted internal diagnostics, shared production quotas, account export/deletion, governed licensed integrations, durable CSV screening, customer API keys, correction handling, a scheduled monitoring foundation, policy-acceptance records, model reconstruction metadata, pilot metrics, pinned dependencies and CI controls are implemented. Frontend screens expose the main pilot workflows. Marketing and deck replacement copy distinguish implemented, pilot, architected and planned capabilities.

This is a **tested research MVP with pilot foundations**, not an enterprise-ready credit platform. No production deployment was performed. No Vercel/Render administrative credentials, vendor contracts, real customer outcomes or original Git history were provided. Attempts to inspect the live frontend/backend through web retrieval failed. No production secrets, paid services, pricing amounts, ownership, fundraising terms or production data were changed.

## Baseline

- Backend after initial dependency setup: **110 passed, 1 failed, 1 skipped**. The live SEC check failed because this environment initially lacked the SOCKS transport dependency; the remaining live checks later timed out. The original result is preserved.
- Provider gateway: **3 passed**.
- Frontend clean install and production build: passed.
- Original Alembic migrations: applied successfully locally. Later schema comparison found pre-existing timestamp nullability drift between historical migrations and ORM declarations.
- No frontend lint/type-check script or configured dependency/security audit gate existed. This is JavaScript, not a TypeScript project.
- npm audit found one high-severity transitive `nanoid` advisory. A compatible lockfile update resolved it; no forced major frontend upgrade was used.
- Original public health/configuration endpoints exposed internal operational settings; localStorage stored bearer credentials; auth trusted forwarded-IP headers directly; anonymous searches shared global history; pricing claimed unsupported teams and monitoring.

## Changes Completed

|Area|Implementation references|Result|
|---|---|---|
|Sessions|backend/core/security.py, routers/auth.py; frontend/src/api/client.js, context/AuthContext.jsx|Memory-only browser bearer sessions; optional HttpOnly cookie path; strict required JWT claims; bounded password inputs; 60-minute default|
|Revocation/CSRF|routers/auth.py, main.py|Token-version revocation retained; cookie writes require allowed Origin; logout expires cookie; reset consumption locks records|
|Internal exposure|backend/main.py|Production docs disabled, diagnostic routes require metrics secret, health reduced to status, generated request IDs and security headers|
|Shared quotas|backend/core/limiter.py, models/workflows.py|Atomic Postgres/SQLite fixed-window counters; production requires shared store; bounded memory fallback locally|
|Request limits|backend/core/body_limit.py; routers/workflows.py|1 MiB request cap; 256 KiB/100-row CSV limits; duplicate removal, retries and backlog limits|
|Account controls|routers/workflows.py; components/settings/DataControls.jsx|Password-confirmed deletion, export, owned-data cleanup, session/key revocation and de-identified control history|
|Privacy|routers/history.py, routers/score.py|Anonymous global history no longer returned or populated by scoring|
|Pilot workflows|models/workflows.py, routers/workflows.py, pages/Batch.jsx, Developer.jsx, ResearchControls.jsx|Saved batch progress, retry/export, API-key management, correction submissions and monitoring subscriptions|
|Model governance|services/reports.py, history.py, scorer.py|Scoring-input/config snapshots, code hash, config hash, reason codes; permission/config-sensitive cache identity|
|Vendor permissions|services/permissions.py, licensed_data.py|Unknown contractual rights fail closed; no inference of rights from credentials; Codat withheld pending consent isolation|
|Observability|core/observability.py, core/email.py|Structured correlation IDs, email/token redaction, Sentry scrubbing, console email bodies suppressed|
|Data lifecycle|scripts/retention.py, review_correction.py, run_monitoring.py|Runnable maintenance/review interfaces; external activation still required|
|Schema|alembic/versions/20260920_0005_pilot_workflows.py; models|Additive pilot tables and ownership FKs; SQLite FK enforcement; historical nullable timestamps explicitly reflected|
|Delivery|requirements.txt/.in, CI, Dependabot, frontend lint, render.yaml|Transitive Python pins, repeatable npm install, checks/audits; uncontrolled migration removed from build|

## Security Improvements

Default browser auth no longer leaves a seven-day token in localStorage. Existing JWT version invalidation remains, and malformed/missing required claims fail authentication rather than causing arbitrary server errors. Cookie support is intentionally opt-in: Secure/HttpOnly/SameSite=None in production, with Origin enforcement; cross-site cookie behavior is not presumed to work everywhere.

Production startup rejects debug/security-token responses and process-only quotas. Auth request limiting supplements existing account lockout. Application code no longer accepts arbitrary X-Forwarded-For identity. Deployment proxy trust still requires configuration. Diagnostic endpoints and interactive docs are restricted. Account-owned workflows reject cross-account requests and customer keys do not authenticate web-account routes.

Basic redaction and a limited secret-pattern scan are included; neither constitutes a complete secret discovery or independent penetration test. Bandit retains five reviewed low findings: a rejected development-secret sentinel, two hash-scheme strings, and two GLEIF malformed-row skip handlers. No medium/high Bandit findings were reported.

## Product Honesty Improvements

`product.json` is the canonical capability source, used by Pricing and `/api/capabilities`. Public research scoring is distinguished from predictive credit assessment. Landing-page licensed values are explicitly hypothetical. Pricing preserves dollar amounts while marking teams planned, API pilot, monitoring scheduler-dependent and licensed feeds contract-dependent. Alert/digest preferences no longer imply active delivery. The developer page documents the real versioned key API instead of presenting internal login endpoints as enterprise API access.

The deck's 14-signal/five-live-source narrative is superseded by exact replacement text and a discrepancy table. Indeed is unavailable. No customer, revenue, proprietary-data advantage or predictive accuracy was invented. PrivateLens/PrivateScore remain temporary names; primary display constants and a full rename checklist are included.

## Scoring / Model Improvements

The original scoring weights, quality multipliers, missing-data treatment, evidence ceiling, supporting influence cap and entity safeguards were preserved. Eleven weighted definitions exist: six public and five licensed, with hiring unavailable; GLEIF and Census are context-only. These are not eleven universally live sources. Model/version/configuration and input snapshots support reconstruction for newly retained reports. Existing older records cannot be retroactively reconstructed from absent inputs.

Reason codes explain used, context-only, unavailable/unusable and not-applicable rows. A new dated-cohort guard rejects temporal leakage and duplicated entities before future evaluation. Existing scoring/resolver/provider regression and synthetic validation tests remain. These tests do not prove real predictive performance. **NOT YET VALIDATED DUE TO MISSING OUTCOME DATA.**

## Data Governance

A machine-readable source registry and human table record purposes, endpoints, status, quality, freshness, attribution, known rates and unknown retention/redistribution rights. Source links and Wikipedia attribution/license notice are added to the UI. Automated User-Agent configuration replaces invented research contact addresses; the actual operator must supply a verified contact.

Licensed permissions include score/raw display/derived display/retention/monitoring/historical analysis/model development/API redistribution controls. The current unredacted report path requires all rights it actually uses and rejects narrower contracts. Codat stays excluded until account-specific consent and cache isolation are implemented. The customer API refuses licensed redistribution. No vendor terms were accepted or rights inferred.

## Infrastructure Improvements

Python backend and gateway have fully version-pinned dependency resolutions and editable input manifests. Frontend lockfile installation, ESLint, build and npm audit are enforced. CI uses verified immutable action pins, least privilege, concurrency cancellation, timeouts, migration checks, tests, Ruff, Bandit and pip-audit. Dependabot covers Python/npm/actions. Secret-pattern checks do not print matched values.

Local backup files receive restrictive permissions; dump structure/checksum validation is required; direct plaintext S3 upload is rejected; restore uses error-stop/transaction behavior. The existing encrypted artifact workflow has pinned actions. It remains short-term backup, not verified disaster recovery. Scheduling retention/monitoring and external durable backup need deployment access.

## Product Features Added

- **Bulk screening pilot:** CSV name-column mapping, optional country/registration/postcode fields, size/row validation, deduplication, stored per-company status, lease recovery, three-attempt cap, partial failures, account isolation, formula-safe CSV results, history and frontend controls. Browser drives sequential processing; progress survives process/page interruption.
- **Customer API pilot:** high-entropy hashed keys shown once, account scope, score:read endpoint, atomic 1,000-call lifetime quota, rate limiting, counters, revoke/rotate UI and audit events. No organization sharing or webhooks promised.
- **Monitoring foundation:** persistent subscriptions, weekly reevaluation interface, lease/fencing, material score/status/flag changes and in-app event history. Timestamp-only changes do not create alerts. No scheduler activated or email delivery claimed.
- **Correction pilot:** owned report/hash reference, requester/time/reason/status, append-only operator review history and corrected-snapshot reference. No automatic acceptance.
- **Account/policy/pilot controls:** export/delete UI, versioned acceptance endpoint (disabled for unpublished drafts), paired analyst time/usefulness/escalation measurements and non-fabricated ROI aggregation.

## Documentation Added

`dataroom-prep/` contains capability matrix, methodology, security architecture, provenance/source registry, validation/pilot protocol, deck fact-check and exact page replacement text, rename checklist, document dispositions, dependency notices, CycloneDX SBOM and available third-party license texts. Six original policy drafts are marked for counsel review. README and the current rollout runbook describe actual setup and limitations. Historical validation documents and the old README are preserved separately.

The original pitch PDF was not overwritten; exact replacement copy is provided rather than falsely presenting a newly verified strategic/financial deck.

## Tests

Final authoritative outputs are under `verification/`:

|Check|Result|
|---|---|
|Backend complete suite|126 passed, 2 skipped; 2 dependency deprecation warnings|
|Live-source skips|GLEIF and SEC timed out; no live availability claim|
|Provider gateway|3 passed|
|Fresh npm installation|Passed|
|Frontend ESLint|Passed|
|Frontend production build|Passed|
|Backend/gateway pip-audit|0 known vulnerabilities reported|
|npm audit|0 known vulnerabilities reported|
|Ruff fatal/undefined-name checks|Passed|
|Bandit|0 medium/high; 5 low findings described above|
|Secret-pattern scan|No configured pattern matches; not exhaustive|
|Local migrations|Upgrade succeeded; final Alembic schema comparison clean|
|Shell parsing for backup/restore|Passed; no real database restore performed|
|Browser visual/end-to-end checks|Blocked: Chromium unavailable; download failed with timeouts/502|
|Production/Postgres/load testing|Not performed; no production access provided|

## Known Remaining Technical Risks

These are engineering limitations, not tasks misclassified as human-only:

1. No verified browser visual/accessibility regression run or multi-browser cross-site-cookie test. Default memory sessions require sign-in after hard reload. Optional cookie mode requires deployment verification.
2. Bulk screening is bounded pilot functionality, not an autonomous high-volume worker fleet. Database-backed counters are shared, but per-provider global request budgets, fair queue scheduling, wider load tests and durable notification delivery remain scaling work.
3. Organizations/membership/RBAC/SSO are not implemented; the unsupported team claim was removed as authorized. Existing isolation is per account.
4. Codat consent isolation and narrower-license redacted report paths remain intentionally disabled. Retention scripts must actually run before any licensed data is activated; all vendor obligations require contract-specific testing.
5. Monitoring has in-app events, not email/webhook retry/dead-letter delivery. Worker failure alerts and exactly-once report/history persistence need strengthening for enterprise commitments.
6. Pilot timing measurements are self-reported; policy acceptance is supported through an endpoint but approved-policy publication and a full reacceptance UI are not active.
7. No real Postgres concurrency test, restore drill, production proxy/CORS validation or deployed smoke test was performed. Local migration success is not proof of safe production migration.
8. Synthetic resolver/scoring tests remain limited benchmarks. No new representative independent labeled resolver/outcome dataset was available. Long-term replay also depends on preserving matching code and lawful retained snapshots.
9. Source licensing review is incomplete; public availability does not prove redistribution permission. Basic secret scanning/redaction is not exhaustive, and SBOM licenses are reported metadata.
10. Production control-log retention, deletion replay after backup restore and absolute lifetime data-retention enforcement need deployment/counsel policy alignment. Historical nullable timestamps remain unknown rather than invented.

## HUMAN ACTION REQUIRED

|Item|Why needed|Who handles it|Exact action|Proof of completion|
|---|---|---|---|---|
|Brand clearance|Names remain temporary|Owner and trademark counsel|Clear PrivateLens/PrivateScore or approve a final replacement|Written clearance/name decision|
|Commercial data rights|Credentials do not grant scoring/display/retention/redistribution rights|Owner, vendor and counsel|Negotiate Creditsafe/Middesk/Codat schedules and document each permitted use/consent duty|Executed agreements plus approved permission matrix|
|Policy/legal approval|Drafts are not legal compliance|Counsel and accountable operator|Confirm entity, contacts, eligibility, retention/holds, regional rights and final policies|Approved versioned policies and publication decision|
|IP/company records|Repository cannot establish ownership|Founders, contributors and counsel|Complete incorporation, cap table, founder/contributor IP assignments|Executed corporate/IP documents|
|Deployment access and verified contacts|No Vercel/Render/Postgres credentials supplied|Infrastructure owner|Provide authorized access, verified sender/security contact and approved scheduling/backup resources|Access granted; verified contacts and operational ownership recorded|
|Independent security assessment|Self-tests do not replace independent review|Qualified security reviewer|Test staged deployment, auth, tenant isolation, data paths and remediation|Written report and closure evidence|
|Real customer pilots|No customer behavior or ROI data supplied|Founder and consenting pilot analysts|Agree pilot scope and run paired measured research tasks|Pilot agreements and raw measurement records|
|Real outcome data|Predictive validation needs dated labels and lawful snapshots|Research owner/data partner|Obtain lawful representative outcome cohort and independent evaluation|Data rights, dated cohort and signed-off evaluation|
|Fundraising/customer decisions|Strategy/outreach/contracts require owner control|Founder|Approve positioning and commercial terms; conduct outreach separately|Approved materials and actual commercial evidence|

No purchases, contracts, investor messages or customer outreach were performed.

## Final Readiness Assessment

|Stage|Assessment|
|---|---|
|Technical MVP|Materially improved; local test/build coverage passes with external-source limitations|
|Public beta|Conditional on deployed browser/auth/email/proxy checks and published operational contacts/policies|
|Institutional pilot|Suitable for technical review and a supervised public-data evaluation after staging checks; not ready for reliance as a credit rating|
|Enterprise production|Not ready: organization controls, operational durability, vendor rights, independent security and production testing remain|
|Investor technical diligence|Substantially clearer evidence packet and honest limitations; corporate, commercial, production and outcome evidence still required|

Local commits preserve the imported source and cleanup stages. The supplied archive did not contain original Git history; no claim of code originality, IP clearance or historical ownership is made.

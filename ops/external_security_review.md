> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# External Security Review Scope

Perspicil should not be described as bank-grade until an independent reviewer validates the production deployment.

## Scope

- Backend API authentication and authorization
- JWT/session invalidation behavior
- Password reset and email verification flows
- CORS, host validation, headers, and rate limiting
- Tenant isolation for history, watchlist, settings, and reports
- Managed Postgres access, migration, backup, and restore process
- Licensed data gateway authentication and data handling
- Frontend session handling and protected routes
- Dependency and supply-chain review

## Minimum Tests Requested

- OWASP ASVS Level 2 application review
- Auth brute force and lockout testing
- API authorization object-level access testing
- Secrets management review
- Dependency vulnerability scan
- Backup restore tabletop
- Incident response tabletop

## Deliverables

- Executive summary
- Finding list with severity, reproduction, and remediation
- Retest letter after fixes
- Attestation letter suitable for investors or design partners

## Pre-Review Evidence

- GitHub Actions CI run
- Production environment variable inventory without secret values
- Render deployment settings
- Vercel deployment settings
- Backup and restore runbook
- Data source/vendor list and licenses

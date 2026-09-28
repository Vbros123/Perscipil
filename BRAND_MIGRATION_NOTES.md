# Perspicil brand migration notes

2026-09-28. Public product name: **Perspicil**. Public score label: **Perspicil Score**.
`product.json` is the source of truth consumed by React, Vite metadata and the API.
The legal entity is unset, not inferred from the product name. Counsel review and
trademark clearance remain required.

## Compatibility retained

- API routes, `private_score` fields, evidence/model-validation schema strings and
  `X-PrivateLens-*` webhook headers remain stable for existing integrations.
- The `privatelens_session` cookie, JWT issuer/audience, session-expiry event and
  removal of the obsolete local-storage token key remain unchanged. No forced
  session reset, token migration, database migration or global SQL replacement.
- Logger/metric namespaces, Sentry release prefix, database filenames, backup
  prefixes, npm package identity and test fixture IDs remain technical identifiers.
- Repository, Vercel project/URLs, Render production service and staging database
  keep their existing identifiers. Renaming infrastructure is not needed to ship
  the public rebrand. The old URL remains visible in the browser address bar until
  an owned and verified domain is configured.
- Existing authenticator enrollments retain their stored issuer label. New TOTP
  enrollment uses Perspicil. Re-enrollment is optional, not forced for cosmetics.
- Immutable evidence, model snapshots, audit history, historical cleanup reports,
  the dated SBOM and verification logs retain their original names. No stored
  customer/provider/historical data was modified. Live database inspection awaits
  staging access; there is no claim that historic rows were rewritten.

## Environment values requiring owner configuration

Set `APP_NAME=Perspicil API` and `SMTP_FROM_NAME=Perspicil Security` when existing
hosting variables override code defaults. Configure actual verified sender and
support addresses; no new email address/domain has been invented. `APP_PUBLIC_URL`,
`FRONTEND_URL`, `ALLOWED_ORIGINS`, `ALLOWED_HOSTS` and `VITE_API_URL` must use the exact
existing or newly verified hosts. Keep all auth/encryption keys stable within each
environment. See `ops/STAGING_RENDER_SETUP.md` for isolated staging setup.

## Domain/account actions

A final domain, DNS ownership, sender verification and trademark/legal entity
information require the owner. Existing project/service/account display names may
remain internal. No domain was purchased, no production resource was renamed and
no redirect to an unowned domain was introduced.

## Residue audit

`docs/BRAND_RESIDUE_AUDIT.md` inventories every matched tracked/current text-file
line, including hidden workflow/config files, with its classification and reason.
Audit/report documents discussing the old name are explicitly classified historical
migration documentation. Generated builds, dependencies and Git object internals
are excluded from source inventory; the built frontend is checked separately.
Original PDF copies are historical; the new deck is checked for old-brand text.
No unexplained user-facing source residue is accepted.

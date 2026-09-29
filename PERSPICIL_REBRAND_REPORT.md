# Perspicil rebrand report

Updated 2026-09-28. Rebrand code is pushed and preview-verified; CI is green for the code revision.
Deployment verification below remains separate from code completion. Production release remains gated.

## Brand Migration

`product.json` defines product, score, short/support/sender names, title and factual
description, with legal entity explicitly unset. React brand components, Vite HTML
metadata/manifest, API title/health, email subjects/bodies/sender defaults and new
MFA enrollment consume shared values. Updated homepage, navigation, login/signup,
verification/reset, onboarding, settings, score/report/compare labels, account
export filenames, pricing/footer, provider descriptions and active technical docs.
Existing organization/monitoring/bulk/API-key/correction screens use the shared
application shell; their data models and behavior were not rebuilt.

## Remaining Legacy Identifiers

See `BRAND_MIGRATION_NOTES.md` and the line-level residue audit. Auth cookies/JWT,
API schema/field/header contracts, telemetry, resource URLs and historical records
are preserved. No database schema or data migration is necessary for these labels.
Live database-visible historical content has not been inspected or modified.

## Logo

Original geometric split-aperture P with a small focal square: precision and
revealing evidence. No reference image was attached; the supplied written direction
was used. `frontend/public/brand/` contains horizontal light/dark/mono SVGs,
symbol/light/dark/mono SVGs, 16/32/180/192/512 PNGs, and SVG/PNG social art.
The wordmark uses the existing Inter/Arial/sans-serif font stack. The common
`BrandMark` supplies navigation/auth screens. HTML favicons, generated manifest,
social metadata and transactional email header use these assets.

## Pitch Deck

The final separate copy is `output/pdf/Perspicil_Corrected_Deck.pdf`, also committed
at `dataroom-prep/Perspicil_Corrected_Deck.pdf`. All seven pages were rendered and
visually checked. Cover logo, title, footers, score title, metadata and homepage
screenshot use the new brand. Deprecated raster assets were removed. Text comparison
confirms every non-brand word is preserved, including market assumptions and
customer/funding/validation/backend-activation caveats. No old-brand PDF text remains.

## Website / Product

Browser-inspected the exact `b134100809039dc78bcc2d009734050ee3e72136` preview:
homepage, login/MFA input, signup and forgot-password. Branding/logo loads, metadata
uses Perspicil and preview-local social art, signup inputs have accessible labels,
and desktop has no horizontal overflow. Fixed an existing body font-inheritance
bug and bounded session discovery to 15 seconds so an unreachable API cannot leave
public auth pages loading indefinitely. Login renders after that bound. No app-origin
console errors observed; browser-extension metadata errors were excluded.
Authenticated staging journeys, mobile/cross-browser tests and full accessibility
automation remain unverified. Public-page inspection is not an authenticated E2E pass.

## Email

Password-reset and email-verification subjects/bodies, sender display default and
HTML logo header updated. Monitoring subjects updated. Existing mail addresses
remain operator-configured. Delivery to a real inbox is not yet verified.

## API / Docs

FastAPI title is Perspicil API; health/capability output and public score descriptions
use the new names. Gateway display title and active docs updated; stable protocol
identifiers retained. README reconciled to the implemented workspace/durable-job
features. The dated SBOM and historical reports remain unchanged evidence.

## Legal Drafts

Terms and other draft material use the new brand where a brand appears. Existing
DRAFT / COUNSEL REVIEW REQUIRED status remains. No incorporated entity or legal
approval is asserted.

## Deployment

Before this rebrand, cleanup branch remote head was
`f721a586bee1754508aef700bfae5c1dbbc08c31` (PR #10). Latest confirmed production
frontend: `3ed1df1d58e821c246a91b04982f5511ce22d250`; Render production API remained
`3060359ae6b7a55ff9384db8b36b7472c9634905`. They have not been promoted by this rebrand.
Isolated Render database `dpg-das6rme0tbcc73e2v1hg-a` is available, expires 2026-10-27.
Rebrand code commit: `b134100809039dc78bcc2d009734050ee3e72136`.
Verified Vercel preview: `dpl_HS5gq8Jh7ZewbUKkuqzoS3iHevdY`, READY,
https://privatelens-bqk7xd0v3-bruh-gangs-projects.vercel.app .
Branch alias: https://privatelens-git-final-pre-fundraisin-928d23-bruh-gangs-projects.vercel.app .
The preview still points to the legacy API, not an isolated full-stack staging deployment.
The staging API and worker are not yet deployed. User requested dashboard steps:
`ops/STAGING_RENDER_SETUP.md` provides the complete procedure.

## Tests

Local backend: 149 passed, six environment-specific skips, two deprecation warnings.
Gateway: three passed. Ruff correctness passed; Bandit high-severity gate passed
(six low-severity findings remain, not represented as zero findings). Frontend
lint/build passed. Fresh SQLite migration and schema diff passed.
Both local dependency audits passed (npm: zero vulnerabilities; pip: no known
vulnerabilities). Full CI run **36477859083** at the exact code SHA above passed
all five jobs: backend, frontend, provider-gateway, postgres and secret-history.
Postgres: **155 passed**, two deprecation warnings. Encrypted restore: **31 tables /
3,359 rows** matched, readiness passed, post-backup deletion replay and idempotence
passed. Earlier rebrand run 36477602640 also passed all five jobs. Evidence:
`verification/rebrand/results.json`. Final documentation/deck commits do not change
runtime code; their separate CI status is available on PR #10.

## Search Audit

Case-insensitive inventory covers the old product and score spellings with spaces
or no spaces. See `docs/BRAND_RESIDUE_AUDIT.md` for each file/line and classification.
Historical output PDFs and source deck are retained separately, not presented as
current branding.

## HUMAN ACTION REQUIRED

- Enter isolated staging secrets and verified sender settings in Render as requested;
  return only the staging API URL and deployed SHA. No secrets in chat.
- Choose/authorize worker compute and private backup destination/key custody.
- Supply an owned domain/verified sender if a final brand domain is desired.
- Founder/counsel: legal entity, policy approval, trademark/name clearance.

Authenticated browser journeys, live worker/delivery verification and real-hosting
restore are still **technical release gates**, not falsely labeled external-only
work. They resume when the chosen infrastructure is configured. Vendor contracts,
real customers/outcome cohorts and independent security review remain external.

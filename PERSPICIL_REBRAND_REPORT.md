# Perspicil rebrand report

Updated 2026-09-28. Implementation complete locally; deployment verification below
is deliberately separate from code completion. Production release remains gated.

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

The corrected seven-slide deck is being rebranded as a separate
`output/pdf/Perspicil_Corrected_Deck.pdf`. Financial/customer/validation claims,
market caveats and backend-activation limitations must remain unchanged. Final
visual verification and output status will be recorded after the preview capture.

## Website / Product

Frontend lint/build passed. Public preview visual inspection and responsive checks
will be recorded against the exact rebrand commit. Authenticated full-stack staging
journeys require the isolated Render API/worker and real email configuration.
Do not infer browser success from backend tests.

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
The staging API and worker are not yet deployed. User requested dashboard steps:
`ops/STAGING_RENDER_SETUP.md` provides the complete procedure.

## Tests

Local backend: 149 passed, six environment-specific skips, two deprecation warnings.
Gateway: three passed. Ruff correctness passed; Bandit high-severity gate passed
(six low-severity findings remain, not represented as zero findings). Frontend
lint/build passed. Fresh SQLite migration and schema diff passed.
Current dependency audits, remote CI/Postgres restore and preview verification are
pending at this checkpoint; results will be recorded after push.

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

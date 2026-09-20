> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# Licensed Provider Plan

## Selected stack

### Creditsafe Connect

Use for commercial credit and B2B payment behavior. Creditsafe documents company search, a stable `connectId`, country-specific credit reports, monitoring, credit score, credit limit, and negative information. Its own integration guidance recommends a registration number where available, otherwise company name plus postcode. The reference gateway enforces that rule and does not promote name-only matches to score evidence.

- Official API: https://doc.creditsafe.com/connect-apis-catalog/product-catalog/creditrisk
- Authentication: username/password exchanged for a one-hour bearer token
- Sandbox base URL: `https://connect.sandbox.creditsafe.com/v1`
- Production base URL: `https://connect.creditsafe.com/v1`
- Procurement: request a Connect API quote and written rights for derived PrivateLens outputs, display, retention, and monitoring

### Middesk

Use for legal entity verification, registration standing, UCC/tax liens, bankruptcies, and litigation. Middesk verification is an asynchronous order flow and should be completed during company onboarding or diligence intake. Store only the Middesk business ID and normalized observations in the gateway; consume `business.updated` webhooks there.

- Official docs: https://docs.middesk.com/home
- Business object: https://docs.middesk.com/reference/business
- Legal records: https://docs.middesk.com/assess-risk/legal
- Procurement: contact sales, obtain sandbox access, confirm the jurisdictions and legal products in the contract, and confirm derived-output rights

### Codat

Use only for company-authorized accounting and banking aggregates. Codat connections require the subject company to authorize an accounting, banking, or commerce source. It is not a name-search data source.

- Official docs: https://docs.codat.io/
- Procurement: contact Codat, configure the hosted authorization flow, obtain explicit business consent, and retain the consent artifact and Codat company/connection IDs
- Data minimization: send ratios and aggregates to PrivateLens; do not store raw transactions in the scoring API

## Activation order

1. Sign Creditsafe contract and run its sandbox against a labeled entity-match set.
2. Deploy `provider_gateway/` with Creditsafe credentials and keep PrivateLens in `DATA_MODE=public`.
3. Verify gateway authentication, exact entity matches, provider timestamps, and rate-limit behavior in staging.
4. Add Middesk business verification plus webhook persistence to the gateway after the contract and jurisdiction review.
5. Add the Codat consent flow and connection-ID mapping; never query it for companies that did not authorize access.
6. Set the backend to `DATA_MODE=licensed` and `MODEL_RELEASE_STAGE=shadow`.
7. Build the time-indexed outcome dataset and run `ops/model_validation_runbook.md`.
8. Obtain independent model-risk, legal/permitted-use, and security approvals.
9. Set `MODEL_RELEASE_STAGE=validated` only with `MODEL_VALIDATION_REFERENCE` and `MODEL_APPROVED_BY`.

## Contract checklist

- Permitted product and customer use cases
- Right to create, retain, and display derived outputs
- Restrictions on adverse action, lending, insurance, employment, or consumer use
- Source attribution requirements
- Data retention and deletion periods
- Monitoring and webhook rights
- Sandbox and production quotas
- Service levels and incident notice
- Subprocessor and international transfer terms
- Audit, termination, and post-termination deletion obligations

No provider is enabled merely because its name appears in the catalog. Production stays fail-closed until credentials and a valid `license_reference` are configured.

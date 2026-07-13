# PrivateLens Legal And Compliance Controls

PrivateLens is a research product, not a credit decisioning, lending, investment, legal, or underwriting authority.

## Required Product Controls

- Every report must state that PrivateLens does not provide credit, investment, legal, or lending advice.
- Simulated/modelled data must remain visibly labelled.
- Licensed-source responses must include provider, license reference, and source metadata when available.
- Customers must not use PrivateLens as the sole basis for adverse action.
- User access requires authentication.
- Security-sensitive actions are written to `auth_audit_events`.

## Required Company Controls Before Selling To Financial Institutions

- Privacy policy reviewed by counsel.
- Terms of service reviewed by counsel.
- Data processing agreement template.
- Vendor/license register for every paid data provider.
- Incident response policy and owner.
- Backup and restore policy.
- Access review cadence for production systems.
- External security review completed and remediated.

## Data Handling

- Store only the minimum account profile data needed for the product.
- Do not store raw bank credentials.
- Do not store payment account numbers or direct personal payment identifiers.
- Do not ingest regulated consumer credit report data unless counsel approves the product flow.

## Review Cadence

- Security review: before launch and after material auth/data changes.
- Legal review: before paid customer launch.
- Data vendor review: before enabling any licensed connector.
- Backup restore drill: monthly.

# PrivateLens Legal And Compliance Controls

PrivateLens is a research product, not a credit decisioning, lending, investment, legal, or underwriting authority.

## Required Product Controls

- Every report must state that PrivateLens does not provide credit, investment, legal, or lending advice.
- Unavailable and public context inputs must remain visibly labelled and excluded from ratings.
- Licensed-source responses must include provider, license reference, source metadata, observation time, entity-match evidence, and permitted use.
- Numeric ratings stay disabled until the evidence, provider-diversity, entity, and documented model-approval gates pass.
- Customers must not use PrivateLens as the sole basis for adverse action.
- User access requires authentication.
- Security-sensitive actions are written to `auth_audit_events`.

## Required Company Controls Before Selling To Financial Institutions

- Privacy policy reviewed by counsel.
- Terms of service reviewed by counsel.
- Data processing agreement template.
- Vendor/license register for every paid data provider.
- Model inventory, validation packet, approver, release owner, rollback owner, and annual review date.
- Documented dispute and correction process for company data.
- Incident response policy and owner.
- Backup and restore policy.
- Access review cadence for production systems.
- External security review completed and remediated.

## Data Handling

- Store only the minimum account profile data needed for the product.
- Do not store raw bank credentials.
- Do not store raw bank transactions in the scoring API; retain only consented aggregates needed for the model.
- Do not store payment account numbers or direct personal payment identifiers.
- Do not ingest regulated consumer credit report data unless counsel approves the product flow.

## Review Cadence

- Security review: before launch and after material auth/data changes.
- Legal review: before paid customer launch.
- Data vendor review: before enabling any licensed connector.
- Model performance and drift review: monthly after a validated release, with automatic shadow fallback on a breached threshold.
- Backup restore drill: monthly.

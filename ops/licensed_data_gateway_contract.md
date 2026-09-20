> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# Licensed Evidence Gateway Contract v2

PrivateLens calls an isolated gateway so vendor credentials, licensed payloads, rate limits, and contract restrictions do not live in the public scoring API. Version 2 accepts raw observations only. A provider or gateway cannot inject a PrivateLens score.

## Request

```json
{
  "schema": "privatelens.evidence.request.v2",
  "request_id": "f7746b7a-3b35-45be-a742-2658d8cd3178",
  "entity": {
    "legal_name": "Acme Manufacturing LLC",
    "country_code": "US",
    "registration_number": "A-123",
    "postal_code": "10001",
    "provider_ids": {}
  },
  "providers": ["creditsafe", "middesk", "codat"],
  "required_permitted_use": "company_intelligence"
}
```

## Response

```json
{
  "schema": "privatelens.evidence.v2",
  "request_id": "f7746b7a-3b35-45be-a742-2658d8cd3178",
  "generated_at": "2026-07-31T16:00:00Z",
  "bundles": [
    {
      "provider": {
        "key": "creditsafe",
        "name": "Creditsafe Connect",
        "license_reference": "contract-2026-001",
        "permitted_use": ["company_intelligence"]
      },
      "entity_match": {
        "provider_entity_id": "US-123",
        "legal_name": "Acme Manufacturing LLC",
        "country_code": "US",
        "registration_number": "A-123",
        "postal_code": "10001",
        "match_status": "exact",
        "confidence": 1.0,
        "matched_fields": ["legal_name", "registration_number"]
      },
      "observations": [
        {
          "evidence_id": "creditsafe:US-123:credit:2026-07-30",
          "metric": "creditsafe.credit_score",
          "value": 82,
          "scale_min": 0,
          "scale_max": 100,
          "higher_is_better": true,
          "observed_at": "2026-07-30T00:00:00Z",
          "fetched_at": "2026-07-31T16:00:00Z",
          "source_ref": "urn:creditsafe:company:US-123:credit-report",
          "quality_flags": []
        }
      ]
    }
  ]
}
```

## Accepted metrics

- Creditsafe: `creditsafe.credit_score`, `creditsafe.payment_index`, `creditsafe.days_beyond_terms`
- Middesk: `middesk.registration_status`, `middesk.active_bankruptcy_count`, `middesk.recent_lien_count_12m`, `middesk.active_tax_lien_count`, `middesk.defendant_litigation_count_24m`
- Codat: `codat.current_ratio`, `codat.debt_service_coverage_ratio`, `codat.operating_cash_flow_margin`, `codat.months_cash_on_hand`, `codat.revenue_growth_yoy`

Unknown fields are rejected. The backend owns all metric-to-signal transformations and records `transform_version`, evidence IDs, observation dates, entity confidence, and an input snapshot hash.

## Entity gate

Evidence is accepted only when either:

1. The registration number is an exact match, or
2. Match confidence is at least 0.95 and legal name plus registration number, postcode, or address are matched.

Name-only, ambiguous, and not-found matches never affect a rating.
The scoring API independently checks the returned country and every claimed matched field against the original request. A gateway response for a different registration number, legal name, postcode/address, or explicit provider ID is rejected even if the gateway labels it exact.

## Security and licensing

- Require bearer authentication and HTTPS.
- Keep vendor credentials in the gateway only.
- Confirm the signed contract permits `company_intelligence`, derived outputs, customer display, retention, monitoring, and the target customer/use case.
- Return a non-secret license reference on every bundle.
- Do not return raw bank transactions, bank credentials, personal identifiers, or restricted report documents.
- Preserve provider request IDs in restricted logs and never log credentials or full licensed payloads.
- Do not replace a missing provider observation date with the fetch time.

The reference Creditsafe implementation is in `provider_gateway/`. Middesk requires a completed business verification ID; Codat requires a company-consented connection ID. Those IDs belong in `entity.provider_ids` after their respective onboarding flows complete.

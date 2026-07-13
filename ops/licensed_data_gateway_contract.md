# Licensed Data Gateway Contract

PrivateLens does not call paid vendor APIs directly from the scoring service. It calls a normalization gateway that owns vendor credentials, vendor-specific schemas, and licensing restrictions.

## Request

```json
{
  "company_name": "Acme Manufacturing",
  "provider_key": "ucc",
  "signal": "UCC Filings & Lien Activity",
  "expected_schema": "privatelens.signal.v1"
}
```

## Response

```json
{
  "schema": "privatelens.signal.v1",
  "provider_name": "Example Licensed Provider",
  "license_reference": "contract-2026-001",
  "raw_score": 76,
  "display": "2 active filings, no recent lien acceleration",
  "insight": "UCC activity is present but not excessive for this sector.",
  "source_url": "https://provider.example/report/123"
}
```

## Provider Keys

- `ucc`
- `court_records`
- `open_banking`
- `reviews`
- `web_traffic`
- `social`
- `supply_chain`
- `b2b_payments`
- `employee_sentiment`

## Production Requirements

- Gateway must require bearer authentication.
- Gateway must enforce vendor-specific rate limits and license restrictions.
- Gateway must return normalized scores from 0 to 100.
- Gateway must not return raw credentials, tokens, or restricted personal identifiers.
- Gateway must log provider, request id, and license reference for audit.

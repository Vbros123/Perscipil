# Capability status

Generated from `product.json`, 2026-09-20. LIVE describes repository implementation, not verified deployment.

| Capability | Status | Limitation |
|---|---|---|
|Public evidence collection|LIVE|Implemented; availability varies by source and entity. Deployment not verified.|
|Entity resolution|LIVE|Ambiguous and non-company entities are gated; not an authoritative registry for all companies.|
|Evidence-weighted research score|LIVE|Not a credit rating or default probability; empirical outcomes not validated.|
|Saved companies and history|LIVE|Individual accounts only.|
|CSV bulk screening|PILOT|100 rows, durable resumable progress; browser drives sequential processing.|
|Weekly reevaluation|ARCHITECTED|Durable scheduler interface and in-app events; external scheduler not activated.|
|Customer API|PILOT|Account-scoped public-evidence keys, score:read scope, 1000-call lifetime quota.|
|Team workspaces|PLANNED|No organizations, memberships, or multi-user roles.|
|Licensed commercial evidence|ARCHITECTED|Contracts, granular permissions, retention operations and vendor access required.|
|Consented accounting evidence|PLANNED|Codat excluded until per-account consent isolation is implemented.|
|Predictive default probability|PLANNED|No labeled outcome validation; not available.|
|Company correction review|PILOT|Authenticated report disputes, operator review with append-only review history.|

# Evidence publication correction — 2026-10-10

Sparse public evidence could produce an adverse rating because the evidence
ceiling lowered a model output before rating-band assignment. Missing evidence
must not be interpreted as an adverse finding about a company.

Changes:
- Public reports require at least 40% quality-weighted coverage, 30% evidence
  confidence, a high-quality live core signal, and entity resolution of 75/100.
  These are conservative publication rules, not statistically calibrated accuracy.
- Reports failing those rules retain observations but publish a null score and
  “Insufficient public evidence”. Internal model outputs remain audit diagnostics.
- Eligible public-only scores use a neutral research label. Mixed licensed reports
  must also satisfy licensed coverage, identity, diversity, and model approval.
- Wikipedia recognizes professional services networks. Search failures no longer
  prevent exact-title lookup; REST failures can fall back to the Action API.
- Unverified similarly named government recipients are unavailable, not inapplicable.
  They are never merged into the queried entity merely to increase coverage.
- Reports and signal cards distinguish disconnected sources, lookup errors, and
  absent verified matches. Confidence is labelled as an evidence indicator.
- Null legacy scores no longer become numeric zero in frontend summaries.
- Score cache namespace increments so old computed reports are not reused.

Provider credentials, contracts, consent flows, and paid services are not enabled
by this change. Existing saved snapshots remain historical; regenerate a report
for the corrected calculation. Provider outages can still limit public coverage.

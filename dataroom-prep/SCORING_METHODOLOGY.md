# Scoring methodology — current research model

Perspicil Score is a deterministic, evidence-weighted research score on a 0–1000
scale. Use it to prioritize analyst review and inspect source evidence. It is
not a credit rating, probability of default, underwriting approval, investment
recommendation, or validated forecast. NOT YET VALIDATED DUE TO MISSING OUTCOME DATA.

## Signal definitions

Eleven weighted definitions: five licensed and six public. The hiring definition
is unavailable, not a functioning collector. GLEIF identity and Census industry
statistics are additional context-only inputs. Counts describe definitions, not
signals available for any particular company.

| Signal | Track | Base weight | Role | Quality hint | Maximum age (days) |
|---|---|---:|---|---|---:|
|Commercial Credit Risk|licensed|0.30|core|high|120|
|B2B Payment Behavior|licensed|0.20|core|high|120|
|Cash Flow & Liquidity|licensed|0.20|core|high|45|
|Business Identity & Standing|licensed|0.15|core|high|180|
|Liens, Bankruptcy & Litigation|licensed|0.15|core|high|120|
|SEC Financial Evidence|public|0.18|core|high|400|
|Brand Legitimacy & Web Presence|public|0.08|supporting|low|365|
|Company Stability|public|0.08|supporting|medium|365|
|Job Posting Velocity|public|0.08|supporting|low|14|
|News & Media Sentiment|public|0.06|supporting|low|14|
|Government Contract Awards|public|0.10|core|high|365|

Licensed base weights sum to 1.00; public base weights sum to 0.58. They are
track-specific base weights, not eleven percentages that sum to 100%. Actual
usable evidence and quality determine the denominator. Public-only coverage is
coverage of applicable public inputs, not full financial coverage.

## Calculation and safeguards

`backend/services/scorer.py` is authoritative. A row needs a known nonzero
weight, usable finite raw value, scoring eligibility and usable availability;
industry context is excluded. Missing evidence does not receive 0 or 50.
Quality multipliers reduce effective weights. Supporting evidence is capped at
30% of effective weight when core evidence exists. Supporting-only evidence is
separately gated; the cap does not create core evidence where none exists.

Observed strength is sum(raw score × effective weight) / sum(effective weight).
Coverage is effective weight divided by applicable weight. The evidence ceiling
is 1000 × (0.32 + 0.68 × coverage^1.05) × quality mix. Public-only ceiling is 820.
Incomplete high-quality coverage additionally caps the ceiling at 950. Published
output also depends on track-specific eligibility and resolution gates.

No economic weights or predictive calibration were invented in this cleanup.
Weak news, encyclopedia presence, and age proxies retain existing supporting
roles. Changing their weights or removal is a model-governance decision requiring
comparison on a labeled benchmark, not evidence of improved accuracy by itself.

Freshness is source-specific. Observation and retrieval dates mean different
things; collector freshness and the confidence factor must not be presented as
proof of recent financial performance. Exact quality constants, signal specs,
ceiling parameters and scorer source hash are embedded in report reproducibility
metadata. Public model identifiers remain public-v2 and licensed logic v4.0;
scoringConfigHash distinguishes configuration/source revisions.

## Explanation and reconstruction

Breakdown rows contain contributions, source provenance, eligibility and reason
codes (USED_EVIDENCE, NOT_APPLICABLE, MISSING_OR_UNUSABLE_EVIDENCE, CONTEXT_ONLY).
Metadata includes score, confidence, coverage, model version, evidence snapshot
hash, missing sources and warnings. Persisted reports now contain scoring inputs,
configuration, resolution confidence and release stage. Re-run the matching
archived code with these inputs; do not substitute current source data.

Snapshot retention is finite. Reconstruction is limited to retained reports and
code versions; this is not an indefinite historical database. Existing pre-cleanup
reports do not retroactively acquire missing reconstruction inputs.

## Validation plan

Preserve existing synthetic and regression tests; they prove invariants, not
commercial predictive performance. Before prediction claims: obtain lawful dated
outcomes, freeze the model, split by time and entity, compare simple baselines,
measure calibration/AUC/PR lift and false positives/negatives, report subgroup and
missingness performance, confidence intervals and stability. Do not convert
1000-minus-score into a distress probability. Existing `model_validation.py`
expects separately supplied probabilities and labels.

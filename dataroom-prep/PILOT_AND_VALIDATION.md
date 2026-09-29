# Pilot and validation packet

Outcome validation: NOT YET VALIDATED DUE TO MISSING OUTCOME DATA.
Existing model validation code and historical synthetic reports are retained.
No dataset, model accuracy, customer count, or investment performance is invented.

Pilot protocol: freeze source/code/model version; recruit a consented analyst;
pre-register a representative company list; record manual research time and
Perspicil-assisted review time using the same task definition. Record coverage,
entity correctness, unresolved cases, escalations, usefulness (1–5), processing
latency, and any later observed outcomes. Avoid selecting only easy recognizable
companies. Report failures and missingness by geography, size and source coverage.

`POST /api/pilot/reviews` stores owned-report paired timing estimates and ratings.
`GET /api/pilot/metrics` returns 100 × mean(manual_minutes−review_minutes)/60.
Negative savings stay negative. Empty datasets return null. These are self-reported
estimates, not causal proof of ROI. No fabricated numerator or denominator.

Predictive study: entity-disjoint, out-of-time development/test split, baseline
comparison, confidence intervals, subgroup calibration, missingness, drift and
false-positive/negative review. Require dated ground truth and pre-outcome feature
snapshots. Existing release metadata alone cannot establish empirical validity.

`scripts/validate_dated_cohort.py` requires timezone-aware feature/outcome dates,
entity-disjoint train/test cohorts and a temporal cutoff before metric evaluation.
The older metric-only entrypoint remains for compatibility; use the dated-cohort
guard first for real validation. A probability model and independent labeled data
must precede predictive product claims.

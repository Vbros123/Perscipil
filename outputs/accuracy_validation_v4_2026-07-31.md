# PrivateLens v4 Accuracy and Release Status

Date: 2026-07-31

## Status

Predictive accuracy approval is not granted. Version 4 is a fail-closed evidence and governance release, not a claim that a predictive model has been validated.

## Corrected controls

- Vendor-produced composite scores cannot be injected into the PrivateLens result contract.
- Name-only and ambiguous entity matches are excluded.
- Exact registration number, or legal name plus a corroborating address field at 0.95 confidence, is required.
- Gateway match claims are independently bound to the requested country and supplied legal identifiers.
- Stale observations are excluded by signal-specific freshness limits.
- Missing provider observation dates are not replaced with fetch time.
- Public-web findings are context only and never show numeric score bars.
- A rating requires at least 70% model-weight coverage, verified legal identity, and two licensed providers.
- Even complete evidence remains on `Validation hold` while `MODEL_RELEASE_STAGE=shadow`.
- Every accepted input records provider, license reference, evidence ID, observation time, entity confidence, transform version, and snapshot hash.

## Automated validation

- Backend and evidence tests: 23 passed.
- Provider gateway tests: 3 passed.
- Frontend production build: passed.
- Browser flow: signup, onboarding, legal-entity search, unrated report, evidence gates, watchlist add/remove, history clear, compare validation, settings persistence, profile update, password rotation, password reset, email verification, and global lookup passed on desktop; the report also passed a 390px no-horizontal-overflow check.
- Dependency audit: `npm audit --omit=dev` and `pip-audit -r backend/requirements.txt` reported no known vulnerabilities.
- Tests cover score injection rejection, ambiguous or mismatched entities, entity-specific audit hashes, stale evidence, deterministic transforms, provider diversity, identity gating, model approval gating, Creditsafe date handling, and holdout metric calculations.

## Remaining proof required

The model cannot be promoted until a sufficiently large, time-indexed, out-of-time outcome cohort passes the thresholds in `backend/services/model_validation.py` and an independent reviewer approves the packet. The harness reports ROC-AUC, PR-AUC lift, Brier score, expected calibration error, false-negative rate, evidence coverage, and subgroup AUC gaps.

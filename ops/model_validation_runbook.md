> SUPERSEDED reference: consult `cleanup_deployment.md` and `../dataroom-prep/` for current controls. Historical assumptions below may no longer apply.

# Model Validation Runbook

PrivateLens v4 ships in `shadow` mode. A numeric rating must not be enabled until an independent reviewer approves an out-of-time validation packet.

## Holdout record

Each JSONL row must contain:

```json
{
  "company_id": "stable-non-name-id",
  "distress_probability": 0.72,
  "distress_within_12m": 1,
  "evidence_coverage": 0.8,
  "subgroup": "manufacturing"
}
```

The outcome label must be fixed before scoring. Use a documented definition such as bankruptcy, payment default, or a material delinquency within 12 months. Do not mix definitions after results are seen.

## Run

```bash
cd backend
PYTHONPATH=. python scripts/validate_model.py holdout.jsonl \
  --output validation-2026-001.json \
  --decision-threshold 0.50
```

The command exits `0` only when every configured release check passes. It measures sample size, event count, ROC-AUC, PR-AUC lift over prevalence, Brier score, expected calibration error, false-negative rate, usable evidence coverage, and subgroup AUC gaps.

## Approval

1. Keep the holdout and generated JSON immutable.
2. Have a qualified independent model-risk reviewer reproduce the run.
3. Document data provenance, outcome definition, cohort dates, exclusions, leakage checks, subgroup analysis, and threshold rationale.
4. Record the approved packet ID in `MODEL_VALIDATION_REFERENCE`, its SHA-256 in `MODEL_VALIDATION_SHA256`, and reviewer or committee in `MODEL_APPROVED_BY`.
5. Change `MODEL_RELEASE_STAGE` to `validated` only after the legal permitted-use review also passes.

Production startup rejects a validated release without the reference and approver fields.

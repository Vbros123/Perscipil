# PrivateLens Accuracy Validation

Date: 2026-07-31  
Model reviewed: v2.0  
Corrected scoring contract: v3.0

## Executive conclusion

The original public-data score was not accurate enough for credit, lending, investment, vendor-risk, or partnership decisions. Most configured model weight came from generated fallback values, entity resolution was weak, and the same company could move hundreds of points after a process restart.

Version 3.0 now fails closed. Public mode returns `Unrated`, shows no user-facing financial-health score, keeps open-data findings as research context, and never fabricates company-specific values. A rating is available only when entity-resolved licensed inputs cover at least 50% of configured model weight.

## Test scope

- All 17 frontend routes, including signup, onboarding, login, recovery, verification, dashboard, reports, compare, watchlist, history, settings, account, developer, pricing, and not-found behavior.
- All API families: health, metrics protection, compliance, auth, users, settings, score, compare, signals, cache, watchlist, and history.
- Desktop and 390 x 844 mobile layouts, including horizontal-overflow checks.
- Fresh SQLite migration, Python dependency integrity, frontend production build, and npm advisory scan.
- Accuracy challenge set containing healthy operating companies, failed companies, and a nonexistent control name.

## Original accuracy failures

1. Generated fallback values influenced at least 70% of configured model weight in typical public-mode runs.
2. The same modeled-only Cargill input produced scores from 434 to 756 across 40 fresh Python processes, a 322-point spread without new evidence.
3. `Zxqvpl Fake Holdings`, a nonexistent control, scored 628 and tied Stripe while exceeding Cargill, Publix, Mars, FTX, and Theranos.
4. SEC full-text keyword volume was treated as risk. Broad mentions produced thousands of supposed filings for names such as Cargill and forced a zero regulatory score without issuer-level entity resolution.
5. USASpending broad recipient matches attributed unrelated awards to companies.
6. Random fallbacks displayed invented liens, lawsuits, reviews, traffic, followers, retention, payment days, and CEO approval.
7. Confidence counted live sources equally instead of measuring verified model-weight coverage.

## Reference-case comparison

| Company | Original output | External reference evidence | Validation result |
| --- | --- | --- | --- |
| Cargill | 544, Weak / Elevated | FY2025 revenue reported at $154B | Material false-negative risk |
| Publix Super Markets | 516, Weak / Elevated | 2025 sales $62.7B and net earnings $4.7B | Material false-negative risk |
| Stripe | 628, Adequate / Moderate | 2025 volume $1.9T, 34% growth, described as robustly profitable | Weak discrimination |
| FTX | 537, Weak / Elevated | Founder sentenced after fraud involving billions of customer funds | Severity materially understated |
| Theranos | 544, Weak / Elevated | Defunct; SEC charged massive fraud and DOJ obtained investor-fraud conviction | Severity materially understated |
| Zxqvpl Fake Holdings | 628, Adequate / Moderate | Nonexistent control name | Entity-existence failure |

Reference sources:

- [Cargill 2025 annual report](https://www.cargill.com/doc/1432279934974/2025-cargill-annual-report.pdf)
- [Publix 2025 annual results](https://www.publixstockholder.com/financial-information-and-filings/financial-news-releases/Publix-reports-fourth-quarter-and-annual-results-for-2025)
- [Stripe 2025 annual update](https://stripe.com/en-no/newsroom/news/stripe-2025-update)
- [DOJ FTX sentencing release](https://www.justice.gov/usao-sdny/pr/samuel-bankman-fried-sentenced-25-years-prison)
- [SEC Theranos enforcement release](https://www.sec.gov/newsroom/press-releases/2018-41)
- [DOJ Theranos sentencing release](https://www.justice.gov/usao-ndca/pr/elizabeth-holmes-sentenced-more-11-years-defrauding-theranos-investors-hundreds)

## Corrected public-mode benchmark

| Company | Status | User-facing score | Verified score coverage | Score inputs |
| --- | --- | --- | --- | --- |
| Cargill | Unrated | N/A | 0% | 0 |
| Publix Super Markets | Unrated | N/A | 0% | 0 |
| Stripe | Unrated | N/A | 0% | 0 |
| FTX | Unrated | N/A | 0% | 0 |
| Theranos | Unrated | N/A | 0% | 0 |
| Zxqvpl Fake Holdings | Unrated | N/A | 0% | 0 |

Open-data findings remain visible as `Context only`. Missing paid sources render as `Unavailable / Not scored` and contain no generated company values.

## Release gates for a validated rating

PrivateLens should not claim predictive accuracy until all of the following exist:

1. Stable entity identifiers and entity-resolution precision measured on a labeled company set.
2. Licensed payment, cash-flow, UCC, court, and other contracted data with provenance and permitted-use records.
3. A time-indexed outcome dataset with distress/default definitions fixed before model fitting.
4. Train, calibration, and out-of-time holdout cohorts with no company leakage.
5. Reported ROC-AUC, PR-AUC, Brier score, calibration error, coverage, false-negative rate, and subgroup performance.
6. Baseline comparison against a simple prior and ablation tests for each signal family.
7. Independent model-risk, security, and legal/compliance review before decision use.
8. Ongoing drift monitoring, source-quality alerts, score-version retention, and documented rollback thresholds.

## Verification summary

- Backend tests: 12 passed.
- Frontend production build: passed.
- Fresh migration: passed.
- Desktop/mobile workflow checks: passed after fixes.
- Remaining dependency advisory: React Router RSC-mode CSRF advisory; this Vite client-only SPA does not enable React Server Components, so the affected execution path is not present. The scanner remains red until an upstream non-breaking release resolves it.
- Accuracy approval: not granted for predictive use. Public mode is safe for contextual research only; licensed mode still requires formal validation before production decisioning.

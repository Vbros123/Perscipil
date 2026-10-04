# Pitch-deck diligence

Open Research → Deck diligence after signing in. Upload one PDF/PPTX and up to two optional reference decks you have permission to compare. Limit: 2 MiB and 60 slides per file. Download the diligence memo before leaving.

## Included

Slide-linked text extraction; eight diligence topics and follow-up questions; absolute/competition/credential claims for verification; reconciliation of differing explicitly labeled ARR/MRR values in the same currency; up to 80 unverified numeric excerpts; up to 30 strongest exact-phrase matches against supplied decks; inspectable slide text and a downloadable memo.

Revenue differences may reflect different dates or forecasts. Comparison requires at least five shared eight-word phrases; templates or common sources can explain overlap. Neither check establishes fraud or copying.

## Limits and privacy

Deterministic document checks, no paid AI calls or external web search. No market-wide competitor map, legal clearance, or investment recommendation. Images, charts, notes, embedded spreadsheets and scanned text are not evaluated. Topic mentions do not establish sufficient evidence; no findings does not establish a sound investment.

Authenticated POST /api/decks/review accepts JSON with a deck and optional references, each containing name and base64 data. Documents and reviews are transient, not stored in the account, database or filesystem, and not sent to third-party models. Downloaded memos are under the analyst's control. Existing session/policy checks apply. Three requests per user per minute, using the shared database limiter in production.

A disposable parser process has no application secrets in its environment, a 256 MiB address-space cap, eight CPU seconds, a 15-second timeout, and disabled core dumps. One parser runs per API process. PPTX archives are bounded and never unpacked; no macros or external relationships are executed. This is resource isolation, not a general OS sandbox. Only this endpoint gets a 9 MiB encoded-body limit; other routes retain 1 MiB. Free-service sleep/compute limits still apply.

## Validation

Regressions cover PDF extraction/encryption, actual PPTX slide order, malformed/empty files, archive expansion/page limits, cited revenue differences and equivalent units, wording overlap, instruction text treated as data, isolated processing, authenticated access and input restrictions. Browser authentication remains a separate hosted verification gate.

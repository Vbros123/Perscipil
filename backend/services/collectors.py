"""
PrivateLens Data Collectors v5
Public collectors return live, modelled, unavailable, or not_applicable results.
Licensed score inputs are supplied by the evidence gateway and transformed locally.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from core.config import get_settings
from services.evidence import CompanyIdentity
from services.licensed_data import collect_licensed_signals
from services.resolver import (
    _founded_year,
    _looks_like_organisation,
    canonical_key,
    names_match,
)

settings = get_settings()

HEADERS = {"User-Agent": get_settings().PUBLIC_DATA_USER_AGENT}

# USASpending returns awards page by page. Anything derived from one page is a
# floor across the largest awards, not a lifetime total.
AWARD_PAGE_SIZE = 10
AWARD_SEARCH_START = "2022-01-01"

# Re-exported so existing tests keep importing from this module.
_normalize_entity_name = canonical_key


SOURCE_META = {
    "gleif": {"label": "GLEIF", "group": "identity", "groupLabel": "IDENTITY & REGISTRY"},
    "sec": {"label": "SEC EDGAR", "group": "financial_regulatory", "groupLabel": "FINANCIAL & REGULATORY"},
    "usaspending": {"label": "USASpending", "group": "government", "groupLabel": "GOVERNMENT ACTIVITY"},
    "census": {"label": "Census", "group": "industry", "groupLabel": "INDUSTRY CONTEXT"},
    "wikipedia": {"label": "Wikipedia", "group": "public_signals", "groupLabel": "PUBLIC SIGNALS"},
    "news": {"label": "DuckDuckGo / Hacker News", "group": "public_signals", "groupLabel": "PUBLIC SIGNALS"},
    "jobs": {"label": "Jobs", "group": "operating", "groupLabel": "OPERATING SIGNALS"},
}


@dataclass
class CollectorResult:
    source: str
    status: str
    signals: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_quality: str | None = None
    optional: bool = False
    coverage: str | None = None
    entity_match: str | None = None
    source_url: str | None = None

    def as_source_card(self) -> dict[str, Any]:
        meta = SOURCE_META.get(self.source, {"label": self.source, "group": "public_signals", "groupLabel": "PUBLIC SIGNALS"})
        quality = self.evidence_quality
        if quality is None:
            if self.status == "live" and self.source in {"sec", "usaspending", "gleif"}:
                quality = "high"
            elif self.status == "live" and self.source == "census":
                quality = "medium"
            elif self.status == "live":
                quality = "low"
            elif self.status == "modelled":
                quality = "modelled"
            elif self.status == "not_applicable":
                quality = "not_applicable"
            else:
                quality = "unavailable"
        coverage = self.coverage
        if coverage is None:
            if self.status == "not_applicable":
                coverage = "n/a"
            elif self.status != "live":
                coverage = "none"
            elif self.source == "census":
                coverage = "industry"
            elif self.source in {"gleif", "sec", "usaspending"}:
                coverage = "entity"
            else:
                coverage = "keyword"
        return {
            "source": meta["label"],
            "key": self.source,
            "status": self.status,
            "evidenceQuality": quality,
            "coverage": coverage,
            "lastRetrieved": self.retrieved_at,
            "errorCode": self.error_code,
            "entityMatch": self.entity_match,
            "sourceUrl": self.source_url,
            "group": meta["group"],
            "groupLabel": meta["groupLabel"],
            "optional": self.optional,
        }


def _clamp(val: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, val))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_timeout() -> httpx.Timeout:
    budget = max(2.0, float(settings.HTTP_TIMEOUT))
    return httpx.Timeout(connect=min(3.0, budget), read=budget, write=min(5.0, budget), pool=3.0)


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "TIMEOUT"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status == 429:
            return "RATE_LIMIT"
        if status in {401, 403}:
            return "BLOCKED"
        return "HTTP_ERROR"
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "MALFORMED"
    name = type(exc).__name__.upper()
    if "TIMEOUT" in name:
        return "TIMEOUT"
    return name[:32]


def _public_signal(
    *,
    name: str,
    icon: str,
    category: str,
    display: str,
    status: str,
    source_url: str,
    insight: str,
    raw_score: float | None = None,
    extra: dict[str, Any] | None = None,
    evidence_quality: str | None = None,
) -> dict[str, Any]:
    scored = status in {"live", "modelled"} and raw_score is not None
    if evidence_quality is None:
        if status == "modelled":
            evidence_quality = "modelled"
        elif status == "unavailable":
            evidence_quality = "unavailable"
        elif status == "not_applicable":
            evidence_quality = "not_applicable"
        else:
            evidence_quality = "low"
    payload = {
        "signal": name,
        "icon": icon,
        "category": category,
        "display": display,
        "raw_score": round(raw_score, 1) if scored else None,
        "is_simulated": status == "modelled",
        "is_scored": scored,
        "availability_status": status,
        "source_url": source_url,
        "insight": insight,
        "retrieved_at": _now(),
        "evidence_quality": evidence_quality,
    }
    if extra:
        payload.update(extra)
    return payload


def _unavailable_signal(signal: str, icon: str, category: str, source_url: str, reason: str | None = None) -> dict:
    return _public_signal(
        name=signal,
        icon=icon,
        category=category,
        display="Verified data unavailable — not scored",
        status="unavailable",
        source_url=source_url,
        insight=(
            reason
            or (
                "No verified data was available for this signal during the current run. "
                "It is excluded from the evidence score."
            )
        ),
        extra={"is_simulated": True, "is_scored": False},
    )


def _not_applicable_signal(signal: str, icon: str, category: str, source_url: str, display: str, insight: str) -> dict:
    return _public_signal(
        name=signal,
        icon=icon,
        category=category,
        display=display,
        status="not_applicable",
        source_url=source_url,
        insight=insight,
        extra={"is_simulated": False, "is_scored": False},
    )


def _result(
    source: str,
    signals: list[dict[str, Any]],
    error: str | None = None,
    error_code: str | None = None,
    optional: bool = False,
    coverage: str | None = None,
    entity_match: str | None = None,
    source_url: str | None = None,
    evidence_quality: str | None = None,
) -> CollectorResult:
    statuses = [item.get("availability_status") or "unavailable" for item in signals]
    if any(status == "live" for status in statuses):
        overall = "live"
    elif any(status == "modelled" for status in statuses):
        overall = "modelled"
    elif statuses and all(status == "not_applicable" for status in statuses):
        overall = "not_applicable"
    else:
        overall = "unavailable"
    return CollectorResult(
        source=source,
        status=overall,
        signals=signals,
        error=error,
        error_code=error_code,
        retrieved_at=_now(),
        optional=optional,
        coverage=coverage,
        entity_match=entity_match,
        source_url=source_url,
        evidence_quality=evidence_quality,
    )


def _hiring_score(count: int) -> float:
    # A live zero is "no current postings", not a mid-range default. Keyword job
    # counts also cannot reach 100 — they are not entity-resolved headcount.
    if count <= 0:
        return 22.0
    return _clamp(22.0 + math.log10(count + 1) * 18.0, 0.0, 88.0)


def _news_score(pos: int, neg: int, hn_hits: int) -> float:
    polarity = (pos - neg) / (pos + neg)
    # Keyword polarity is a weak supporting signal. Cap well below 100 so a
    # handful of positive words cannot look like verified financial strength.
    return _clamp(50.0 + polarity * 20.0 + min(5.0, hn_hits * 0.35), 20.0, 72.0)


def _award_score(total: float) -> float:
    return _clamp(math.log10(max(total, 0.0) + 1.0) * 11.0, 0.0, 92.0)


def _stability_score(founded_year: int) -> float:
    age = datetime.now().year - founded_year
    # Age is a supporting operational band, not proof of creditworthiness.
    if age >= 50:
        return 76.0
    if age >= 20:
        return 66.0
    if age >= 10:
        return 56.0
    if age >= 5:
        return 48.0
    return 40.0


# ── REAL COLLECTORS ────────────────────────────────────────────────────────────

def _money(value: float | None) -> str:
    if value is None:
        return "n/a"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.1f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    return f"${value:,.0f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


async def collect_sec_edgar(name: str, resolved=None) -> CollectorResult:
    """Official data.sec.gov CIK + XBRL facts. Private companies stay NOT_APPLICABLE."""
    source_url = "https://data.sec.gov"
    company_type = getattr(resolved, "company_type", "unknown") or "unknown"
    identifiers = getattr(resolved, "identifiers", None) or {}
    if company_type == "private" and not identifiers.get("cik"):
        return _result(
            "sec",
            [_not_applicable_signal(
                "SEC Financial Evidence",
                "📋",
                "financial",
                source_url,
                "Not applicable — private company, not an SEC filer",
                "This company is treated as private, so SEC filings are not a company financial record "
                "and are excluded from scoring.",
            )],
            coverage="n/a",
            entity_match="Private company",
            source_url=source_url,
            evidence_quality="not_applicable",
        )
    try:
        from services.providers.sec import lookup_sec, score_sec_financials

        payload = getattr(resolved, "sec", None) if resolved is not None else None
        lookup = None
        if isinstance(payload, dict) and payload.get("status") in {"not_applicable", "unavailable"} and not payload.get("selected"):
            from services.providers.sec import SecLookup
            lookup = SecLookup(status=payload.get("status") or "not_applicable", error_code=payload.get("errorCode"))
        elif isinstance(payload, dict) and payload.get("selected") and payload.get("status") == "live":
            from services.providers.sec import SecEntity, SecLookup

            selected = payload["selected"]
            lookup = SecLookup(
                selected=SecEntity(
                    cik=selected.get("cik"),
                    ticker=selected.get("ticker"),
                    title=selected.get("title"),
                    match_score=int(selected.get("matchScore") or 0),
                    submissions=selected.get("submissions"),
                    financials=selected.get("financials"),
                    source_url=selected.get("sourceUrl"),
                ),
                status="live",
                error_code=payload.get("errorCode"),
            )
        else:
            aliases = list(getattr(resolved, "aliases", None) or [])
            legal = getattr(resolved, "legal_name", None)
            if legal and legal not in aliases:
                aliases.append(legal)
            cik = (getattr(resolved, "identifiers", None) or {}).get("cik")
            lookup = await lookup_sec(name, aliases=aliases, cik=cik)

        if lookup.status == "not_applicable" or (lookup.selected is None and lookup.error_code == "NO_CIK"):
            display = (
                "Not applicable — private company, not an SEC filer"
                if company_type == "private"
                else "Not applicable — not an SEC registrant"
            )
            return _result(
                "sec",
                [_not_applicable_signal(
                    "SEC Financial Evidence",
                    "📋",
                    "financial",
                    source_url,
                    display,
                    "No matching SEC registrant was found. That is not negative financial evidence "
                    "and is excluded from PrivateScore.",
                )],
                coverage="n/a",
                entity_match="Private company" if company_type == "private" else "Not an SEC filer",
                source_url=source_url,
                evidence_quality="not_applicable",
            )
        if lookup.status != "live" or lookup.selected is None:
            code = lookup.error_code or "UNAVAILABLE"
            return _result(
                "sec",
                [_unavailable_signal(
                    "SEC Financial Evidence",
                    "📋",
                    "financial",
                    source_url,
                    "SEC EDGAR could not be retrieved. The report continues with remaining sources.",
                )],
                error=code,
                error_code=code,
                coverage="none",
                entity_match="Lookup failed",
                source_url=source_url,
            )

        entity = lookup.selected
        filings = (entity.submissions or {}).get("filings") or []
        metrics = entity.financials or {}
        raw = score_sec_financials(metrics)
        ticker = entity.ticker or (entity.submissions or {}).get("tickers", [None])[0]
        display_bits = [
            f"CIK {entity.cik}",
            ticker or None,
            f"revenue {_money(metrics.get('revenue'))}" if metrics.get("revenue") is not None else None,
            f"net income {_money(metrics.get('netIncome'))}" if metrics.get("netIncome") is not None else None,
        ]
        leverage = metrics.get("debtToEquity")
        fact_bits = []
        for key, label in (
            ("revenue", "Revenue"),
            ("assets", "Assets"),
            ("liabilities", "Liabilities"),
            ("cash", "Cash"),
            ("equity", "Equity"),
            ("netIncome", "Net income"),
            ("operatingIncome", "Operating income"),
        ):
            fact = (metrics.get("facts") or {}).get(key)
            if not fact:
                continue
            fact_bits.append(
                f"{label} {_money(fact.get('value'))} {fact.get('unit') or 'USD'} "
                f"({fact.get('period')} FY{fact.get('fiscalYear') or '?'} "
                f"{fact.get('form') or ''} ended {fact.get('periodEnd') or 'n/a'}"
                f"{', filed ' + str(fact['filed']) if fact.get('filed') else ''})"
            )
        insight = (
            f"SEC registrant {entity.title or name} (CIK {entity.cik}"
            f"{', ticker ' + ticker if ticker else ''}). "
            + ("; ".join(fact_bits) + ". " if fact_bits else "")
            + f"Annual revenue growth {_pct(metrics.get('revenueGrowth'))}; "
            f"operating margin {_pct(metrics.get('operatingMargin'))}"
            f"{f'; debt/equity {leverage:.2f}' if leverage is not None else ''}. "
            "Ratios use annual facts from the same fiscal year only. "
            f"{len(filings)} recent filing(s) are listed on the submissions feed. "
            "These are company-specific XBRL facts, not industry estimates."
        )
        return _result(
            "sec",
            [_public_signal(
                name="SEC Financial Evidence",
                icon="📋",
                category="financial",
                display=" · ".join(item for item in display_bits if item),
                raw_score=raw,
                status="live",
                source_url=entity.source_url or source_url,
                insight=insight,
                extra={
                    "is_scored": raw is not None,
                    "is_simulated": False,
                    "evidence_scope": "company",
                    "cik": entity.cik,
                    "ticker": ticker,
                    "financials": metrics,
                    "filings": filings[:8],
                    "entity_match_confidence": min(1.0, (entity.match_score or 80) / 100),
                },
                evidence_quality="high",
            )],
            coverage="entity",
            entity_match="Entity matched",
            source_url=entity.source_url or source_url,
            evidence_quality="high",
        )
    except Exception as exc:
        code = _error_code(exc)
        if code == "MALFORMED":
            code = "MALFORMED_RESPONSE"
        return _result(
            "sec",
            [_unavailable_signal("SEC Financial Evidence", "📋", "financial", source_url)],
            error=code,
            error_code=code,
            coverage="none",
            source_url=source_url,
        )


def _wikipedia_signals_from_summary(name: str, summary: dict) -> list[dict[str, Any]] | None:
    if summary.get("type") == "disambiguation":
        return None
    if not _looks_like_organisation(summary):
        return None
    resolved_title = summary.get("title") or ""
    if not names_match(name, resolved_title):
        return None
    extract = summary.get("extract") or ""
    founded = _founded_year(extract)
    age_note = ""
    if founded:
        age_note = f" Founded {founded} ({datetime.now().year - founded} years ago)."
    wiki_url = f"https://en.wikipedia.org/wiki/{resolved_title.replace(' ', '_')}"
    digital = _public_signal(
        name="Brand Legitimacy & Web Presence",
        icon="🌐",
        category="identity",
        display=f"Wikipedia article: {resolved_title}{age_note}",
        raw_score=56.0,
        status="live",
        source_url=wiki_url,
        evidence_quality="low",
        insight=(
            f"Matched the Wikipedia article \"{resolved_title}\""
            f"{' — ' + summary['description'] if summary.get('description') else ''}."
            f"{age_note} Article presence confirms a public identity page; it is not "
            "a measure of revenue, customers, or financial health."
        ),
        extra={"matched_entity": resolved_title},
    )
    if founded:
        stability = _public_signal(
            name="Company Stability",
            icon="🏢",
            category="operational",
            display=f"Operating age about {datetime.now().year - founded} years (founded {founded})",
            raw_score=_stability_score(founded),
            status="live",
            source_url=wiki_url,
            insight=(
                f"Wikipedia reports a founding year of {founded}. Age is a supporting stability band, "
                "not proof of creditworthiness or commercial traction."
            ),
            extra={"matched_entity": resolved_title, "founded_year": founded},
            evidence_quality="medium",
        )
    else:
        stability = _unavailable_signal(
            "Company Stability",
            "🏢",
            "operational",
            wiki_url,
            "No founding year was found on the matched Wikipedia article, so no age score was inferred.",
        )
    return [digital, stability]


def _no_wikipedia_signals(name: str, reason: str) -> list[dict[str, Any]]:
    search_url = "https://en.wikipedia.org/wiki/Special:Search?search=" + name.replace(" ", "+")
    return [
        _unavailable_signal(
            "Brand Legitimacy & Web Presence",
            "🌐",
            "identity",
            search_url,
            f"No Wikipedia article was confidently resolved to this company ({reason}). "
            "Absence of an article is not evidence about the company, so no value was inferred.",
        ),
        _unavailable_signal(
            "Company Stability",
            "🏢",
            "operational",
            search_url,
            "Company age was not scored because no organisation article was resolved.",
        ),
    ]


async def _wikipedia_summary(client: httpx.AsyncClient, title: str) -> dict | None:
    resp = await client.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
        headers=HEADERS,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


async def collect_wikipedia(name: str, resolved=None) -> CollectorResult:
    """Resolve the company's Wikipedia article as a live digital-presence signal."""
    if getattr(resolved, "wikipedia_summary", None):
        signals = _wikipedia_signals_from_summary(name, resolved.wikipedia_summary)
        if signals:
            return _result("wikipedia", signals)

    requested = canonical_key(name)
    if not requested:
        return _result("wikipedia", _no_wikipedia_signals(name, "no searchable company name was provided"))
    try:
        async with httpx.AsyncClient(timeout=_http_timeout()) as client:
            search = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": f"{name} company",
                    "srlimit": 5,
                    "format": "json",
                },
                headers=HEADERS,
            )
            candidates: list[str] = [name]
            if search.status_code == 200:
                for hit in search.json().get("query", {}).get("search", []):
                    title = hit.get("title")
                    if title and title not in candidates:
                        candidates.append(title)

            for title in candidates:
                summary = await _wikipedia_summary(client, title)
                if not summary:
                    continue
                signals = _wikipedia_signals_from_summary(name, summary)
                if signals:
                    return _result("wikipedia", signals)
            return _result("wikipedia", _no_wikipedia_signals(name, "no candidate article resolved to this organisation"))
    except Exception as exc:
        return _result("wikipedia", _no_wikipedia_signals(name, "wikipedia lookup failed"), error=_error_code(exc), error_code=_error_code(exc))


async def collect_news_sentiment(name: str, resolved=None) -> CollectorResult:
    """DuckDuckGo instant answers + HackerNews search for news sentiment."""
    source_url = f"https://hn.algolia.com/api/v1/search?query={name.replace(' ', '%20')}&tags=story"
    try:
        pos_words = {
            "growth", "profit", "revenue", "raises", "expands", "wins",
            "award", "launch", "partnership", "record", "acquisition", "innovation",
            "promotion", "dividend", "milestone", "breakthrough",
        }
        neg_words = {
            "lawsuit", "fraud", "bankrupt", "layoff", "scandal", "loss",
            "investigation", "debt", "closure", "default", "breach", "fine",
            "recall", "dispute", "settlement", "penalty", "downgrade",
        }

        async with httpx.AsyncClient(timeout=_http_timeout(), follow_redirects=True) as client:
            ddg = await client.get(
                f"https://api.duckduckgo.com/?q={name.replace(' ', '+')}&format=json&no_html=1",
                headers=HEADERS,
            )
            hn = await client.get(source_url, headers=HEADERS)

        text = ""
        if ddg.status_code == 200:
            data = ddg.json()
            text += data.get("Abstract", "") + " "
            text += " ".join(
                topic.get("Text", "")
                for topic in data.get("RelatedTopics", [])[:8]
                if isinstance(topic, dict)
            )

        hn_hits = 0
        if hn.status_code == 200:
            hits = hn.json().get("hits", [])
            hn_hits = len(hits)
            text += " ".join(item.get("title", "") for item in hits)

        text = text.lower()
        pos = sum(1 for word in pos_words if word in text)
        neg = sum(1 for word in neg_words if word in text)
        if pos + neg == 0:
            return _result("news", [_unavailable_signal(
                "News & Media Sentiment",
                "📰",
                "sentiment",
                source_url,
                "No usable positive or negative polarity counts were found, so news sentiment was not scored.",
            )])

        if pos > neg * 1.5:
            label = "Positive"
        elif neg > pos * 1.5:
            label = "Negative"
        else:
            label = "Mixed"

        return _result("news", [_public_signal(
            name="News & Media Sentiment",
            icon="📰",
            category="sentiment",
            display=f"{label} — {pos} positive, {neg} negative signals, {hn_hits} HN mentions",
            raw_score=_news_score(pos, neg, hn_hits),
            status="live",
            evidence_quality="low",
            source_url=source_url,
            insight=(
                f"Keyword context across DuckDuckGo and HackerNews: {pos} positive indicator(s), "
                f"{neg} negative indicator(s), and {hn_hits} Hacker News mention(s). "
                "This is a low-quality supporting sentiment signal, not entity-resolved credit news, "
                "and it cannot by itself produce a high PrivateScore."
            ),
        )])
    except Exception as exc:
        return _result(
            "news",
            [_unavailable_signal("News & Media Sentiment", "📰", "sentiment", "https://newsapi.org")],
            error=_error_code(exc),
            error_code=_error_code(exc),
        )


async def collect_job_postings(name: str, resolved=None) -> CollectorResult:
    """Optional operating signal. Indeed is not scraped and is not required."""
    source_url = "https://www.indeed.com"
    return _result(
        "jobs",
        [_unavailable_signal(
            "Job Posting Velocity",
            "💼",
            "operational",
            source_url,
            "Job posting data is an optional public signal. PrivateLens does not scrape Indeed "
            "and does not treat missing hiring data as a system failure or as negative evidence.",
        )],
        error="OPTIONAL_UNAVAILABLE",
        error_code="OPTIONAL_UNAVAILABLE",
        optional=True,
        coverage="none",
        entity_match="Optional source",
        source_url=source_url,
        evidence_quality="none",
    )


def _recipient_names(name: str, resolved=None) -> list[str]:
    names = [name]
    if resolved is not None:
        for item in (
            getattr(resolved, "legal_name", None),
            getattr(resolved, "canonical_name", None),
            *((getattr(resolved, "aliases", None) or [])),
        ):
            if item and item not in names:
                names.append(item)
        gleif = getattr(resolved, "gleif", None) or {}
        selected = gleif.get("selected") if isinstance(gleif, dict) else None
        if isinstance(selected, dict) and selected.get("legalName"):
            if selected["legalName"] not in names:
                names.append(selected["legalName"])
    return names


def _award_matches_recipient(recipient_name: str, accepted: list[str]) -> bool:
    return any(names_match(recipient_name, item) or canonical_key(recipient_name) == canonical_key(item) for item in accepted)


def _usaspending_match_tier(recipient_name: str, accepted: list[str], unique_recipient: bool) -> str:
    if not recipient_name or not accepted:
        return "Unresolved"
    exact = any(canonical_key(recipient_name) == canonical_key(item) for item in accepted)
    strong = any(names_match(recipient_name, item) for item in accepted)
    if exact and unique_recipient:
        return "Exact"
    if exact or (strong and unique_recipient):
        return "Strong"
    if strong:
        return "Name Match"
    return "Unresolved"


async def collect_usa_spending(name: str, resolved=None) -> CollectorResult:
    """USASpending.gov — federal awards for a matched recipient, not a similar name."""
    source_url = f"https://www.usaspending.gov/search/?query={name.replace(' ', '%20')}"
    accepted = _recipient_names(name, resolved)
    try:
        async with httpx.AsyncClient(timeout=_http_timeout()) as client:
            recipient = None
            try:
                auto = await client.post(
                    "https://api.usaspending.gov/api/v2/autocomplete/recipient/",
                    json={"search_text": accepted[0], "limit": 10},
                    headers={**HEADERS, "Content-Type": "application/json"},
                )
                if auto.status_code == 200:
                    rows = auto.json().get("results") or []
                    exact = [
                        item for item in rows
                        if _award_matches_recipient(item.get("recipient_name") or item.get("legal_business_name") or "", accepted)
                    ]
                    if len(exact) == 1:
                        recipient = exact[0]
                    elif len(exact) > 1:
                        recipient = exact[0]
                        recipient = {**recipient, "ambiguous": True}
            except Exception:
                recipient = None

            search_name = (
                (recipient or {}).get("recipient_name")
                or (recipient or {}).get("legal_business_name")
                or accepted[0]
            )
            resp = await client.post(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                json={
                    "filters": {
                        "recipient_search_text": [search_name],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": AWARD_SEARCH_START, "end_date": datetime.now().strftime("%Y-%m-%d")}],
                    },
                    "fields": [
                        "Award Amount",
                        "Recipient Name",
                        "Recipient UEI",
                        "Awarding Agency",
                        "Award Type",
                        "Start Date",
                        "End Date",
                    ],
                    "page": 1,
                    "limit": AWARD_PAGE_SIZE,
                    "sort": "Award Amount",
                    "order": "desc",
                },
                headers={**HEADERS, "Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                raise httpx.HTTPStatusError("usaspending failed", request=resp.request, response=resp)
            data = resp.json()
            results = data.get("results", [])
            verified = [
                item for item in results
                if _award_matches_recipient(item.get("Recipient Name", ""), accepted)
            ]
            total = sum(item.get("Award Amount", 0) or 0 for item in verified)
            count = len(verified)
            unverified_count = len(results) - count
            truncated = bool(data.get("page_metadata", {}).get("hasNext"))
            exact_unique = bool(recipient) and not recipient.get("ambiguous")
            if count == 0:
                return _result(
                    "usaspending",
                    [_not_applicable_signal(
                        "Government Contract Awards",
                        "🏛️",
                        "government",
                        source_url,
                        (
                            f"Not applicable — no matched recipient in the {AWARD_PAGE_SIZE} largest awards"
                            + (f"; {unverified_count} similarly named award(s) excluded" if unverified_count else "")
                        ),
                        "No award matched the resolved legal name or aliases. Similarly named recipients "
                        "were excluded. That is not a failed observation for a company that may not be "
                        "a federal contractor.",
                    )],
                    coverage="n/a",
                    entity_match="Unresolved",
                    source_url=source_url,
                    evidence_quality="not_applicable",
                )
            uei = (recipient or {}).get("uei") or next((item.get("Recipient UEI") for item in verified if item.get("Recipient UEI")), None)
            duns = (recipient or {}).get("duns")
            agencies = sorted({item.get("Awarding Agency") for item in verified if item.get("Awarding Agency")})
            types = sorted({item.get("Award Type") for item in verified if item.get("Award Type")})
            if resolved is not None and uei:
                identifiers = dict(getattr(resolved, "identifiers", None) or {})
                identifiers["uei"] = uei
                if duns:
                    identifiers["duns"] = str(duns)
                resolved.identifiers = identifiers
            sample_name = verified[0].get("Recipient Name") or search_name
            match_label = _usaspending_match_tier(sample_name, accepted, exact_unique)
            quality = {"Exact": "high", "Strong": "high", "Name Match": "medium"}.get(match_label, "low")
            exact_match = match_label in {"Exact", "Strong"}
            return _result(
                "usaspending",
                [_public_signal(
                    name="Government Contract Awards",
                    icon="🏛️",
                    category="government",
                    display=(
                        f"{count} matched award(s) · ${total:,.0f} obligated"
                        + (f" · UEI {uei}" if uei else "")
                    ),
                    raw_score=_award_score(total) if match_label in {"Exact", "Strong", "Name Match"} else None,
                    status="live",
                    evidence_quality=quality,
                    source_url=source_url,
                    insight=(
                        f"USASpending.gov returned {count} award(s) for recipient {sample_name}. "
                        f"Entity match: {match_label}. Matched obligations on this page total ${total:,.0f}"
                        f"{f'; UEI {uei}' if uei else ''}"
                        f"{f'; DUNS {duns}' if duns else ''}. "
                        f"Award types: {', '.join(types) or 'unspecified'}. "
                        f"Agencies: {', '.join(agencies[:6]) or 'unspecified'}. "
                        "This is a floor across the retrieved page, not lifetime federal spend. "
                        + (
                            "Recipient identity was confirmed before attributing awards."
                            if match_label in {"Exact", "Strong"}
                            else "The recipient was only name-matched, so confidence is lowered and "
                            "similarly named entities were not assumed to be the same company."
                        )
                        + (" More awards exist beyond this page." if truncated else "")
                    ),
                    extra={
                        "evidence_scope": "company",
                        "uei": uei,
                        "duns": duns,
                        "awardCount": count,
                        "totalObligations": total,
                        "awardTypes": types,
                        "agencies": agencies,
                        "entityMatch": match_label,
                        "entity_match_confidence": {"Exact": 0.95, "Strong": 0.82, "Name Match": 0.58}.get(match_label, 0.0),
                    },
                )],
                coverage="entity",
                entity_match=match_label,
                source_url=source_url,
                evidence_quality=quality,
            )
    except Exception as exc:
        return _result(
            "usaspending",
            [_unavailable_signal("Government Contract Awards", "🏛️", "government", "https://www.usaspending.gov")],
            error=_error_code(exc),
            error_code=_error_code(exc),
            coverage="none",
            source_url="https://www.usaspending.gov",
        )


FALLBACK_SIGNALS = {
    "sec": [("SEC Financial Evidence", "📋", "financial", "https://data.sec.gov")],
    "wikipedia": [
        ("Brand Legitimacy & Web Presence", "🌐", "identity", "https://en.wikipedia.org"),
        ("Company Stability", "🏢", "operational", "https://en.wikipedia.org"),
    ],
    "news": [("News & Media Sentiment", "📰", "sentiment", "https://newsapi.org")],
    "jobs": [("Job Posting Velocity", "💼", "operational", "https://www.indeed.com")],
    "usaspending": [("Government Contract Awards", "🏛️", "government", "https://www.usaspending.gov")],
    "gleif": [("Legal Entity Identity", "🪪", "identity", "https://api.gleif.org/api/v1")],
    "census": [("Industry Context", "🏭", "industry", "https://api.census.gov")],
}


def _crash_result(source: str, error: BaseException) -> CollectorResult:
    specs = FALLBACK_SIGNALS.get(source, [(source, "data", "operational", "")])
    code = _error_code(error)
    return CollectorResult(
        source=source,
        status="unavailable",
        signals=[_unavailable_signal(*spec) for spec in specs],
        error=code,
        error_code=code,
        retrieved_at=_now(),
        evidence_quality="unavailable",
        optional=source in {"jobs", "census"},
    )


async def collect_gleif(name: str, resolved=None) -> CollectorResult:
    """GLEIF legal-entity identity. Context only — never a PrivateScore input."""
    source_url = "https://www.gleif.org"
    try:
        selected = None
        error_code = None
        payload = getattr(resolved, "gleif", None) if resolved is not None else None
        if isinstance(payload, dict) and payload.get("selected"):
            selected = payload["selected"]
            error_code = payload.get("errorCode")
        else:
            from services.providers.gleif import lookup_gleif

            country = None
            if resolved is not None:
                country = (getattr(resolved, "identifiers", {}) or {}).get("country")
            lookup = await lookup_gleif(name, country)
            if lookup.error_code:
                error_code = lookup.error_code
            if lookup.selected:
                selected = lookup.selected.as_identity_dict()
        if selected and selected.get("lei"):
            lei = selected["lei"]
            legal_name = selected.get("legalName") or name
            status = selected.get("entityStatus") or "unknown"
            insight = (
                f"GLEIF reports LEI {lei} for {legal_name} "
                f"(entity status {status}"
                f"{', jurisdiction ' + selected['jurisdiction'] if selected.get('jurisdiction') else ''}). "
                "This is legal-entity identification, not a financial-health observation, "
                "and is excluded from PrivateScore."
            )
            return _result("gleif", [_public_signal(
                name="Legal Entity Identity",
                icon="🪪",
                category="identity",
                display=f"LEI {lei} · {legal_name} · {status}",
                status="live",
                source_url=selected.get("sourceUrl") or f"https://api.gleif.org/api/v1/lei-records/{lei}",
                insight=insight,
                extra={
                    "is_scored": False,
                    "is_simulated": False,
                    "evidence_scope": "company",
                    "lei": lei,
                    "legalName": legal_name,
                    "entityStatus": selected.get("entityStatus"),
                    "jurisdiction": selected.get("jurisdiction"),
                    "legalForm": selected.get("legalForm"),
                    "registeredAddress": selected.get("registeredAddress"),
                    "parents": selected.get("parents") or [],
                    "retrievedAt": selected.get("retrievedAt"),
                },
                evidence_quality="high",
            )], error_code=error_code, coverage="entity", entity_match="Entity matched",
                source_url=selected.get("sourceUrl") or source_url, evidence_quality="high")
        if error_code:
            return _result(
                "gleif",
                [_unavailable_signal(
                    "Legal Entity Identity",
                    "🪪",
                    "identity",
                    source_url,
                    "GLEIF could not be reached. Missing LEI data is not a negative financial signal.",
                )],
                error=error_code,
                error_code=error_code,
            )
        return _result("gleif", [_not_applicable_signal(
            "Legal Entity Identity",
            "🪪",
            "identity",
            source_url,
            "Not applicable — no matching LEI",
            "No LEI was found for this name. Absence of an LEI is not evidence that the "
            "company does not exist and is not treated as negative financial evidence.",
        )], coverage="n/a", entity_match="No LEI", source_url=source_url)
    except Exception as exc:
        code = _error_code(exc)
        return _result(
            "gleif",
            [_unavailable_signal(
                "Legal Entity Identity",
                "🪪",
                "identity",
                source_url,
                "GLEIF could not be retrieved. Missing LEI data is not a negative financial signal.",
            )],
            error=code,
            error_code=code,
        )


async def collect_census(name: str, resolved=None) -> CollectorResult:
    """National Census industry context. Never treated as this company's own numbers."""
    source_url = "https://api.census.gov"
    try:
        from services.providers.census import lookup_census

        industry = getattr(resolved, "industry", None) if resolved is not None else None
        description = None
        summary = getattr(resolved, "wikipedia_summary", None) if resolved is not None else None
        if isinstance(summary, dict):
            description = summary.get("description") or summary.get("extract")
        lookup = await lookup_census(name, industry=industry, description=description)
        if lookup.status == "unavailable" and lookup.error_code == "NOT_CONFIGURED":
            return _result(
                "census",
                [_unavailable_signal(
                    "Industry Context",
                    "🏭",
                    "industry",
                    source_url,
                    "Census industry context is disabled until CENSUS_API_KEY is set on the backend. "
                    "Missing industry statistics are not company financial evidence.",
                )],
                error="NOT_CONFIGURED",
                error_code="NOT_CONFIGURED",
                optional=True,
                coverage="none",
                entity_match="Not configured",
                source_url=source_url,
                evidence_quality="none",
            )
        if lookup.status != "live" or lookup.selected is None:
            code = lookup.error_code
            if lookup.status == "not_applicable":
                return _result(
                    "census",
                    [_not_applicable_signal(
                        "Industry Context",
                        "🏭",
                        "industry",
                        source_url,
                        "Not applicable — no industry mapping",
                        "No NAICS industry could be inferred for this company. That is not a "
                        "company-specific financial observation.",
                    )],
                    coverage="n/a",
                    entity_match="No industry mapping",
                    source_url=source_url,
                )
            return _result(
                "census",
                [_unavailable_signal(
                    "Industry Context",
                    "🏭",
                    "industry",
                    source_url,
                    "Census industry statistics could not be retrieved.",
                )],
                error=code,
                error_code=code,
                optional=True,
                coverage="none",
                source_url=source_url,
            )
        ctx = lookup.selected
        growth = _pct(ctx.employment_growth)
        display = f"{ctx.label} (NAICS {ctx.naics}, {ctx.year})"
        if ctx.establishments is not None:
            display += f" · {ctx.establishments:,} U.S. establishments"
        insight = f"U.S. Census County Business Patterns for {ctx.label} (NAICS {ctx.naics}, {ctx.year})"
        if ctx.establishments is not None:
            insight += f" show {ctx.establishments:,} establishments"
        if ctx.employment is not None:
            insight += f" and {ctx.employment:,} employees"
        if ctx.annual_payroll is not None:
            insight += f", with annual payroll of ${ctx.annual_payroll:,} (thousands of dollars as published)"
        insight += (
            f". Employment change vs prior year: {growth}. "
            "This is national industry context for benchmarking only. It is not this company's "
            "own employment, payroll, sales, or financials and is excluded from PrivateScore."
        )
        return _result(
            "census",
            [_public_signal(
                name="Industry Context",
                icon="🏭",
                category="industry",
                display=display,
                status="live",
                source_url=ctx.source_url or source_url,
                insight=insight,
                extra={
                    "is_scored": False,
                    "is_simulated": False,
                    "evidence_scope": "industry",
                    **ctx.as_dict(),
                },
                evidence_quality="medium",
            )],
            coverage="industry",
            entity_match="Industry-level",
            source_url=ctx.source_url or source_url,
            evidence_quality="medium",
        )
    except Exception as exc:
        code = _error_code(exc)
        return _result(
            "census",
            [_unavailable_signal("Industry Context", "🏭", "industry", source_url)],
            error=code,
            error_code=code,
            optional=True,
            coverage="none",
            source_url=source_url,
        )


async def collect_all(identity: CompanyIdentity | str, resolved=None) -> dict:
    """Run public collectors and the licensed evidence client concurrently."""
    if isinstance(identity, str):
        identity = CompanyIdentity(legal_name=identity)
    company_name = identity.legal_name

    named = [
        ("sec", collect_sec_edgar(company_name, resolved)),
        ("wikipedia", collect_wikipedia(company_name, resolved)),
        ("news", collect_news_sentiment(company_name, resolved)),
        ("jobs", collect_job_postings(company_name, resolved)),
        ("usaspending", collect_usa_spending(company_name, resolved)),
        ("gleif", collect_gleif(company_name, resolved)),
        ("census", collect_census(company_name, resolved)),
    ]
    licensed_task = asyncio.create_task(collect_licensed_signals(identity))
    gathered = await asyncio.gather(*(task for _, task in named), return_exceptions=True)

    collector_results: list[CollectorResult] = []
    partial_failure = False
    public_signals: list[dict[str, Any]] = []
    for (source, _), item in zip(named, gathered):
        if isinstance(item, Exception):
            crashed = _crash_result(source, item)
            collector_results.append(crashed)
            public_signals.extend(crashed.signals)
            if not crashed.optional:
                partial_failure = True
            continue
        collector_results.append(item)
        public_signals.extend(item.signals)
        if item.error and not item.optional:
            partial_failure = True

    try:
        licensed, evidence_audit = await licensed_task
    except Exception as exc:
        licensed, evidence_audit = [], {
            "gateway_enabled": False,
            "error_code": _error_code(exc),
        }
    evidence_audit["partial_source_failure"] = partial_failure

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    # Public observations win over licensed placeholders for the same name.
    for signal in public_signals + licensed:
        name = signal.get("signal")
        if name not in seen:
            seen.add(name)
            out.append(signal)
    return {
        "signals": out,
        "evidence": evidence_audit,
        "collector_results": collector_results,
        "partial_failure": partial_failure,
    }

"""
PrivateLens Data Collectors v5
Public collectors return live, modelled, unavailable, or not_applicable results.
Licensed score inputs are supplied by the evidence gateway and transformed locally.
"""
from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

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

HEADERS = {"User-Agent": "PrivateLens/2.0 research@privatelens.io"}

# USASpending returns awards page by page. Anything derived from one page is a
# floor across the largest awards, not a lifetime total.
AWARD_PAGE_SIZE = 10
AWARD_SEARCH_START = "2022-01-01"
# Indeed's public result counter is capped before display; the cap must be shown
# as a lower bound rather than an exact posting count.
JOB_COUNT_CAP = 5000

# Re-exported so existing tests keep importing from this module.
_normalize_entity_name = canonical_key


@dataclass
class CollectorResult:
    source: str
    status: str
    signals: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_quality: str | None = None

    def as_source_card(self) -> dict[str, Any]:
        labels = {
            "sec": "SEC EDGAR",
            "wikipedia": "Wikipedia",
            "news": "DuckDuckGo / Hacker News",
            "jobs": "Indeed",
            "usaspending": "USASpending",
        }
        quality = self.evidence_quality
        if quality is None:
            if self.status == "live" and self.source in {"sec", "usaspending"}:
                quality = "high"
            elif self.status == "live":
                quality = "low"
            elif self.status == "modelled":
                quality = "modelled"
            elif self.status == "not_applicable":
                quality = "not_applicable"
            else:
                quality = "unavailable"
        return {
            "source": labels.get(self.source, self.source),
            "key": self.source,
            "status": self.status,
            "evidenceQuality": quality,
            "errorCode": self.error_code,
            "retrievedAt": self.retrieved_at,
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
) -> CollectorResult:
    statuses = [item.get("availability_status") or "unavailable" for item in signals]
    if any(status in {"live", "modelled"} and item.get("is_scored") for status, item in zip(statuses, signals)):
        overall = "live" if any(status == "live" for status in statuses) else "modelled"
    elif all(status == "not_applicable" for status in statuses):
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

async def collect_sec_edgar(name: str, resolved=None) -> CollectorResult:
    """SEC EDGAR full-text search — research context, never a risk score."""
    source_url = "https://efts.sec.gov"
    company_type = getattr(resolved, "company_type", "unknown") or "unknown"
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index"
            f"?q=%22{name.replace(' ', '+')}%22"
            f"&dateRange=custom&startdt={start}&enddt={end}"
        )
        async with httpx.AsyncClient(timeout=_http_timeout()) as client:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("hits", {}).get("total", {}) or {}
                hits = total.get("value", 0)
                capped = total.get("relation") == "gte"
                hit_label = f"{hits:,}+" if capped else f"{hits:,}"
                edgar_url = (
                    f"https://www.sec.gov/edgar/search/#/q=%22{quote(name)}%22"
                    f"&dateRange=custom&startdt={start}&enddt={end}"
                )
                private_or_empty = hits == 0 or company_type == "private"
                if private_or_empty:
                    return _result("sec", [_not_applicable_signal(
                        "SEC / Regulatory Filings",
                        "📋",
                        "legal",
                        edgar_url,
                        (
                            "Not applicable — private company, not an SEC filer"
                            if company_type == "private"
                            else "Not applicable — no SEC keyword matches"
                        ),
                        (
                            "This company is treated as private, so SEC keyword hits are not a filing record "
                            "for the company and are excluded from scoring."
                            if company_type == "private"
                            else "No SEC full-text matches were returned. That is not a negative observation "
                            "for a company that may not file with the SEC."
                        ),
                    )])
                return _result("sec", [_public_signal(
                    name="SEC / Regulatory Filings",
                    icon="📋",
                    category="legal",
                    display=f"{hit_label} unverified keyword match(es) in the past 2 years",
                    status="live",
                    source_url=edgar_url,
                    insight=(
                        f"SEC full-text search returned {hit_label} keyword match(es) between {start} and {end}, "
                        "shown as research context only. Keyword matches can refer to customers, competitors, "
                        "exhibits, or similarly named entities, so filing volume is not used as a risk signal."
                        + (" SEC caps this counter, so the true total is higher." if capped else "")
                    ),
                    extra={"is_scored": False, "is_simulated": False},
                    evidence_quality="high",
                )])
    except Exception as exc:
        return _result(
            "sec",
            [_unavailable_signal("SEC / Regulatory Filings", "📋", "legal", source_url)],
            error=_error_code(exc),
            error_code=_error_code(exc),
        )
    return _result(
        "sec",
        [_unavailable_signal("SEC / Regulatory Filings", "📋", "legal", source_url)],
        error="unavailable",
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
        category="digital",
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
            "digital",
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
    """Indeed job count via public search."""
    source_url = f"https://www.indeed.com/jobs?q=%22{quote(name)}%22"
    try:
        async with httpx.AsyncClient(timeout=_http_timeout(), follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.indeed.com/jobs?q=%22{name.replace(' ', '+')}%22&sort=date",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
        if resp.status_code == 200:
            count_match = re.search(r"(\d[\d,]*)\s+jobs?", resp.text, re.IGNORECASE)
            if count_match is None:
                return _result("jobs", [_unavailable_signal(
                    "Job Posting Velocity",
                    "💼",
                    "operational",
                    source_url,
                    "Indeed did not return a parsable job counter, so hiring was not scored.",
                )])
            parsed_count = int(count_match.group(1).replace(",", ""))
            raw_count = min(parsed_count, JOB_COUNT_CAP)
            capped = parsed_count > JOB_COUNT_CAP
            count_label = f"{raw_count:,}+" if capped else f"{raw_count:,}"
            if raw_count > 200:
                trend = "Very active hiring"
            elif raw_count > 50:
                trend = "Active hiring"
            elif raw_count > 10:
                trend = "Some hiring activity"
            elif raw_count > 0:
                trend = "Minimal hiring detected"
            else:
                trend = "No current postings reported"

            return _result("jobs", [_public_signal(
                name="Job Posting Velocity",
                icon="💼",
                category="operational",
                display=f"{count_label} active job posting(s) — {trend}",
                raw_score=_hiring_score(raw_count),
                status="live",
                evidence_quality="low",
                source_url=source_url,
                insight=(
                    f"{trend} ({count_label} postings reported by Indeed's public result counter). "
                    "Keyword search is not entity-resolved, so postings may belong to other employers. "
                    "Hiring activity is a supporting operational signal, not proof of financial strength. "
                    + ("The public counter is capped, so this is a lower bound." if capped else "")
                ),
            )])
    except Exception as exc:
        return _result(
            "jobs",
            [_unavailable_signal("Job Posting Velocity", "💼", "operational", source_url)],
            error=_error_code(exc),
            error_code=_error_code(exc),
        )
    return _result(
        "jobs",
        [_unavailable_signal("Job Posting Velocity", "💼", "operational", "https://www.indeed.com")],
        error="unavailable",
    )


async def collect_usa_spending(name: str, resolved=None) -> CollectorResult:
    """USASpending.gov — federal contract awards for an exact recipient name."""
    source_url = f"https://www.usaspending.gov/search/?query={name.replace(' ', '%20')}"
    try:
        async with httpx.AsyncClient(timeout=_http_timeout()) as client:
            resp = await client.post(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                json={
                    "filters": {
                        "recipient_search_text": [name],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": AWARD_SEARCH_START, "end_date": datetime.now().strftime("%Y-%m-%d")}],
                    },
                    "fields": ["Award Amount", "Recipient Name"],
                    "page": 1,
                    "limit": AWARD_PAGE_SIZE,
                    "sort": "Award Amount",
                    "order": "desc",
                },
                headers={**HEADERS, "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                requested = canonical_key(name)
                verified_results = [
                    item for item in results
                    if canonical_key(item.get("Recipient Name", "")) == requested
                ]
                total = sum(item.get("Award Amount", 0) or 0 for item in verified_results)
                count = len(verified_results)
                unverified_count = len(results) - count
                truncated = bool(data.get("page_metadata", {}).get("hasNext"))
                if count == 0:
                    return _result("usaspending", [_not_applicable_signal(
                        "Government Contract Awards",
                        "🏛️",
                        "financial",
                        source_url,
                        (
                            f"Not applicable — no exact-name match in the {AWARD_PAGE_SIZE} largest awards"
                            + (f"; {unverified_count} broader match(es) excluded" if unverified_count else "")
                        ),
                        "No award in this page matched the exact recipient name. That is not a failed "
                        "observation for a company that may not be a federal contractor.",
                    )])
                return _result("usaspending", [_public_signal(
                    name="Government Contract Awards",
                    icon="🏛️",
                    category="financial",
                    display=(
                        f"{count} of the {AWARD_PAGE_SIZE} largest awards match this exact name — "
                        f"${total:,.0f} across those awards"
                    ),
                    raw_score=_award_score(total),
                    status="live",
                    evidence_quality="medium",
                    source_url=source_url,
                    insight=(
                        f"USASpending.gov was queried for the {AWARD_PAGE_SIZE} largest awards since "
                        f"{AWARD_SEARCH_START}; {count} of them match this exact recipient name and total "
                        f"${total:,.0f}. This is a floor across those awards, not the company's total federal "
                        f"contract value{', and more awards exist beyond this page' if truncated else ''}."
                    ),
                )])
    except Exception as exc:
        return _result(
            "usaspending",
            [_unavailable_signal("Government Contract Awards", "🏛️", "financial", "https://www.usaspending.gov")],
            error=_error_code(exc),
            error_code=_error_code(exc),
        )
    return _result(
        "usaspending",
        [_unavailable_signal("Government Contract Awards", "🏛️", "financial", "https://www.usaspending.gov")],
        error="unavailable",
    )


FALLBACK_SIGNALS = {
    "sec": [("SEC / Regulatory Filings", "📋", "legal", "https://efts.sec.gov")],
    "wikipedia": [
        ("Brand Legitimacy & Web Presence", "🌐", "digital", "https://en.wikipedia.org"),
        ("Company Stability", "🏢", "operational", "https://en.wikipedia.org"),
    ],
    "news": [("News & Media Sentiment", "📰", "sentiment", "https://newsapi.org")],
    "jobs": [("Job Posting Velocity", "💼", "operational", "https://www.indeed.com")],
    "usaspending": [("Government Contract Awards", "🏛️", "financial", "https://www.usaspending.gov")],
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
    ]
    licensed_task = asyncio.create_task(collect_licensed_signals(identity))
    gathered = await asyncio.gather(*(task for _, task in named), return_exceptions=True)

    collector_results: list[CollectorResult] = []
    partial_failure = False
    public_signals: list[dict[str, Any]] = []
    for (source, _), item in zip(named, gathered):
        if isinstance(item, Exception):
            partial_failure = True
            crashed = _crash_result(source, item)
            collector_results.append(crashed)
            public_signals.extend(crashed.signals)
            continue
        collector_results.append(item)
        public_signals.extend(item.signals)
        if item.error:
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

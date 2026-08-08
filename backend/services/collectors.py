"""
PrivateLens Data Collectors v4
Real data sources: SEC EDGAR, Wikipedia, DuckDuckGo, Indeed, HackerNews, USASpending
Licensed score inputs are supplied by the evidence gateway and transformed locally.
"""
import httpx
import asyncio
import math
import re
from datetime import datetime, timedelta
from urllib.parse import quote
from core.config import get_settings
from services.evidence import CompanyIdentity
from services.licensed_data import collect_licensed_signals

settings = get_settings()

HEADERS = {"User-Agent": "PrivateLens/2.0 research@privatelens.io"}

# USASpending returns awards page by page. Anything derived from one page is a
# floor across the largest awards, not a lifetime total.
AWARD_PAGE_SIZE = 10
AWARD_SEARCH_START = "2022-01-01"
# Indeed's public result counter is capped before display; the cap must be shown
# as a lower bound rather than an exact posting count.
JOB_COUNT_CAP = 5000


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clamp(val: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, val))


# ── REAL COLLECTORS ────────────────────────────────────────────────────────────

async def collect_sec_edgar(name: str) -> dict:
    """SEC EDGAR full-text search — checks regulatory filings (real)."""
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index"
            f"?q=%22{name.replace(' ', '+')}%22"
            f"&dateRange=custom&startdt={start}&enddt={end}"
        )
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("hits", {}).get("total", {}) or {}
                hits = total.get("value", 0)
                # SEC full-text search caps the counter and reports relation "gte";
                # rendering that as an exact figure would overstate precision.
                capped = total.get("relation") == "gte"
                hit_label = f"{hits:,}+" if capped else f"{hits:,}"
                return {
                    "signal": "SEC / Regulatory Filings",
                    "icon": "📋",
                    "category": "legal",
                    "display": f"{hit_label} unverified keyword match(es) in the past 2 years",
                    "raw_score": None,
                    "is_simulated": False,
                    "is_scored": False,
                    # Link the same query and date window the count came from, so
                    # the displayed figure is reproducible by the reader.
                    "source_url": (
                        f"https://www.sec.gov/edgar/search/#/q=%22{quote(name)}%22"
                        f"&dateRange=custom&startdt={start}&enddt={end}"
                    ),
                    "insight": (
                        f"SEC full-text search returned {hit_label} keyword match(es) between {start} and {end}, "
                        "shown as research context only. Keyword matches can refer to customers, competitors, "
                        "exhibits, or similarly named entities, so filing volume is not used as a risk signal."
                        + (" SEC caps this counter, so the true total is higher." if capped else "")
                    ),
                }
    except Exception:
        pass
    return _unavailable_signal("SEC / Regulatory Filings", "📋", "legal", "https://efts.sec.gov")


ORGANISATION_HINTS = (
    "company", "corporation", "conglomerate", "business", "enterprise", "firm",
    "manufacturer", "retailer", "bank", "insurer", "airline", "startup",
    "subsidiary", "holding", "group", "brand", "organisation", "organization",
    "supplier", "operator", "provider", "chain", "publisher", "studio",
)


def _no_wikipedia_match(name: str, reason: str) -> dict:
    return {
        "signal": "Brand Legitimacy & Web Presence",
        "icon": "🌐",
        "category": "digital",
        "display": "No confident Wikipedia company match",
        "raw_score": None,
        "is_simulated": True,
        "is_scored": False,
        "availability_status": "unavailable",
        "source_url": "https://en.wikipedia.org/wiki/Special:Search?search=" + name.replace(" ", "+"),
        "insight": (
            f"No Wikipedia article was confidently resolved to this company ({reason}). "
            "Absence of an article is not evidence about the company, so no value was inferred."
        ),
    }


def _looks_like_organisation(summary: dict) -> bool:
    description = (summary.get("description") or "").lower()
    extract = (summary.get("extract") or "").lower()
    if any(hint in description for hint in ORGANISATION_HINTS):
        return True
    # Fall back to the opening clause of the article, which for organisations
    # almost always states the entity type ("... is an American ... company").
    return any(hint in extract[:400] for hint in ORGANISATION_HINTS)


async def _wikipedia_summary(client: httpx.AsyncClient, title: str) -> dict | None:
    resp = await client.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
        headers=HEADERS,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


async def collect_wikipedia(name: str) -> dict:
    """Resolve the company's Wikipedia article and report it as identity context.

    The article title is not assumed to equal the company name: a bare name like
    "Stripe" or "Apple" resolves to a disambiguation page or an unrelated topic,
    so candidates are verified to refer to the requested organisation before use.
    """
    requested = _normalize_entity_name(name)
    if not requested:
        return _no_wikipedia_match(name, "no searchable company name was provided")
    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            search = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search", "srsearch": f"{name} company",
                    "srlimit": 5, "format": "json",
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
                # A disambiguation page describes a word, not a company.
                if summary.get("type") == "disambiguation":
                    continue
                resolved_title = summary.get("title") or title
                resolved = _normalize_entity_name(resolved_title)
                # Require the article to be about the requested entity, allowing
                # only a legal-suffix difference ("Stripe" -> "Stripe, Inc.") or a
                # trailing qualifier ("Koch" -> "Koch Industries").
                if not (resolved == requested
                        or resolved.startswith(requested + " ")
                        or requested.startswith(resolved + " ")):
                    continue
                if not _looks_like_organisation(summary):
                    continue

                extract = summary.get("extract", "")
                words = len(extract.split())
                founded_match = re.search(r"(?:founded|established|incorporated)(?:\s+\w+){0,2}\s+in\s+(\d{4})",
                                          extract.lower())
                age_note = ""
                if founded_match:
                    year = int(founded_match.group(1))
                    if 1600 <= year <= datetime.now().year:
                        age_note = f" Founded {year} ({datetime.now().year - year} years ago)."
                return {
                    "signal": "Brand Legitimacy & Web Presence",
                    "icon": "🌐",
                    "category": "digital",
                    "display": f"Wikipedia article: {resolved_title}{age_note}",
                    "raw_score": None,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://en.wikipedia.org/wiki/{resolved_title.replace(' ', '_')}",
                    "matched_entity": resolved_title,
                    "insight": (
                        f"Matched the Wikipedia article \"{resolved_title}\""
                        f"{' — ' + summary['description'] if summary.get('description') else ''}."
                        f"{age_note} Article length ({words} words) reflects editorial coverage, not company "
                        "performance, so this is identity context only and is excluded from the score."
                    ),
                }
            return _no_wikipedia_match(name, "no candidate article resolved to this organisation")
    except Exception:
        pass
    return _unavailable_signal("Brand Legitimacy & Web Presence", "🌐", "digital", "https://en.wikipedia.org")


async def collect_news_sentiment(name: str) -> dict:
    """DuckDuckGo instant answers + HackerNews search for news sentiment (real)."""
    try:
        pos_words = {"growth", "profit", "revenue", "raises", "expands", "wins",
                     "award", "launch", "partnership", "record", "acquisition", "innovation",
                     "promotion", "dividend", "milestone", "breakthrough"}
        neg_words = {"lawsuit", "fraud", "bankrupt", "layoff", "scandal", "loss",
                     "investigation", "debt", "closure", "default", "breach", "fine",
                     "recall", "dispute", "settlement", "penalty", "downgrade"}

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
            ddg = await client.get(
                f"https://api.duckduckgo.com/?q={name.replace(' ', '+')}&format=json&no_html=1",
                headers=HEADERS
            )
            hn = await client.get(
                f"https://hn.algolia.com/api/v1/search?query={name.replace(' ', '%20')}&tags=story&hitsPerPage=10",
                headers=HEADERS
            )

        text = ""
        if ddg.status_code == 200:
            d = ddg.json()
            text += d.get("Abstract", "") + " "
            text += " ".join(t.get("Text", "") for t in d.get("RelatedTopics", [])[:8] if isinstance(t, dict))

        hn_hits = 0
        if hn.status_code == 200:
            hits = hn.json().get("hits", [])
            hn_hits = len(hits)
            text += " ".join(h.get("title", "") for h in hits)

        text = text.lower()
        pos = sum(1 for w in pos_words if w in text)
        neg = sum(1 for w in neg_words if w in text)
        total_signals = pos + neg

        if total_signals == 0:
            label = "Neutral / No signal"
        elif pos > neg * 1.5:
            label = "Positive"
        elif neg > pos * 1.5:
            label = "Negative"
        else:
            label = "Mixed"

        return {
            "signal": "News & Media Sentiment",
            "icon": "📰",
            "category": "sentiment",
            "display": f"{label} — {pos} positive, {neg} negative signals, {hn_hits} HN mentions",
            # Keyword counts are not entity-resolved, so no numeric value is published.
            "raw_score": None,
            "is_simulated": False,
            "is_scored": False,
            "source_url": f"https://hn.algolia.com/api/v1/search?query={name.replace(' ', '%20')}&tags=story",
            "insight": (
                f"Keyword context across DuckDuckGo and HackerNews: {pos} positive indicator(s), "
                f"{neg} negative indicator(s), and {hn_hits} Hacker News mention(s). "
                "Entity resolution and sentiment are not strong enough for this signal to affect the score."
            ),
        }
    except Exception:
        pass
    return _unavailable_signal("News & Media Sentiment", "📰", "sentiment", "https://newsapi.org")


async def collect_job_postings(name: str) -> dict:
    """Indeed job count via public search (real)."""
    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                f"https://www.indeed.com/jobs?q=%22{name.replace(' ', '+')}%22&sort=date",
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                }
            )
        if resp.status_code == 200:
            text = resp.text
            # Parse job count from page
            count_match = re.search(r'(\d[\d,]*)\s+jobs?', text, re.IGNORECASE)
            if count_match is None:
                # No parsable counter: the page layout changed or the request was
                # blocked. Reporting "0 postings" here would invent an observation.
                return _unavailable_signal(
                    "Job Posting Velocity", "💼", "operational",
                    f"https://www.indeed.com/jobs?q=%22{quote(name)}%22",
                )
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
            else:
                trend = "Minimal hiring detected"

            return {
                "signal": "Job Posting Velocity",
                "icon": "💼",
                "category": "operational",
                "display": f"{count_label} active job posting(s) — {trend}",
                "raw_score": None,
                "is_simulated": False,
                "is_scored": False,
                "source_url": f"https://www.indeed.com/jobs?q=%22{quote(name)}%22",
                "insight": (
                    f"{trend} ({count_label} postings reported by Indeed's public result counter). "
                    "Keyword search is not entity-resolved, so postings may belong to other employers "
                    "and this signal does not affect the financial-health score."
                ),
            }
    except Exception:
        pass
    return _unavailable_signal("Job Posting Velocity", "💼", "operational", "https://www.indeed.com")


async def collect_usa_spending(name: str) -> dict:
    """USASpending.gov — real federal contract data (real, free API)."""
    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.post(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                json={
                    "filters": {
                        "recipient_search_text": [name],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "time_period": [{"start_date": AWARD_SEARCH_START, "end_date": datetime.now().strftime("%Y-%m-%d")}]
                    },
                    "fields": ["Award Amount", "Recipient Name"],
                    "page": 1,
                    "limit": AWARD_PAGE_SIZE,
                    "sort": "Award Amount",
                    "order": "desc"
                },
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                requested = _normalize_entity_name(name)
                verified_results = [
                    item for item in results
                    if _normalize_entity_name(item.get("Recipient Name", "")) == requested
                ]
                total = sum(r.get("Award Amount", 0) or 0 for r in verified_results)
                count = len(verified_results)
                unverified_count = len(results) - count
                # This request returns only the largest AWARD_PAGE_SIZE awards. The
                # sum is therefore a floor across those awards, never a lifetime
                # total, and must not be presented as one.
                truncated = bool(data.get("page_metadata", {}).get("hasNext"))

                return {
                    "signal": "Government Contract Awards",
                    "icon": "🏛️",
                    "category": "financial",
                    "display": (
                        f"{count} of the {AWARD_PAGE_SIZE} largest awards match this exact name — "
                        f"${total:,.0f} across those awards"
                        if count > 0 else
                        f"No exact-name match in the {AWARD_PAGE_SIZE} largest awards; "
                        f"{unverified_count} broader match(es) excluded"
                    ),
                    "raw_score": None,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://www.usaspending.gov/search/?query={name.replace(' ', '%20')}",
                    "insight": (
                        f"USASpending.gov was queried for the {AWARD_PAGE_SIZE} largest awards since "
                        f"{AWARD_SEARCH_START}; {count} of them match this exact recipient name and total "
                        f"${total:,.0f}. This is a floor across those awards, not the company's total federal "
                        f"contract value{', and more awards exist beyond this page' if truncated else ''}. "
                        "Shown as revenue context only."
                        if count > 0 else
                        "No award in this page matched the exact recipient name. Broader recipient-name matches "
                        "are shown as context only and excluded from scoring."
                    ),
                }
    except Exception:
        pass
    return _unavailable_signal("Government Contract Awards", "🏛️", "financial", "https://www.usaspending.gov")


# ── UNAVAILABLE FALLBACKS ──────────────────────────────────────────────────────

def _unavailable_signal(signal: str, icon: str, category: str, source_url: str) -> dict:
    return {
        "signal": signal,
        "icon": icon,
        "category": category,
        "display": "Verified data unavailable — not scored",
        # No value is invented for an unavailable source, so there is no number
        # a consumer could mistake for an observation.
        "raw_score": None,
        "is_simulated": True,
        "is_scored": False,
        "availability_status": "unavailable",
        "source_url": source_url,
        "insight": (
            "No verified data was available for this signal during the current run. "
            "It is excluded from the evidence score."
        ),
    }


def _normalize_entity_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "company", "co"}
    words = [word for word in value.split() if word not in suffixes]
    return " ".join(words)


# ── AGGREGATE ──────────────────────────────────────────────────────────────────

async def collect_all(identity: CompanyIdentity | str) -> dict:
    """Run public context collectors and the licensed evidence client concurrently."""
    if isinstance(identity, str):
        identity = CompanyIdentity(legal_name=identity)
    company_name = identity.legal_name

    real = await asyncio.gather(
        collect_sec_edgar(company_name),
        collect_wikipedia(company_name),
        collect_news_sentiment(company_name),
        collect_job_postings(company_name),
        collect_usa_spending(company_name),
        return_exceptions=False
    )

    licensed, evidence_audit = await collect_licensed_signals(identity)

    # Deduplicate by signal name
    seen, out = set(), []
    for s in licensed + list(real):
        if s["signal"] not in seen:
            seen.add(s["signal"])
            out.append(s)
    return {"signals": out, "evidence": evidence_audit}

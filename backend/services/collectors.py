"""
PrivateLens Data Collectors v3
Real data sources: SEC EDGAR, Wikipedia, DuckDuckGo, Indeed, HackerNews, USASpending
Unavailable without licensed sources: UCC, court records, open banking, reviews, social, supply chain
"""
import httpx
import asyncio
import math
import re
from datetime import datetime, timedelta
from core.config import get_settings
from services.licensed_data import apply_licensed_overrides

settings = get_settings()

HEADERS = {"User-Agent": "PrivateLens/2.0 research@privatelens.io"}


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
                hits = data.get("hits", {}).get("total", {}).get("value", 0)
                return {
                    "signal": "SEC / Regulatory Filings",
                    "icon": "📋",
                    "category": "legal",
                    "display": f"{hits:,} unverified keyword match(es) in the past 2 years",
                    "raw_score": 50,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://efts.sec.gov/LATEST/search-index?q=%22{name.replace(' ', '+')}%22",
                    "insight": (
                        "SEC full-text results are shown as research context only. Keyword matches can refer to customers, "
                        "competitors, exhibits, or similarly named entities, so filing volume is not used as a risk signal."
                    ),
                }
    except Exception:
        pass
    return _sim_generic(name, "sec_edgar", "SEC / Regulatory Filings", "📋", "legal",
                        "Simulated — real data from SEC EDGAR (available with funding).",
                        "https://efts.sec.gov")


async def collect_wikipedia(name: str) -> dict:
    """Wikipedia API — brand legitimacy, establishment, public profile (real)."""
    try:
        slug = name.replace(" ", "_")
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
                headers=HEADERS
            )
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                words = len(extract.split())
                # Also extract founding year hint if present
                founded_match = re.search(r'founded in (\d{4})', extract.lower())
                age_bonus = 0
                age_note = ""
                if founded_match:
                    age = datetime.now().year - int(founded_match.group(1))
                    age_bonus = min(15, age // 3)
                    age_note = f" Founded {founded_match.group(1)} ({age} years ago)."

                score = _clamp(45 + words // 8 + age_bonus) if words > 0 else 28
                return {
                    "signal": "Brand Legitimacy & Web Presence",
                    "icon": "🌐",
                    "category": "digital",
                    "display": f"Wikipedia page found ({words} words){age_note}",
                    "raw_score": score,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://en.wikipedia.org/wiki/{slug}",
                    "insight": f"Established public profile with a {words}-word Wikipedia article.{age_note} Shown as identity and web-presence context only.",
                }
            else:
                return {
                    "signal": "Brand Legitimacy & Web Presence",
                    "icon": "🌐",
                    "category": "digital",
                    "display": "No Wikipedia presence found",
                    "raw_score": 30,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://en.wikipedia.org/wiki/{slug}",
                    "insight": "No Wikipedia page detected. May indicate a smaller, newer, or deliberately low-profile company.",
                }
    except Exception:
        pass
    return _sim_generic(name, "brand", "Brand Legitimacy & Web Presence", "🌐", "digital",
                        "Simulated — real data from Wikipedia API.", "https://en.wikipedia.org")


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
            score = 58
            label = "Neutral / No signal"
        elif pos > neg * 1.5:
            score = _clamp(68 + pos * 4)
            label = "Positive"
        elif neg > pos * 1.5:
            score = _clamp(52 - neg * 6)
            label = "Negative"
        else:
            score = 55
            label = "Mixed"

        return {
            "signal": "News & Media Sentiment",
            "icon": "📰",
            "category": "sentiment",
            "display": f"{label} — {pos} positive, {neg} negative signals, {hn_hits} HN mentions",
            "raw_score": score,
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
    return _sim_generic(name, "news", "News & Media Sentiment", "📰", "sentiment",
                        "Simulated — real data requires NewsAPI/GDELT (available with funding).",
                        "https://newsapi.org")


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
            raw_count = int(count_match.group(1).replace(",", "")) if count_match else 0
            raw_count = min(raw_count, 5000)  # cap outliers

            score = _clamp(35 + math.log10(raw_count + 1) * 20)
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
                "display": f"{raw_count:,} active job posting(s) — {trend}",
                "raw_score": score,
                "is_simulated": False,
                "is_scored": False,
                "source_url": f"https://www.indeed.com/jobs?q=%22{name.replace(' ', '+')}%22",
                "insight": f"{trend} ({raw_count:,} postings). Public job-search results are not entity-resolved enough to affect the financial-health score.",
            }
    except Exception:
        pass
    return _sim_generic(name, "jobs", "Job Posting Velocity", "💼", "operational",
                        "Simulated — real data requires Indeed/LinkedIn API (available with funding).",
                        "https://www.indeed.com")


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
                        "time_period": [{"start_date": "2022-01-01", "end_date": datetime.now().strftime("%Y-%m-%d")}]
                    },
                    "fields": ["Award Amount", "Recipient Name"],
                    "page": 1,
                    "limit": 10,
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
                score = _clamp(55 + min(count * 4, 30) + min(math.log10(total + 1) * 2, 15)) if count > 0 else 50

                return {
                    "signal": "Government Contract Awards",
                    "icon": "🏛️",
                    "category": "financial",
                    "display": (
                        f"{count} exact-name contract(s) — ${total:,.0f} total value"
                        if count > 0 else
                        f"No exact-name contracts; {unverified_count} broader match(es) excluded"
                    ),
                    "raw_score": score,
                    "is_simulated": False,
                    "is_scored": False,
                    "source_url": f"https://www.usaspending.gov/search/?query={name.replace(' ', '%20')}",
                    "insight": (
                        f"Found {count} exact-name federal contract(s) totaling ${total:,.0f}. Shown as revenue-context evidence only."
                        if count > 0 else
                        "Broader recipient-name matches are shown as context only and excluded from scoring."
                    ),
                }
    except Exception:
        pass
    return _sim_generic(name, "govt", "Government Contract Awards", "🏛️", "financial",
                        "Simulated — real data from USASpending.gov API (available with funding).",
                        "https://www.usaspending.gov")


# ── SIMULATED COLLECTORS ───────────────────────────────────────────────────────

def _sim_generic(name, seed_key, signal, icon, category, insight, source_url,
                 lo=35, hi=85) -> dict:
    return {
        "signal": signal,
        "icon": icon,
        "category": category,
        "display": "Verified data unavailable — not scored",
        "raw_score": 50,
        "is_simulated": True,
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


def sim_ucc(name: str) -> dict:
    return _sim_generic(name, "ucc", "UCC Filings & Lien Activity", "⚖️", "financial", "", "https://www.ucc.gov")


def sim_court(name: str) -> dict:
    return _sim_generic(name, "court", "Court Records & Litigation", "🏛️", "legal", "", "https://www.courtlistener.com")


def sim_open_banking(name: str) -> dict:
    return _sim_generic(name, "banking", "Open Banking Payment Flows", "🏦", "financial", "", "https://www.consumerfinance.gov/section1033/")


def sim_reviews(name: str) -> dict:
    return _sim_generic(name, "reviews", "Employee & Customer Reviews", "⭐", "sentiment", "", "https://www.glassdoor.com")


def sim_web_traffic(name: str) -> dict:
    return _sim_generic(name, "traffic", "Web Traffic Trends", "📈", "digital", "", "https://www.similarweb.com")


def sim_social(name: str) -> dict:
    return _sim_generic(name, "social", "Social Media Activity", "📱", "digital", "", "https://twitter.com")


def sim_supply_chain(name: str) -> dict:
    return _sim_generic(name, "supply", "Supply Chain & Vendor Signals", "🔗", "operational", "", "https://www.riskmethods.net")


def sim_payment_behavior(name: str) -> dict:
    return _sim_generic(name, "payment", "B2B Payment Behavior", "💳", "financial", "", "https://www.dnb.com")


def sim_insider_sentiment(name: str) -> dict:
    return _sim_generic(name, "insider", "Insider & Employee Sentiment", "🧠", "sentiment", "", "https://www.glassdoor.com")


# ── AGGREGATE ──────────────────────────────────────────────────────────────────

async def collect_all(company_name: str) -> list[dict]:
    """Run all collectors concurrently. Returns list of signal dicts."""
    real = await asyncio.gather(
        collect_sec_edgar(company_name),
        collect_wikipedia(company_name),
        collect_news_sentiment(company_name),
        collect_job_postings(company_name),
        collect_usa_spending(company_name),
        return_exceptions=False
    )

    simulated = [
        sim_ucc(company_name),
        sim_court(company_name),
        sim_open_banking(company_name),
        sim_reviews(company_name),
        sim_web_traffic(company_name),
        sim_social(company_name),
        sim_supply_chain(company_name),
        sim_payment_behavior(company_name),
        sim_insider_sentiment(company_name),
    ]
    simulated = await apply_licensed_overrides(company_name, simulated)

    # Deduplicate by signal name
    seen, out = set(), []
    for s in list(real) + simulated:
        if s["signal"] not in seen:
            seen.add(s["signal"])
            out.append(s)
    return out

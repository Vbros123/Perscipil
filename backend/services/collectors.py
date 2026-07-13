"""
PrivateLens Data Collectors v2
Real data sources: SEC EDGAR, Wikipedia, DuckDuckGo, Indeed, HackerNews, USASpending
Simulated (clearly labeled): UCC, court records, open banking, reviews, social, supply chain
"""
import httpx
import asyncio
import random
import math
import re
from datetime import datetime, timedelta
from core.config import get_settings
from services.licensed_data import apply_licensed_overrides

settings = get_settings()

HEADERS = {"User-Agent": "PrivateLens/2.0 research@privatelens.io"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _seed(name: str, signal: str) -> random.Random:
    """Deterministic per-company-per-signal seed so simulated values are stable."""
    r = random.Random()
    # Add day-of-year so simulated scores shift slightly each day (realistic drift)
    day_offset = datetime.now().timetuple().tm_yday
    r.seed(hash(name.lower().strip() + signal + str(day_offset)) % (2**32))
    return r


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
                # More filings for a private company = unusual, slight risk flag
                score = _clamp(80 - hits * 5) if hits > 0 else 72
                return {
                    "signal": "SEC / Regulatory Filings",
                    "icon": "📋",
                    "category": "legal",
                    "display": f"{hits} filing(s) in past 2 years",
                    "raw_score": score,
                    "is_simulated": False,
                    "source_url": f"https://efts.sec.gov/LATEST/search-index?q=%22{name.replace(' ', '+')}%22",
                    "insight": (
                        f"Found {hits} SEC filing(s). Private companies rarely file — elevated count may signal regulatory scrutiny."
                        if hits > 0 else
                        "No SEC filings found — typical for private companies with no public obligations."
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
                    "source_url": f"https://en.wikipedia.org/wiki/{slug}",
                    "insight": f"Established public profile with {words}-word Wikipedia article.{age_note} Stronger profile = higher brand legitimacy score.",
                }
            else:
                return {
                    "signal": "Brand Legitimacy & Web Presence",
                    "icon": "🌐",
                    "category": "digital",
                    "display": "No Wikipedia presence found",
                    "raw_score": 30,
                    "is_simulated": False,
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
            "source_url": f"https://hn.algolia.com/api/v1/search?query={name.replace(' ', '%20')}&tags=story",
            "insight": f"NLP analysis across DuckDuckGo and HackerNews: {pos} positive indicator(s), {neg} negative indicator(s). {hn_hits} Hacker News story mention(s).",
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
                "source_url": f"https://www.indeed.com/jobs?q=%22{name.replace(' ', '+')}%22",
                "insight": f"{trend} ({raw_count:,} postings). High hiring velocity is a strong leading indicator of growth and financial health.",
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
                total = sum(r.get("Award Amount", 0) or 0 for r in results)
                count = len(results)
                score = _clamp(45 + min(count * 4, 40) + min(math.log10(total + 1) * 3, 15)) if count > 0 else 40

                return {
                    "signal": "Government Contract Awards",
                    "icon": "🏛️",
                    "category": "financial",
                    "display": f"{count} contract(s) — ${total:,.0f} total value" if count > 0 else "No federal contracts found",
                    "raw_score": score,
                    "is_simulated": False,
                    "source_url": f"https://www.usaspending.gov/search/?query={name.replace(' ', '%20')}",
                    "insight": (
                        f"Found {count} federal contract(s) totaling ${total:,.0f}. Government contracts signal revenue diversification and credibility."
                        if count > 0 else
                        "No federal contracts found — common for most private companies."
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
    r = _seed(name, seed_key)
    score = _clamp(r.uniform(lo, hi))
    return {
        "signal": signal,
        "icon": icon,
        "category": category,
        "display": f"Estimated score: {score:.0f}/100 (simulated)",
        "raw_score": score,
        "is_simulated": True,
        "source_url": source_url,
        "insight": insight,
    }


def sim_ucc(name: str) -> dict:
    r = _seed(name, "ucc")
    filings = r.randint(0, 9)
    score = _clamp(100 - filings * 11)
    risk = "Low debt risk" if filings < 2 else ("Moderate lien activity" if filings < 5 else "Elevated lien exposure")
    return {
        "signal": "UCC Filings & Lien Activity",
        "icon": "⚖️",
        "category": "financial",
        "display": f"~{filings} estimated UCC filing(s) — {risk}",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.ucc.gov",
        "insight": f"Simulated — {risk}. UCC filings reveal real-time debt and collateral obligations. Real data requires state-level API access (available with funding).",
    }


def sim_court(name: str) -> dict:
    r = _seed(name, "court")
    cases = r.randint(0, 6)
    score = _clamp(100 - cases * 14)
    status = "Clean legal record" if cases == 0 else f"{cases} estimated litigation event(s)"
    return {
        "signal": "Court Records & Litigation",
        "icon": "🏛️",
        "category": "legal",
        "display": status,
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.courtlistener.com",
        "insight": f"Simulated — {status.lower()}. Real court record data requires PACER or CourtListener API (available with funding).",
    }


def sim_open_banking(name: str) -> dict:
    r = _seed(name, "banking_v2")
    score = _clamp(r.uniform(32, 94))
    dso = int(r.uniform(15, 85))
    health = "Strong" if score > 72 else ("Moderate" if score > 48 else "Stressed")
    return {
        "signal": "Open Banking Payment Flows",
        "icon": "🏦",
        "category": "financial",
        "display": f"Cash flow health: {score:.0f}/100 — {health} (est. DSO: {dso} days)",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.consumerfinance.gov/section1033/",
        "insight": f"Simulated — {health} cash flow signal (estimated DSO {dso} days). Real data unlocked by Section 1033 open banking API (available with funding).",
    }


def sim_reviews(name: str) -> dict:
    r = _seed(name, "reviews_v2")
    rating = round(r.uniform(2.4, 4.9), 1)
    count = r.randint(12, 4800)
    score = _clamp((rating / 5) * 100)
    label = "Excellent" if rating >= 4.3 else ("Good" if rating >= 3.6 else ("Mixed" if rating >= 3.0 else "Poor"))
    return {
        "signal": "Employee & Customer Reviews",
        "icon": "⭐",
        "category": "sentiment",
        "display": f"{rating}/5.0 avg — {label} (~{count:,} reviews estimated)",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.glassdoor.com",
        "insight": f"Simulated — {label} internal sentiment ({rating}/5.0 across ~{count:,} estimated reviews). Real data requires Glassdoor/G2 API (available with funding).",
    }


def sim_web_traffic(name: str) -> dict:
    r = _seed(name, "traffic_v2")
    monthly = r.randint(800, 3500000)
    trend_val = r.uniform(-18, 32)
    trend = f"+{trend_val:.1f}% MoM" if trend_val > 0 else f"{trend_val:.1f}% MoM"
    score = _clamp(math.log10(monthly + 1) * 14)
    return {
        "signal": "Web Traffic Trends",
        "icon": "📈",
        "category": "digital",
        "display": f"~{monthly:,} est. monthly visits — {trend}",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.similarweb.com",
        "insight": f"Simulated — ~{monthly:,} estimated monthly visits, trending {trend}. Real traffic data requires SimilarWeb API (available with funding).",
    }


def sim_social(name: str) -> dict:
    r = _seed(name, "social_v2")
    followers = r.randint(200, 800000)
    engagement = round(r.uniform(0.4, 7.2), 1)
    score = _clamp(math.log10(followers + 1) * 14 + engagement * 2)
    return {
        "signal": "Social Media Activity",
        "icon": "📱",
        "category": "digital",
        "display": f"~{followers:,} est. followers — {engagement}% engagement rate",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://twitter.com",
        "insight": f"Simulated — {engagement}% engagement rate across estimated {followers:,} followers. Real data requires social platform API (available with funding).",
    }


def sim_supply_chain(name: str) -> dict:
    r = _seed(name, "supply_v2")
    score = _clamp(r.uniform(38, 94))
    risk_level = "Low" if score > 72 else ("Medium" if score > 50 else "High")
    vendor_count = r.randint(5, 200)
    return {
        "signal": "Supply Chain & Vendor Signals",
        "icon": "🔗",
        "category": "operational",
        "display": f"Supply chain risk: {risk_level} — ~{vendor_count} est. vendors",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.riskmethods.net",
        "insight": f"Simulated — {risk_level} supply chain risk across ~{vendor_count} estimated vendor relationships. Real data requires supply chain API (available with funding).",
    }


def sim_payment_behavior(name: str) -> dict:
    r = _seed(name, "payment_v2")
    dso = r.randint(12, 95)
    score = _clamp(100 - dso * 0.9)
    health = "Excellent" if dso < 28 else ("Good" if dso < 45 else ("Fair" if dso < 65 else "Poor"))
    return {
        "signal": "B2B Payment Behavior",
        "icon": "💳",
        "category": "financial",
        "display": f"Est. DSO: {dso} days — {health} payment discipline",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.dnb.com",
        "insight": f"Simulated — {health} payment behavior (DSO {dso} days). Lower DSO = faster collections = healthier cash flow. Real data from D&B Paydex (available with funding).",
    }


def sim_insider_sentiment(name: str) -> dict:
    r = _seed(name, "insider_v2")
    score = _clamp(r.uniform(30, 92))
    retention = round(r.uniform(55, 98), 1)
    ceo_approval = round(r.uniform(40, 98), 0)
    mood = "Positive" if score > 70 else ("Neutral" if score > 50 else "Negative")
    return {
        "signal": "Insider & Employee Sentiment",
        "icon": "🧠",
        "category": "sentiment",
        "display": f"Est. retention: {retention}% — CEO approval: {ceo_approval:.0f}% — {mood}",
        "raw_score": score,
        "is_simulated": True,
        "source_url": "https://www.glassdoor.com",
        "insight": f"Simulated — {mood} insider sentiment. Est. {retention}% retention and {ceo_approval:.0f}% CEO approval. Real data requires Glassdoor API (available with funding).",
    }


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

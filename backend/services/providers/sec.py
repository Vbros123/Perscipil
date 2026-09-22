"""SEC EDGAR public filings and XBRL facts. No API key.

Official host: https://data.sec.gov
CIK map: https://www.sec.gov/files/company_tickers.json
Submissions: https://data.sec.gov/submissions/CIK##########.json
Company facts: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

Every request sends a descriptive User-Agent. Absence of an SEC filing is not
negative evidence and is never treated as a credit-risk signal.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from core.provider_budget import HOOKS

from core.config import get_settings
from services.resolver import canonical_key, names_match

logger = logging.getLogger("privatelens.sec")
settings = get_settings()

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_HEADERS = {
    "User-Agent": get_settings().PUBLIC_DATA_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}
DATA_SEC_HEADERS = {
    "User-Agent": get_settings().PUBLIC_DATA_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}
NON_OPERATING = ("etf", "trust", "fund", "reit", "warrant", "preferred", "depositary")
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)
ASSET_TAGS = ("Assets",)
LIABILITY_TAGS = ("Liabilities",)
CASH_TAGS = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsAndShortTermInvestments",
)
EQUITY_TAGS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
NET_INCOME_TAGS = ("NetIncomeLoss",)
OPERATING_INCOME_TAGS = ("OperatingIncomeLoss",)
OPERATING_CASH_TAGS = ("NetCashProvidedByUsedInOperatingActivities",)

_TICKER_CACHE: dict[str, Any] = {"fetched_at": 0.0, "rows": []}
_TICKER_TTL = 6 * 60 * 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_timeout(read: float | None = None) -> httpx.Timeout:
    budget = max(2.0, float(read or settings.HTTP_TIMEOUT))
    return httpx.Timeout(connect=min(3.0, budget), read=budget, write=min(5.0, budget), pool=3.0)


def error_code(exc: BaseException) -> str:
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "TIMEOUT"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status == 429:
            return "RATE_LIMIT"
        if status in {401, 403}:
            return "BLOCKED"
        return "HTTP_ERROR"
    if isinstance(exc, (ValueError, KeyError, TypeError, AttributeError)):
        return "MALFORMED_RESPONSE"
    if "Proxy" in type(exc).__name__ or "ConnectError" in type(exc).__name__:
        return "HTTP_ERROR"
    name = type(exc).__name__.upper()
    if "TIMEOUT" in name:
        return "TIMEOUT"
    return name[:32]


def pad_cik(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not digits:
        raise ValueError("missing CIK")
    return digits.zfill(10)


def _is_operating_title(title: str) -> bool:
    lowered = (title or "").lower()
    return not any(token in lowered for token in NON_OPERATING)


def rank_sec_match(query: str, title: str, ticker: str = "") -> int:
    score = 0
    q_key = canonical_key(query)
    t_key = canonical_key(title)
    if not q_key or not t_key:
        return 0
    if q_key == t_key:
        score += 70
    elif names_match(query, title):
        score += 55
    elif t_key.startswith(q_key + " ") or q_key.startswith(t_key + " "):
        score += 18
    else:
        return 0
    if _is_operating_title(title):
        score += 15
    else:
        score -= 25
    if ticker and canonical_key(ticker) == q_key:
        score += 8
    return max(0, min(100, score))


def select_sec_match(query: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        title = str(row.get("title") or "")
        ticker = str(row.get("ticker") or "")
        score = rank_sec_match(query, title, ticker)
        if score >= 55:
            ranked.append((score, row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0
    if best_score < 70 and second and best_score - second < 15:
        return None
    if not _is_operating_title(str(best.get("title") or "")) and best_score < 80:
        return None
    return {**best, "match_score": best_score}


def period_kind(row: dict[str, Any] | None) -> str:
    if not row:
        return "unknown"
    form = str(row.get("form") or "")
    fp = str(row.get("fp") or "")
    if fp == "FY" or form.startswith("10-K") or form in {"20-F", "40-F"}:
        return "annual"
    if form.startswith("10-Q") or fp.startswith("Q"):
        return "quarterly"
    return "unknown"


def fact_record(item: dict[str, Any] | None, unit: str = "USD") -> dict[str, Any] | None:
    if not item or item.get("val") is None:
        return None
    try:
        value = float(item["val"])
    except (TypeError, ValueError):
        return None
    return {
        "value": value,
        "unit": unit,
        "period": period_kind(item),
        "fiscalYear": item.get("fy"),
        "fiscalPeriod": item.get("fp"),
        "periodEnd": item.get("end"),
        "filed": item.get("filed"),
        "form": item.get("form"),
        "tag": item.get("tag"),
        "source": "SEC EDGAR XBRL",
    }


def _latest_fact(concept: dict[str, Any] | None) -> dict[str, Any] | None:
    """Latest annual (FY / 10-K / 20-F) USD fact. Quarterly points are ignored."""
    if not isinstance(concept, dict):
        return None
    units = concept.get("units") or {}
    points: list[dict[str, Any]] = []
    for unit, rows in units.items():
        if unit not in {"USD", "USD/shares"} and not str(unit).upper().startswith("USD"):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("val") is None:
                continue
            if period_kind(row) != "annual":
                continue
            points.append({**row, "unit": unit})
    if not points:
        return None
    return max(points, key=lambda row: (row.get("fy") or 0, str(row.get("end") or ""), str(row.get("filed") or "")))


def _fact_value(facts: dict[str, Any], tags: tuple[str, ...]) -> dict[str, Any] | None:
    """Latest annual fact across candidate tags.

    Issuers change revenue tags over time. Taking the first tag that has any
    annual point would mix a stale FY2022 revenue series with a FY2026 10-K.
    """
    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    ifrs = (facts.get("facts") or {}).get("ifrs-full") or {}
    chosen: dict[str, Any] | None = None
    chosen_key: tuple[Any, ...] = ()
    for tag in tags:
        latest = _latest_fact(us_gaap.get(tag) or ifrs.get(tag))
        if latest is None:
            continue
        key = (latest.get("fy") or 0, str(latest.get("end") or ""), str(latest.get("filed") or ""))
        if chosen is None or key > chosen_key:
            chosen = {"tag": tag, **latest}
            chosen_key = key
    return chosen


def _prior_annual(concept: dict[str, Any] | None, current: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(concept, dict) or not current:
        return None
    current_fy = current.get("fy")
    units = concept.get("units") or {}
    candidates: list[dict[str, Any]] = []
    for rows in units.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or row.get("val") is None:
                continue
            if row.get("fp") != "FY" and not str(row.get("form") or "").startswith("10-K"):
                continue
            if current_fy and row.get("fy") == current_fy - 1:
                candidates.append(row)
    if not candidates:
        return None
    chosen = max(candidates, key=lambda row: str(row.get("end") or ""))
    return {**chosen, "tag": current.get("tag")}


def extract_financials(facts: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(facts, dict) or not facts.get("facts"):
        raise ValueError("malformed company facts")
    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    revenue = _fact_value(facts, REVENUE_TAGS)
    prior = None
    if revenue:
        prior = _prior_annual(us_gaap.get(revenue["tag"]), revenue)
    assets = _fact_value(facts, ASSET_TAGS)
    liabilities = _fact_value(facts, LIABILITY_TAGS)
    cash = _fact_value(facts, CASH_TAGS)
    equity = _fact_value(facts, EQUITY_TAGS)
    net_income = _fact_value(facts, NET_INCOME_TAGS)
    operating_income = _fact_value(facts, OPERATING_INCOME_TAGS)
    operating_cash = _fact_value(facts, OPERATING_CASH_TAGS)

    def _num(item: dict[str, Any] | None) -> float | None:
        if not item:
            return None
        try:
            return float(item["val"])
        except (TypeError, ValueError, KeyError):
            return None

    revenue_val = _num(revenue)
    prior_val = _num(prior)
    assets_val = _num(assets)
    liabilities_val = _num(liabilities)
    cash_val = _num(cash)
    equity_val = _num(equity)
    net_income_val = _num(net_income)
    operating_income_val = _num(operating_income)
    growth = None
    same_annual_revenue = (
        revenue
        and prior
        and period_kind(revenue) == "annual"
        and period_kind(prior) == "annual"
        and revenue.get("tag") == (prior.get("tag") or revenue.get("tag"))
    )
    if same_annual_revenue and revenue_val and prior_val and prior_val != 0:
        growth = (revenue_val - prior_val) / abs(prior_val)

    def _same_annual(*items: dict[str, Any] | None) -> bool:
        present = [item for item in items if item]
        if len(present) < 2:
            return False
        years = {item.get("fy") for item in present}
        return years != {None} and len(years) == 1 and all(period_kind(item) == "annual" for item in present)

    net_margin = (
        net_income_val / revenue_val
        if revenue_val and net_income_val is not None and _same_annual(revenue, net_income)
        else None
    )
    operating_margin = (
        operating_income_val / revenue_val
        if revenue_val and operating_income_val is not None and _same_annual(revenue, operating_income)
        else None
    )
    debt_to_equity = (
        liabilities_val / equity_val
        if liabilities_val is not None and equity_val not in {None, 0} and _same_annual(liabilities, equity)
        else None
    )
    records = {
        "revenue": fact_record(revenue),
        "priorRevenue": fact_record(prior),
        "assets": fact_record(assets),
        "liabilities": fact_record(liabilities),
        "cash": fact_record(cash),
        "equity": fact_record(equity),
        "netIncome": fact_record(net_income),
        "operatingIncome": fact_record(operating_income),
        "operatingCashFlow": fact_record(operating_cash),
    }
    headline = max(
        [item for item in (revenue, assets, net_income, operating_income) if item],
        key=lambda item: (item.get("fy") or 0, str(item.get("end") or "")),
        default=None,
    )
    return {
        "revenue": revenue_val,
        "revenueFy": revenue.get("fy") if revenue else None,
        "revenueGrowth": growth,
        "assets": assets_val,
        "liabilities": liabilities_val,
        "cash": cash_val,
        "equity": equity_val,
        "netIncome": net_income_val,
        "operatingIncome": operating_income_val,
        "operatingCashFlow": _num(operating_cash),
        "netMargin": net_margin,
        "operatingMargin": operating_margin,
        "debtToEquity": debt_to_equity,
        "period": "annual",
        "periodEnd": (headline or {}).get("end"),
        "form": (headline or {}).get("form"),
        "facts": {key: value for key, value in records.items() if value},
    }


def score_sec_financials(metrics: dict[str, Any]) -> float | None:
    """Conservative polarity from reported facts. Presence of a filing is not a 90."""
    if not any(metrics.get(key) is not None for key in ("revenue", "assets", "netIncome", "equity")):
        return None
    score = 52.0
    net_income = metrics.get("netIncome")
    if net_income is not None:
        score += 10.0 if net_income > 0 else -14.0
    margin = metrics.get("operatingMargin")
    if margin is not None:
        if margin >= 0.15:
            score += 8.0
        elif margin >= 0.05:
            score += 4.0
        elif margin < 0:
            score -= 8.0
    growth = metrics.get("revenueGrowth")
    if growth is not None:
        if growth >= 0.10:
            score += 6.0
        elif growth <= -0.10:
            score -= 8.0
    leverage = metrics.get("debtToEquity")
    if leverage is not None:
        if leverage < 1:
            score += 6.0
        elif leverage > 3:
            score -= 10.0
    cash = metrics.get("cash")
    liabilities = metrics.get("liabilities")
    if cash is not None and liabilities not in {None, 0} and cash / abs(liabilities) >= 0.20:
        score += 5.0
    return max(18.0, min(86.0, score))


def parse_submissions(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("cik"):
        raise ValueError("malformed submissions")
    recent = (payload.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    history = []
    for form, filed, accession in zip(forms, dates, accessions):
        history.append({"form": form, "filed": filed, "accession": accession})
        if len(history) >= 12:
            break
    return {
        "cik": pad_cik(payload.get("cik")),
        "name": payload.get("name"),
        "tickers": payload.get("tickers") or [],
        "exchanges": payload.get("exchanges") or [],
        "sic": payload.get("sic"),
        "sicDescription": payload.get("sicDescription"),
        "entityType": payload.get("entityType"),
        "filings": history,
        "recentFormCount": len(forms),
    }


@dataclass
class SecEntity:
    cik: str
    ticker: str | None = None
    title: str | None = None
    match_score: int = 0
    submissions: dict[str, Any] | None = None
    financials: dict[str, Any] | None = None
    source: str = "SEC EDGAR"
    source_url: str | None = None
    retrieved_at: str = field(default_factory=_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cik": self.cik,
            "ticker": self.ticker,
            "title": self.title,
            "matchScore": self.match_score,
            "submissions": self.submissions,
            "financials": self.financials,
            "source": self.source,
            "sourceUrl": self.source_url or f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={self.cik}",
            "retrievedAt": self.retrieved_at,
        }


@dataclass
class SecLookup:
    selected: SecEntity | None = None
    status: str = "unavailable"
    error_code: str | None = None
    retrieved_at: str = field(default_factory=_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.as_dict() if self.selected else None,
            "status": self.status,
            "errorCode": self.error_code,
            "retrievedAt": self.retrieved_at,
        }


class SecProvider:
    def configured(self) -> bool:
        return True

    async def _ticker_rows(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        now = time.time()
        if _TICKER_CACHE["rows"] and now - _TICKER_CACHE["fetched_at"] < _TICKER_TTL:
            return _TICKER_CACHE["rows"]
        resp = await client.get(SEC_TICKERS_URL, headers=SEC_HEADERS)
        if resp.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError("ticker map failed", request=resp.request, response=resp)
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ValueError("malformed ticker map")
        rows = [item for item in payload.values() if isinstance(item, dict) and item.get("cik_str") is not None]
        if not rows:
            raise ValueError("empty ticker map")
        _TICKER_CACHE["rows"] = rows
        _TICKER_CACHE["fetched_at"] = now
        return rows

    async def resolve_cik(self, name: str, aliases: list[str] | None = None) -> SecLookup:
        queries = [item for item in [name, *(aliases or [])] if item]
        try:
            async with httpx.AsyncClient(event_hooks=HOOKS, timeout=_http_timeout()) as client:
                rows = await self._ticker_rows(client)
            best: dict[str, Any] | None = None
            for query in queries:
                match = select_sec_match(query, rows)
                if match and (best is None or match.get("match_score", 0) > best.get("match_score", 0)):
                    best = match
            if best is None:
                return SecLookup(status="not_applicable", error_code="NO_CIK")
            entity = SecEntity(
                cik=pad_cik(best.get("cik_str")),
                ticker=best.get("ticker"),
                title=best.get("title"),
                match_score=int(best.get("match_score") or 0),
            )
            return SecLookup(selected=entity, status="resolved")
        except Exception as exc:
            logger.warning("[SEC] CIK lookup failed query=%r error=%s", name, type(exc).__name__)
            return SecLookup(status="unavailable", error_code=error_code(exc))

    async def lookup(self, name: str, aliases: list[str] | None = None, cik: str | None = None) -> SecLookup:
        try:
            selected = None
            if cik:
                try:
                    selected = SecEntity(cik=pad_cik(cik), title=name, match_score=100)
                except ValueError:
                    selected = None
            if selected is None:
                resolved = await self.resolve_cik(name, aliases)
                if resolved.selected is None:
                    return resolved
                selected = resolved.selected
            async with httpx.AsyncClient(event_hooks=HOOKS, timeout=_http_timeout(read=max(12.0, float(settings.HTTP_TIMEOUT)))) as client:
                submissions_resp = await client.get(
                    SEC_SUBMISSIONS_URL.format(cik=selected.cik),
                    headers=DATA_SEC_HEADERS,
                )
                if submissions_resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate limited", request=submissions_resp.request, response=submissions_resp)
                if submissions_resp.status_code >= 400:
                    raise httpx.HTTPStatusError("submissions failed", request=submissions_resp.request, response=submissions_resp)
                selected.submissions = parse_submissions(submissions_resp.json())
                selected.title = selected.submissions.get("name") or selected.title
                selected.ticker = (selected.submissions.get("tickers") or [selected.ticker])[0]
                facts_resp = await client.get(
                    SEC_FACTS_URL.format(cik=selected.cik),
                    headers=DATA_SEC_HEADERS,
                )
                if facts_resp.status_code == 429:
                    raise httpx.HTTPStatusError("rate limited", request=facts_resp.request, response=facts_resp)
                if facts_resp.status_code == 200:
                    selected.financials = extract_financials(facts_resp.json())
                elif facts_resp.status_code != 404:
                    raise httpx.HTTPStatusError("company facts failed", request=facts_resp.request, response=facts_resp)
            selected.source_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={selected.cik}"
            return SecLookup(selected=selected, status="live")
        except Exception as exc:
            logger.warning("[SEC] lookup failed query=%r error=%s", name, type(exc).__name__)
            return SecLookup(selected=selected if "selected" in locals() else None, status="unavailable", error_code=error_code(exc))


_provider = SecProvider()


def get_sec_provider() -> SecProvider:
    return _provider


async def lookup_sec(name: str, aliases: list[str] | None = None, cik: str | None = None) -> SecLookup:
    return await _provider.lookup(name, aliases=aliases, cik=cik)


async def lookup_sec_cik(name: str, aliases: list[str] | None = None) -> SecLookup:
    return await _provider.resolve_cik(name, aliases=aliases)

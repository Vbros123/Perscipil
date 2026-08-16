"""US Census industry context. Optional free API key.

Official host: https://api.census.gov
Primary dataset: County Business Patterns (national NAICS totals).

Industry-level statistics are never treated as a company's own revenue,
employment, or financials. Missing CENSUS_API_KEY disables the provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from core.config import get_settings

logger = logging.getLogger("privatelens.census")
settings = get_settings()

CENSUS_CBP = "https://api.census.gov/data/{year}/cbp"
CBP_YEARS = (2023, 2022, 2021)
INDUSTRY_NAICS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("food", "agriculture", "agribusiness", "grain", "commodity", "cargill", "farm"), "311", "Food Manufacturing"),
    (("semiconductor", "gpu", "chip", "nvidia", "graphics processor"), "3344", "Semiconductor and Other Electronic Component Manufacturing"),
    (("computer", "iphone", "smartphone", "consumer electronics", "apple"), "3341", "Computer and Peripheral Equipment Manufacturing"),
    (("software", "cloud", "operating system", "microsoft", "saas"), "5112", "Software Publishers"),
    (("artificial intelligence", "openai", "ai research", "machine learning"), "5417", "Scientific Research and Development Services"),
    (("payment", "fintech", "stripe", "payments"), "5223", "Activities Related to Credit Intermediation"),
    (("search", "advertising", "internet"), "5191", "Other Information Services"),
    (("retail", "ecommerce", "e-commerce"), "44", "Retail Trade"),
    (("bank", "banking", "financial services"), "5221", "Depository Credit Intermediation"),
    (("energy", "oil", "gas", "petroleum"), "211", "Oil and Gas Extraction"),
    (("airline", "aviation"), "481", "Air Transportation"),
    (("automotive", "automobile", "vehicle"), "3361", "Motor Vehicle Manufacturing"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_timeout() -> httpx.Timeout:
    budget = max(2.0, float(settings.HTTP_TIMEOUT))
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
    name = type(exc).__name__.upper()
    if "TIMEOUT" in name:
        return "TIMEOUT"
    return name[:32]


def infer_naics(name: str, industry: str | None = None, description: str | None = None) -> dict[str, str] | None:
    blob = " ".join(item for item in (name, industry, description) if item).lower()
    if not blob.strip():
        return None
    for keywords, code, label in INDUSTRY_NAICS:
        if any(keyword in blob for keyword in keywords):
            return {"naics": code, "label": label}
    return None


def parse_cbp_table(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[0], list):
        raise ValueError("malformed census table")
    header = [str(item) for item in payload[0]]
    row = payload[1]
    if not isinstance(row, list) or len(row) != len(header):
        raise ValueError("malformed census row")
    mapped = dict(zip(header, row))

    def _int(key: str) -> int | None:
        raw = mapped.get(key)
        if raw in {None, "", "null"}:
            return None
        try:
            return int(str(raw).replace(",", ""))
        except ValueError:
            return None

    return {
        "naics": mapped.get("NAICS2017") or mapped.get("NAICS2022"),
        "label": mapped.get("NAICS2017_LABEL") or mapped.get("NAICS2022_LABEL"),
        "establishments": _int("ESTAB"),
        "employment": _int("EMP"),
        "annualPayroll": _int("PAYANN"),
        "geography": mapped.get("NAME") or "United States",
    }


@dataclass
class CensusContext:
    naics: str
    label: str
    year: int
    establishments: int | None = None
    employment: int | None = None
    annual_payroll: int | None = None
    prior_year: int | None = None
    employment_growth: float | None = None
    establishment_growth: float | None = None
    source: str = "US Census Bureau"
    source_url: str | None = None
    retrieved_at: str = field(default_factory=_now)
    scope: str = "industry"

    def as_dict(self) -> dict[str, Any]:
        return {
            "naics": self.naics,
            "label": self.label,
            "year": self.year,
            "establishments": self.establishments,
            "employment": self.employment,
            "annualPayroll": self.annual_payroll,
            "priorYear": self.prior_year,
            "employmentGrowth": self.employment_growth,
            "establishmentGrowth": self.establishment_growth,
            "source": self.source,
            "sourceUrl": self.source_url,
            "retrievedAt": self.retrieved_at,
            "scope": self.scope,
            "note": "Industry-level Census statistics. Not this company's own employment, payroll, or revenue.",
        }


@dataclass
class CensusLookup:
    selected: CensusContext | None = None
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


class CensusProvider:
    def configured(self) -> bool:
        return bool((settings.CENSUS_API_KEY or "").strip())

    async def _cbp(self, client: httpx.AsyncClient, year: int, naics: str, key: str) -> dict[str, Any] | None:
        resp = await client.get(
            CENSUS_CBP.format(year=year),
            params={
                "get": "NAME,NAICS2017,NAICS2017_LABEL,ESTAB,EMP,PAYANN",
                "for": "us:*",
                "NAICS2017": naics,
                "key": key,
            },
        )
        if resp.status_code == 204:
            return None
        if resp.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError("census failed", request=resp.request, response=resp)
        return parse_cbp_table(resp.json())

    async def lookup(self, name: str, industry: str | None = None, description: str | None = None) -> CensusLookup:
        key = (settings.CENSUS_API_KEY or "").strip()
        if not key:
            return CensusLookup(status="unavailable", error_code="NOT_CONFIGURED")
        mapped = infer_naics(name, industry, description)
        if mapped is None:
            return CensusLookup(status="not_applicable", error_code="NO_INDUSTRY")
        try:
            async with httpx.AsyncClient(timeout=_http_timeout()) as client:
                current = None
                year = CBP_YEARS[0]
                for candidate in CBP_YEARS:
                    current = await self._cbp(client, candidate, mapped["naics"], key)
                    if current:
                        year = candidate
                        break
                if current is None:
                    return CensusLookup(status="not_applicable", error_code="NO_INDUSTRY")
                prior = None
                prior_year = year - 1
                try:
                    prior = await self._cbp(client, prior_year, mapped["naics"], key)
                except Exception:
                    prior = None
            emp_growth = None
            est_growth = None
            if prior and current.get("employment") and prior.get("employment"):
                emp_growth = (current["employment"] - prior["employment"]) / abs(prior["employment"])
            if prior and current.get("establishments") and prior.get("establishments"):
                est_growth = (current["establishments"] - prior["establishments"]) / abs(prior["establishments"])
            context = CensusContext(
                naics=str(current.get("naics") or mapped["naics"]),
                label=str(current.get("label") or mapped["label"]),
                year=year,
                establishments=current.get("establishments"),
                employment=current.get("employment"),
                annual_payroll=current.get("annualPayroll"),
                prior_year=prior_year if prior else None,
                employment_growth=emp_growth,
                establishment_growth=est_growth,
                source_url=f"https://api.census.gov/data/{year}/cbp.html",
            )
            return CensusLookup(selected=context, status="live")
        except Exception as exc:
            logger.warning("[Census] lookup failed query=%r error=%s", name, type(exc).__name__)
            return CensusLookup(status="unavailable", error_code=error_code(exc))


_provider = CensusProvider()


def get_census_provider() -> CensusProvider:
    return _provider


async def lookup_census(name: str, industry: str | None = None, description: str | None = None) -> CensusLookup:
    return await _provider.lookup(name, industry=industry, description=description)

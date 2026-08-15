"""Canonical company identity resolution, independent of any one data source."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config import get_settings

settings = get_settings()
HEADERS = {"User-Agent": "PrivateLens/2.0 research@privatelens.io"}

LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "company", "co", "plc", "lp", "llp", "pllc", "pc", "na",
})
LEADING_STOPWORDS = frozenset({"the", "a", "an"})
ORGANISATION_HINTS = (
    "company", "corporation", "conglomerate", "business", "enterprise", "firm",
    "manufacturer", "retailer", "bank", "insurer", "airline", "startup",
    "subsidiary", "holding", "group", "brand", "organisation", "organization",
    "supplier", "operator", "provider", "chain", "publisher", "studio",
)
PUBLIC_HINTS = (
    "publicly traded", "public company", "listed on", "nyse", "nasdaq",
    "stock exchange", "ticker symbol",
)
PRIVATE_HINTS = (
    "privately held", "private company", "family-owned", "closely held",
    "privately owned",
)


def canonical_key(name: str) -> str:
    """Suffix-aware identity key so Cargill / Cargill Inc / CARGILL collapse."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    words = [word for word in cleaned.split() if word]
    while words and words[0] in LEADING_STOPWORDS:
        words.pop(0)
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def names_match(left: str, right: str) -> bool:
    a, b = canonical_key(left), canonical_key(right)
    if not a or not b:
        return False
    return a == b or a.startswith(b + " ") or b.startswith(a + " ")


def _looks_like_organisation(summary: dict) -> bool:
    description = (summary.get("description") or "").lower()
    extract = (summary.get("extract") or "").lower()
    if any(hint in description for hint in ORGANISATION_HINTS):
        return True
    return any(hint in extract[:400] for hint in ORGANISATION_HINTS)


def _company_type_from_text(text: str) -> str:
    lowered = text.lower()
    if any(hint in lowered for hint in PUBLIC_HINTS):
        return "public"
    if any(hint in lowered for hint in PRIVATE_HINTS):
        return "private"
    return "unknown"


def _founded_year(extract: str) -> int | None:
    match = re.search(
        r"(?:founded|established|incorporated)(?:\s+\w+){0,2}\s+in\s+(\d{4})",
        extract.lower(),
    )
    if not match:
        return None
    year = int(match.group(1))
    if 1600 <= year <= datetime.now().year:
        return year
    return None


def _domain_from_summary(summary: dict) -> str | None:
    extract = summary.get("extract") or ""
    match = re.search(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+\.[a-z]{2,})(?:/[^\s]*)?", extract, re.I)
    if not match:
        return None
    host = match.group(1).lower()
    if host.endswith(("wikipedia.org", "wikimedia.org")):
        return None
    return host


@dataclass
class CompanyCandidate:
    title: str
    description: str = ""
    extract: str = ""
    url: str = ""
    canonical_key: str = ""
    company_type: str = "unknown"
    founded_year: int | None = None
    domain: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.title,
            "canonicalName": self.title,
            "description": self.description,
            "companyType": self.company_type,
            "domain": self.domain,
            "url": self.url,
        }


@dataclass
class ResolvedCompany:
    query_name: str
    canonical_key: str
    canonical_name: str
    legal_name: str
    aliases: list[str] = field(default_factory=list)
    domain: str | None = None
    industry: str | None = None
    headquarters: str | None = None
    company_type: str = "unknown"
    identifiers: dict[str, str] = field(default_factory=dict)
    resolution_confidence: int = 0
    candidates: list[CompanyCandidate] = field(default_factory=list)
    wikipedia_title: str | None = None
    wikipedia_summary: dict[str, Any] | None = None
    founded_year: int | None = None
    needs_disambiguation: bool = False
    limited_identification: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.legal_name,
            "canonicalName": self.canonical_name,
            "domain": self.domain,
            "industry": self.industry,
            "companyType": self.company_type,
            "location": self.headquarters,
            "aliases": self.aliases,
            "identifiers": self.identifiers,
            "resolutionConfidence": self.resolution_confidence,
        }


async def _wikipedia_summary(client: httpx.AsyncClient, title: str) -> dict | None:
    resp = await client.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
        headers=HEADERS,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def _candidate_from_summary(summary: dict) -> CompanyCandidate | None:
    if summary.get("type") == "disambiguation":
        return None
    if not _looks_like_organisation(summary):
        return None
    title = summary.get("title") or ""
    extract = summary.get("extract") or ""
    description = summary.get("description") or ""
    url = (summary.get("content_urls") or {}).get("desktop", {}).get("page") or (
        f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else ""
    )
    return CompanyCandidate(
        title=title,
        description=description,
        extract=extract,
        url=url,
        canonical_key=canonical_key(title),
        company_type=_company_type_from_text(f"{description} {extract}"),
        founded_year=_founded_year(extract),
        domain=_domain_from_summary(summary),
    )


async def resolve_company(name: str) -> ResolvedCompany:
    """Resolve a typed name to a canonical company before collectors run."""
    key = canonical_key(name)
    base = ResolvedCompany(
        query_name=name,
        canonical_key=key or name.strip().lower(),
        canonical_name=name.strip(),
        legal_name=name.strip(),
        aliases=[],
        limited_identification=True,
        resolution_confidence=10,
    )
    if not key:
        return base

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            search = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": f"{name} company",
                    "srlimit": 8,
                    "format": "json",
                },
                headers=HEADERS,
            )
            titles: list[str] = [name]
            if search.status_code == 200:
                for hit in search.json().get("query", {}).get("search", []):
                    title = hit.get("title")
                    if title and title not in titles:
                        titles.append(title)

            matched: list[tuple[CompanyCandidate, dict]] = []
            seen_keys: set[str] = set()
            for title in titles:
                summary = await _wikipedia_summary(client, title)
                if not summary:
                    continue
                candidate = _candidate_from_summary(summary)
                if candidate is None:
                    continue
                if not names_match(name, candidate.title):
                    continue
                if candidate.canonical_key in seen_keys:
                    continue
                seen_keys.add(candidate.canonical_key)
                matched.append((candidate, summary))

            if not matched:
                return base

            distinct_orgs = {item[0].canonical_key for item in matched}
            if len(distinct_orgs) > 1:
                # Several different organisations share this name. Ask the user.
                return ResolvedCompany(
                    query_name=name,
                    canonical_key=key,
                    canonical_name=name.strip(),
                    legal_name=name.strip(),
                    aliases=[],
                    resolution_confidence=40,
                    candidates=[item[0] for item in matched],
                    needs_disambiguation=True,
                    limited_identification=True,
                )

            chosen, summary = matched[0]
            aliases = [name.strip(), chosen.title]
            aliases = list(dict.fromkeys(item for item in aliases if item))
            industry = chosen.description or None
            return ResolvedCompany(
                query_name=name,
                canonical_key=chosen.canonical_key or key,
                canonical_name=chosen.title,
                legal_name=chosen.title,
                aliases=aliases,
                domain=chosen.domain,
                industry=industry,
                headquarters=None,
                company_type=chosen.company_type,
                identifiers={"wikipedia": chosen.title},
                resolution_confidence=88 if chosen.founded_year else 76,
                candidates=[chosen],
                wikipedia_title=chosen.title,
                wikipedia_summary=summary,
                founded_year=chosen.founded_year,
                needs_disambiguation=False,
                limited_identification=False,
            )
    except Exception:
        return base

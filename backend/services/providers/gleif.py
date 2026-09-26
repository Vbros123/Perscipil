"""GLEIF public LEI lookup. No API key. Identity evidence only — never a credit score.

Official API: https://api.gleif.org/api/v1
Documentation: https://documenter.getpostman.com/view/7679680/SVYrrxuU

Absence of an LEI is not evidence that a company does not exist and is never
treated as negative financial evidence.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from core.provider_budget import HOOKS, ProviderClient

from core.config import get_settings

logger = logging.getLogger("privatelens.gleif")
settings = get_settings()

GLEIF_API = "https://api.gleif.org/api/v1"
GLEIF_ACCEPT = "application/vnd.api+json"
HEADERS = {
    "User-Agent": get_settings().PUBLIC_DATA_USER_AGENT,
    "Accept": GLEIF_ACCEPT,
}
LEI_RE = re.compile(r"^[A-Z0-9]{20}$")
NON_OPERATING = (
    "pension", "trust", "fund", "foundation", "master trust",
    "employee benefit", "401k", "401(k)",
)
NAME_EXPANSIONS = ("INCORPORATED", "INC.", "CORPORATION", "CORP.", "LLC", "LTD")


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
    if isinstance(exc, (ValueError, KeyError, TypeError, AttributeError)):
        return "MALFORMED"
    name = type(exc).__name__.upper()
    if "TIMEOUT" in name:
        return "TIMEOUT"
    return name[:32]


def _text(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return str(name).strip() if name else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _format_address(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    parts = [str(item).strip() for item in (payload.get("addressLines") or []) if item]
    for key in ("city", "region", "postalCode", "country"):
        item = payload.get(key)
        if item:
            parts.append(str(item).strip())
    return ", ".join(parts) if parts else None


@dataclass
class GleifEntity:
    lei: str
    legal_name: str
    other_names: list[str] = field(default_factory=list)
    entity_status: str | None = None
    registration_status: str | None = None
    jurisdiction: str | None = None
    country: str | None = None
    legal_form: str | None = None
    registered_address: str | None = None
    headquarters_address: str | None = None
    parents: list[dict[str, str]] = field(default_factory=list)
    source: str = "GLEIF"
    source_url: str | None = None
    retrieved_at: str = field(default_factory=_now)
    match_score: int = 0

    def as_identity_dict(self) -> dict[str, Any]:
        return {
            "lei": self.lei,
            "legalName": self.legal_name,
            "otherNames": self.other_names,
            "entityStatus": self.entity_status,
            "registrationStatus": self.registration_status,
            "jurisdiction": self.jurisdiction,
            "legalForm": self.legal_form,
            "registeredAddress": self.registered_address,
            "headquartersAddress": self.headquarters_address,
            "parents": self.parents,
            "source": self.source,
            "sourceUrl": self.source_url or f"{GLEIF_API}/lei-records/{self.lei}",
            "retrievedAt": self.retrieved_at,
        }


@dataclass
class GleifLookup:
    selected: GleifEntity | None = None
    candidates: list[GleifEntity] = field(default_factory=list)
    status: str = "unavailable"
    error_code: str | None = None
    retrieved_at: str = field(default_factory=_now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errorCode": self.error_code,
            "selected": self.selected.as_identity_dict() if self.selected else None,
            "candidates": [item.as_identity_dict() for item in self.candidates[:8]],
            "retrievedAt": self.retrieved_at,
            "source": "GLEIF",
        }


def parse_lei_record(payload: Any) -> GleifEntity | None:
    if not isinstance(payload, dict):
        raise ValueError("GLEIF record must be an object")
    attributes = payload.get("attributes") or {}
    if not isinstance(attributes, dict):
        raise ValueError("GLEIF attributes missing")
    lei = str(attributes.get("lei") or payload.get("id") or "").strip().upper()
    if not LEI_RE.match(lei):
        raise ValueError("GLEIF record has no valid LEI")
    entity = attributes.get("entity") or {}
    if not isinstance(entity, dict):
        raise ValueError("GLEIF entity missing")
    legal_name = _text(entity.get("legalName"))
    if not legal_name:
        raise ValueError("GLEIF legal name missing")
    other_names: list[str] = []
    for bucket in (entity.get("otherNames"), entity.get("transliteratedOtherNames")):
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            label = _text(item)
            if label and label not in other_names:
                other_names.append(label)
    legal_address = entity.get("legalAddress") if isinstance(entity.get("legalAddress"), dict) else {}
    hq = entity.get("headquartersAddress") if isinstance(entity.get("headquartersAddress"), dict) else {}
    legal_form = entity.get("legalForm") if isinstance(entity.get("legalForm"), dict) else {}
    form_label = _text(legal_form.get("other")) or legal_form.get("id")
    registration = attributes.get("registration") if isinstance(attributes.get("registration"), dict) else {}
    return GleifEntity(
        lei=lei,
        legal_name=legal_name,
        other_names=other_names,
        entity_status=_text(entity.get("status")),
        registration_status=_text(registration.get("status")),
        jurisdiction=_text(entity.get("jurisdiction")),
        country=_text(legal_address.get("country")) or _text(hq.get("country")),
        legal_form=str(form_label).strip() if form_label else None,
        registered_address=_format_address(legal_address),
        headquarters_address=_format_address(hq),
        source_url=f"{GLEIF_API}/lei-records/{lei}",
    )


def rank_gleif_match(query: str, entity: GleifEntity, country_code: str | None = None) -> int:
    from services.resolver import canonical_key, names_match

    names = [entity.legal_name, *entity.other_names]
    score = 0
    if any(names_match(query, name) for name in names):
        score += 80
    elif any(canonical_key(query) and canonical_key(query) == canonical_key(name) for name in names):
        score += 80
    elif any(canonical_key(query) and canonical_key(name).startswith(canonical_key(query) + " ") for name in names):
        score += 45
    elif any(canonical_key(query) and canonical_key(query) in canonical_key(name).split() for name in names):
        score += 20
    else:
        return 0
    if (entity.entity_status or "").upper() == "ACTIVE":
        score += 8
    if (entity.registration_status or "").upper() == "ISSUED":
        score += 8
    if country_code and entity.country and entity.country.upper() == country_code.upper():
        score += 16
    official = entity.legal_name.upper()
    if any(token in official for token in ("INCORPORATED", "CORPORATION")):
        score += 10
    lowered = entity.legal_name.lower()
    if any(token in lowered for token in NON_OPERATING):
        score -= 40
    extra = max(0, len(canonical_key(entity.legal_name).split()) - len(canonical_key(query).split()))
    score -= min(18, extra * 3)
    return max(0, min(100, score))


def select_gleif_match(
    query: str,
    entities: list[GleifEntity],
    country_code: str | None = None,
) -> GleifLookup:
    ranked: list[GleifEntity] = []
    seen: set[str] = set()
    for entity in entities:
        if entity.lei in seen:
            continue
        seen.add(entity.lei)
        entity.match_score = rank_gleif_match(query, entity, country_code)
        if entity.match_score <= 0:
            continue
        ranked.append(entity)
    ranked.sort(key=lambda item: (-item.match_score, len(item.legal_name), item.lei))
    if not ranked:
        return GleifLookup(status="unavailable", candidates=[], error_code=None)
    country_pool = [
        item for item in ranked
        if item.match_score >= 70
        and country_code
        and item.country
        and item.country.upper() == country_code.upper()
    ]
    pool = country_pool or [item for item in ranked if item.match_score >= 70]
    if not pool:
        return GleifLookup(selected=None, candidates=ranked, status="ambiguous")
    best = pool[0]
    second = pool[1].match_score if len(pool) > 1 else 0
    auto = best.match_score >= 70 and (len(pool) == 1 or best.match_score - second >= 12)
    return GleifLookup(
        selected=best if auto else None,
        candidates=ranked,
        status="live" if auto else "ambiguous",
    )


class GleifProvider:
    """Free public GLEIF client. configured() is always true; no credentials exist."""

    key = "gleif"
    name = "GLEIF"
    track = "public"
    quality = "high"

    def configured(self) -> bool:
        return True

    async def lookup(self, query: str, country_code: str | None = None) -> GleifLookup:
        name = (query or "").strip()
        if len(name) < 2:
            return GleifLookup(status="unavailable")
        try:
            async with ProviderClient(event_hooks=HOOKS, timeout=_http_timeout(), headers=HEADERS, follow_redirects=True) as client:
                if LEI_RE.match(name.upper()):
                    entity = await self._fetch_lei(client, name.upper())
                    if entity is None:
                        return GleifLookup(status="unavailable")
                    entity.match_score = 100
                    parents = await self._parents(client, entity.lei)
                    entity.parents = parents
                    return GleifLookup(selected=entity, candidates=[entity], status="live")

                records = await self._search_records(client, name, country_code)
                result = select_gleif_match(name, records, country_code)
                if result.selected is not None:
                    result.selected.parents = await self._parents(client, result.selected.lei)
                return result
        except Exception as exc:
            logger.warning("gleif.lookup_failed query=%r error_type=%s", name, type(exc).__name__)
            return GleifLookup(status="unavailable", error_code=_error_code(exc))

    async def _search_records(
        self,
        client: httpx.AsyncClient,
        name: str,
        country_code: str | None,
    ) -> list[GleifEntity]:
        found: list[GleifEntity] = []
        queries = [name]
        from services.resolver import names_match

        for suffix in NAME_EXPANSIONS:
            queries.append(f"{name} {suffix}")
        for term in queries[:4]:
            found.extend(await self._legal_name_search(client, term))
        strong = [
            item for item in found
            if names_match(name, item.legal_name)
            and (not country_code or not item.country or item.country.upper() == country_code.upper())
        ]
        if not strong:
            found.extend(await self._fuzzy_records(client, name))
        return found

    async def _legal_name_search(self, client: httpx.AsyncClient, term: str) -> list[GleifEntity]:
        response = await client.get(
            f"{GLEIF_API}/lei-records",
            params={"filter[entity.legalName]": term, "page[size]": 10},
        )
        if response.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
        if response.status_code >= 400:
            return []
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if rows is None:
            raise ValueError("GLEIF legal-name search missing data")
        if not isinstance(rows, list):
            raise ValueError("GLEIF legal-name search data is not a list")
        out: list[GleifEntity] = []
        for item in rows:
            try:
                parsed = parse_lei_record(item)
            except ValueError:
                continue
            if parsed:
                out.append(parsed)
        return out

    async def _fuzzy_records(self, client: httpx.AsyncClient, term: str) -> list[GleifEntity]:
        response = await client.get(
            f"{GLEIF_API}/fuzzycompletions",
            params={"field": "entity.legalName", "q": term[:255]},
        )
        if response.status_code >= 400:
            return []
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("GLEIF fuzzycompletions data is not a list")
        leis: list[str] = []
        for item in rows[:8]:
            if not isinstance(item, dict):
                continue
            related = (((item.get("relationships") or {}).get("lei-records") or {}).get("data") or {})
            lei = str(related.get("id") or "").strip().upper()
            if LEI_RE.match(lei) and lei not in leis:
                leis.append(lei)
        out: list[GleifEntity] = []
        for lei in leis:
            entity = await self._fetch_lei(client, lei)
            if entity:
                out.append(entity)
        return out

    async def _fetch_lei(self, client: httpx.AsyncClient, lei: str) -> GleifEntity | None:
        response = await client.get(f"{GLEIF_API}/lei-records/{lei}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            response.raise_for_status()
        payload = response.json()
        record = payload.get("data") if isinstance(payload, dict) else None
        return parse_lei_record(record)

    async def _parents(self, client: httpx.AsyncClient, lei: str) -> list[dict[str, str]]:
        parents: list[dict[str, str]] = []
        for rel in ("direct-parent", "ultimate-parent"):
            try:
                response = await client.get(f"{GLEIF_API}/lei-records/{lei}/{rel}")
            except Exception:
                continue
            if response.status_code != 200:
                continue
            try:
                payload = response.json()
                entity = parse_lei_record(payload.get("data") if isinstance(payload, dict) else None)
            except Exception:
                continue
            if entity:
                parents.append({
                    "relationship": rel,
                    "lei": entity.lei,
                    "legalName": entity.legal_name,
                })
        return parents


_provider = GleifProvider()


def get_gleif_provider() -> GleifProvider:
    return _provider


async def lookup_gleif(query: str, country_code: str | None = None) -> GleifLookup:
    return await get_gleif_provider().lookup(query, country_code)

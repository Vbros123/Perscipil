"""Canonical company identity resolution, independent of any one data source."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from core.provider_budget import ProviderClient, HOOKS

from core.config import get_settings

logger = logging.getLogger("privatelens.resolver")
settings = get_settings()
HEADERS = {"User-Agent": get_settings().PUBLIC_DATA_USER_AGENT}

LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
    "company", "co", "plc", "lp", "llp", "pllc", "pc", "na",
})
LEADING_STOPWORDS = frozenset({"the", "a", "an"})
CORPORATE_QUALIFIERS = LEGAL_SUFFIXES | frozenset({
    "industries", "industry", "group", "holdings", "holding", "international",
    "worldwide", "partners", "technologies", "technology", "systems", "solutions",
    "services", "service", "bank", "banks", "motors", "motor", "airlines",
    "airways", "energy", "foods", "food", "brands", "ventures", "capital",
    "partners", "associates", "enterprises", "enterprise",
})
NON_CORPORATE_EXTRAS = frozenset({
    "family", "families", "people", "person", "brothers", "sisters",
    "descendants", "dynasty", "clan", "foundation",
})
ORGANISATION_HINTS = (
    "company", "corporation", "conglomerate", "business", "enterprise", "firm",
    "manufacturer", "retailer", "bank", "insurer", "airline", "startup",
    "subsidiary", "holding", "group", "brand", "organisation", "organization",
    "supplier", "operator", "provider", "chain", "publisher", "studio",
    "professional services network", "accounting firm",
)
PUBLIC_HINTS = (
    "publicly traded", "public company", "listed on", "nyse", "nasdaq",
    "stock exchange", "ticker symbol",
)
PRIVATE_HINTS = (
    "privately held", "private company", "family-owned", "closely held",
    "privately owned",
)
FAMILY_HINTS = (
    "family", "descendants of", "dynasty", "heirs of", "clan",
)
PERSON_HINTS = (
    "american businessman", "businessman", "businesswoman", "entrepreneur",
    "born ", " is a person", "politician", "investor and",
)
SUBSIDIARY_HINTS = ("subsidiary of", "division of", "owned by")
PARENT_HINTS = ("parent company", "holding company")
NONPROFIT_HINTS = ("nonprofit", "non-profit", "charity", "foundation", "ngo")
GOVERNMENT_HINTS = ("government agency", "federal agency", "ministry of", "department of")


def _has_hint(text: str, hints: tuple[str, ...]) -> bool:
    """Match multi-word phrases as substrings and single tokens on word boundaries."""
    lowered = (text or "").lower()
    if not lowered:
        return False
    for hint in hints:
        if " " in hint:
            if hint in lowered:
                return True
        elif re.search(rf"\b{re.escape(hint)}\b", lowered):
            return True
    return False

SCOREABLE_TYPES = frozenset({"company", "parent_company", "subsidiary"})
AUTO_SELECT_THRESHOLD = 75
MIN_MARGIN = 15

WIKIDATA_TYPE_MAP = {
    "Q4830453": "company",       # business
    "Q6881511": "company",       # enterprise
    "Q891723": "company",        # public company
    "Q167037": "company",        # corporation
    "Q783794": "company",        # company
    "Q161726": "company",        # multinational corporation
    "Q219577": "parent_company", # holding company
    "Q18624259": "subsidiary",
    "Q658255": "subsidiary",
    "Q431289": "brand",
    "Q115580": "family",
    "Q8436": "family",
    "Q5": "person",
    "Q163740": "nonprofit",
    "Q157031": "nonprofit",
    "Q327333": "government",
    "Q2659904": "government",
}


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
    """True when two labels are the same company, allowing corporate suffixes only."""
    a, b = canonical_key(left), canonical_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if not longer.startswith(shorter + " "):
        return False
    extra = longer[len(shorter) + 1:].split()
    if any(token in NON_CORPORATE_EXTRAS for token in extra):
        return False
    return all(token in CORPORATE_QUALIFIERS for token in extra)


def _entity_type_from_text(title: str, description: str, extract: str) -> str:
    blob = f"{title} {description} {extract[:500]}"
    title_l = (title or "").lower()
    description_l = (description or "").lower()
    if title_l.endswith(" family") or " descendants of " in blob.lower() or _has_hint(description, FAMILY_HINTS):
        if not _has_hint(description, ORGANISATION_HINTS) and "conglomerate" not in description_l:
            return "family"
        if title_l.endswith(" family"):
            return "family"
    if _has_hint(blob, PERSON_HINTS) and not _has_hint(description, ORGANISATION_HINTS):
        return "person"
    if _has_hint(blob, GOVERNMENT_HINTS):
        return "government"
    if _has_hint(blob, NONPROFIT_HINTS) and not _has_hint(description, ("company",)):
        return "nonprofit"
    if _has_hint(blob, SUBSIDIARY_HINTS):
        return "subsidiary"
    if _has_hint(blob, PARENT_HINTS):
        return "parent_company"
    if _has_hint(description, ORGANISATION_HINTS) or "conglomerate" in description_l:
        return "company"
    if _has_hint(extract[:400], ORGANISATION_HINTS):
        return "company"
    return "unknown"


def _entity_type_from_wikidata(instance_ids: list[str], fallback: str) -> str:
    for qid in instance_ids:
        mapped = WIKIDATA_TYPE_MAP.get(qid)
        if mapped:
            return mapped
    return fallback


def _wikidata_entity_type(instance_ids: list[str], label: str, description: str) -> str:
    if label.lower().endswith(" family") or _has_hint(description, FAMILY_HINTS):
        return "family"
    if _has_hint(description, PERSON_HINTS):
        return "person"
    mapped = _entity_type_from_wikidata(instance_ids, "")
    if mapped:
        return mapped
    return _entity_type_from_text(label, description, "")


def rank_candidate(query: str, candidate: "CompanyCandidate") -> int:
    """0-100 match score. Not a PerpScore."""
    score = 0
    q_key = canonical_key(query)
    t_key = candidate.canonical_key or canonical_key(candidate.title)
    if q_key == t_key:
        score += 40
    elif names_match(query, candidate.title):
        score += 28
    elif t_key.startswith(q_key + " ") or q_key.startswith(t_key + " "):
        score += 8
    if candidate.entity_type in SCOREABLE_TYPES:
        score += 25
    elif candidate.entity_type == "brand":
        score += 10
    elif candidate.entity_type in {"family", "person"}:
        score -= 40
    else:
        score += 2
    blob = f"{candidate.description} {candidate.extract[:300]}"
    if _has_hint(candidate.description or "", ORGANISATION_HINTS):
        score += 15
    elif _has_hint(blob, ORGANISATION_HINTS):
        score += 8
    if candidate.domain:
        score += 8
    if candidate.wikidata_type in SCOREABLE_TYPES:
        score += 12
    if candidate.founded_year:
        score += 5
    return max(0, min(100, score))


@dataclass
class CompanyCandidate:
    title: str
    description: str = ""
    extract: str = ""
    url: str = ""
    canonical_key: str = ""
    company_type: str = "unknown"
    entity_type: str = "unknown"
    founded_year: int | None = None
    domain: str | None = None
    confidence: int = 0
    wikidata_id: str | None = None
    wikidata_type: str | None = None
    industry: str | None = None
    location: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.title,
            "canonicalName": self.title,
            "description": self.description,
            "companyType": self.company_type,
            "entityType": self.entity_type,
            "domain": self.domain,
            "industry": self.industry or self.description,
            "location": self.location,
            "confidence": self.confidence,
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
    entity_type: str = "unknown"
    identifiers: dict[str, str] = field(default_factory=dict)
    resolution_confidence: int = 0
    resolution_status: str = "unresolved"
    candidates: list[CompanyCandidate] = field(default_factory=list)
    wikidata_id: str | None = None
    wikidata_entity: dict[str, Any] | None = None
    founded_year: int | None = None
    needs_disambiguation: bool = False
    limited_identification: bool = False
    gleif: dict[str, Any] | None = None
    sec: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        gleif = self.gleif or {}
        selected = gleif.get("selected") if isinstance(gleif.get("selected"), dict) else gleif
        sec = self.sec or {}
        sec_selected = sec.get("selected") if isinstance(sec.get("selected"), dict) else {}
        return {
            "name": self.legal_name,
            "canonicalName": self.canonical_name,
            "legalName": selected.get("legalName") or self.legal_name,
            "lei": self.identifiers.get("lei") or selected.get("lei"),
            "cik": self.identifiers.get("cik") or sec_selected.get("cik"),
            "ticker": self.identifiers.get("ticker") or sec_selected.get("ticker"),
            "uei": self.identifiers.get("uei"),
            "entityStatus": selected.get("entityStatus"),
            "jurisdiction": selected.get("jurisdiction"),
            "legalForm": selected.get("legalForm"),
            "registeredAddress": selected.get("registeredAddress"),
            "parents": selected.get("parents") or [],
            "domain": self.domain,
            "industry": self.industry,
            "companyType": self.company_type,
            "entityType": self.entity_type,
            "location": self.headquarters,
            "aliases": self.aliases,
            "identifiers": self.identifiers,
            "resolutionConfidence": self.resolution_confidence,
            "gleif": gleif or None,
            "sec": sec or None,
        }

    def resolution_payload(self) -> dict[str, Any]:
        selected = None
        if self.resolution_status == "resolved":
            selected = {
                "name": self.canonical_name,
                "canonicalName": self.canonical_name,
                "entityType": self.entity_type,
                "companyType": self.company_type,
                "confidence": self.resolution_confidence,
                "domain": self.domain,
                "industry": self.industry,
                "description": self.industry,
            }
        return {
            "status": self.resolution_status,
            "selected": selected,
            "candidates": [item.as_dict() for item in self.candidates],
            "limited_identification": self.limited_identification,
            "needs_disambiguation": self.needs_disambiguation,
            "resolution_confidence": self.resolution_confidence,
            "gleif": self.gleif,
        }


def _claim_values(entity: dict, property_id: str) -> list[dict[str, Any]]:
    values = []
    for claim in (entity.get("claims") or {}).get(property_id, []):
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if value is not None:
            values.append(value)
    return values


def _wikidata_year(entity: dict) -> int | None:
    for value in _claim_values(entity, "P571"):
        timestamp = value.get("time") if isinstance(value, dict) else None
        match = re.match(r"^[+-](\d{4,})-", timestamp or "")
        if match:
            year = int(match.group(1))
            if 1600 <= year <= datetime.now().year:
                return year
    return None


async def _wikidata_candidates(client: httpx.AsyncClient, name: str, limit: int = 8) -> list[tuple[CompanyCandidate, dict]]:
    """Find structured Wikidata items by name and load their verified claims."""
    response = await client.get(
        "https://www.wikidata.org/w/api.php",
        params={"action": "wbsearchentities", "search": name, "language": "en",
                "uselang": "en", "type": "item", "limit": limit, "format": "json"},
        headers=HEADERS,
    )
    if response.status_code != 200:
        raise httpx.HTTPStatusError(
            "Wikidata search failed", request=httpx.Request("GET", "https://www.wikidata.org/w/api.php"),
            response=response,
        )
    hits = response.json().get("search", [])
    ids = [hit.get("id") for hit in hits if re.fullmatch(r"Q\d+", hit.get("id") or "")]
    if not ids:
        return []
    entities_response = await client.get(
        "https://www.wikidata.org/w/api.php",
        params={"action": "wbgetentities", "ids": "|".join(ids), "props": "labels|descriptions|aliases|claims",
                "languages": "en", "format": "json"},
        headers=HEADERS,
    )
    if entities_response.status_code != 200:
        raise httpx.HTTPStatusError(
            "Wikidata entity lookup failed", request=httpx.Request("GET", "https://www.wikidata.org/w/api.php"),
            response=entities_response,
        )
    entities = entities_response.json().get("entities", {})
    candidates: list[tuple[CompanyCandidate, dict]] = []
    for hit in hits:
        qid = hit.get("id")
        entity = entities.get(qid, {})
        if not entity or entity.get("missing") is not None:
            continue
        label = (entity.get("labels", {}).get("en") or {}).get("value") or hit.get("label") or ""
        aliases = [alias.get("value", "") for alias in entity.get("aliases", {}).get("en", [])]
        if not label or not any(names_match(name, candidate) for candidate in [label, *aliases]):
            continue
        description = (entity.get("descriptions", {}).get("en") or {}).get("value", "")
        instance_ids = [value.get("id") for value in _claim_values(entity, "P31") if isinstance(value, dict) and value.get("id")]
        entity_type = _wikidata_entity_type(instance_ids, label, description)
        official_sites = [value for value in _claim_values(entity, "P856") if isinstance(value, str)]
        domain = None
        if official_sites:
            from urllib.parse import urlparse
            domain = (urlparse(official_sites[0]).hostname or "").removeprefix("www.").lower() or None
        founded_year = _wikidata_year(entity)
        candidate = CompanyCandidate(
            title=label, description=description, extract=description,
            url=f"https://www.wikidata.org/wiki/{qid}", canonical_key=canonical_key(label),
            entity_type=entity_type, founded_year=founded_year, domain=domain,
            wikidata_id=qid, wikidata_type=entity_type, industry=description or None,
        )
        candidate.confidence = rank_candidate(name, candidate)
        candidates.append((candidate, entity))
    return candidates


def _unresolved(name: str, key: str, candidates: list[CompanyCandidate] | None = None) -> ResolvedCompany:
    ranked = sorted(candidates or [], key=lambda item: item.confidence, reverse=True)
    return ResolvedCompany(
        query_name=name,
        canonical_key=key or name.strip().lower(),
        canonical_name=name.strip(),
        legal_name=name.strip(),
        aliases=[],
        resolution_confidence=max((item.confidence for item in ranked), default=10),
        resolution_status="unresolved",
        candidates=ranked,
        limited_identification=True,
        needs_disambiguation=False,
    )


def _resolved_from_candidate(
    name: str,
    key: str,
    chosen: CompanyCandidate,
    summary: dict,
    all_candidates: list[CompanyCandidate],
) -> ResolvedCompany:
    aliases = list(dict.fromkeys(item for item in [name.strip(), chosen.title] if item))
    return ResolvedCompany(
        query_name=name,
        canonical_key=chosen.canonical_key or key,
        canonical_name=chosen.title,
        legal_name=chosen.title,
        aliases=aliases,
        domain=chosen.domain,
        industry=chosen.industry or chosen.description or None,
        headquarters=chosen.location,
        company_type=chosen.company_type,
        entity_type=chosen.entity_type,
        identifiers={"wikidata": chosen.wikidata_id} if chosen.wikidata_id else {},
        resolution_confidence=chosen.confidence,
        resolution_status="resolved",
        candidates=all_candidates,
        wikidata_id=chosen.wikidata_id,
        wikidata_entity=summary,
        founded_year=chosen.founded_year,
        needs_disambiguation=False,
        limited_identification=False,
    )


def _apply_gleif(resolved: ResolvedCompany, lookup) -> ResolvedCompany:
    """Attach GLEIF identity. A missing LEI never proves the company does not exist."""
    if lookup is None:
        return resolved
    payload = lookup.as_dict()
    resolved.gleif = payload
    selected = lookup.selected
    if selected is None:
        return resolved
    resolved.identifiers = {**resolved.identifiers, "lei": selected.lei}
    aliases = list(resolved.aliases)
    if selected.legal_name and selected.legal_name not in aliases:
        aliases.append(selected.legal_name)
    resolved.aliases = aliases
    resolved.legal_name = selected.legal_name or resolved.legal_name
    if selected.registered_address and not resolved.headquarters:
        resolved.headquarters = selected.registered_address
    if resolved.resolution_status != "resolved" and lookup.status == "live":
        resolved.resolution_status = "resolved"
        resolved.canonical_name = selected.legal_name
        resolved.canonical_key = canonical_key(selected.legal_name) or resolved.canonical_key
        resolved.entity_type = "company" if resolved.entity_type in {"unknown", ""} else resolved.entity_type
        resolved.limited_identification = False
        resolved.needs_disambiguation = False
        resolved.resolution_confidence = max(resolved.resolution_confidence, selected.match_score)
        logger.info(
            "[Resolver] Query=%r gleif_lei=%s legal_name=%r status=resolved_from_gleif",
            resolved.query_name, selected.lei, selected.legal_name,
        )
    elif resolved.resolution_status == "resolved":
        logger.info(
            "[Resolver] Query=%r gleif_lei=%s legal_name=%r status=gleif_attached",
            resolved.query_name, selected.lei, selected.legal_name,
        )
    return resolved


def _apply_sec(resolved: ResolvedCompany, lookup) -> ResolvedCompany:
    """Attach an SEC CIK when the name matches a registrant. Missing CIK is not negative."""
    if lookup is None:
        return resolved
    payload = lookup.as_dict()
    resolved.sec = payload
    selected = lookup.selected
    if selected is None:
        return resolved
    resolved.identifiers = {
        **resolved.identifiers,
        "cik": selected.cik,
        **({"ticker": selected.ticker} if selected.ticker else {}),
    }
    if selected.title and selected.title not in resolved.aliases:
        resolved.aliases = [*resolved.aliases, selected.title]
    if resolved.company_type == "unknown":
        resolved.company_type = "public"
    if resolved.resolution_status == "resolved":
        resolved.resolution_confidence = max(resolved.resolution_confidence, min(92, selected.match_score or 0))
    logger.info("[Resolver] Query=%r cik=%s ticker=%s status=sec_attached", resolved.query_name, selected.cik, selected.ticker)
    return resolved


async def resolve_company(name: str, selected_title: str | None = None, country_code: str | None = None) -> ResolvedCompany:
    """Resolve a typed name to a canonical company before collectors run."""
    key = canonical_key(name)
    if not key:
        unresolved = _unresolved(name, key)
        logger.info("[Resolver] Query=%r status=unresolved reason=empty_key", name)
        return unresolved

    resolved = await _resolve_from_public_sources(name, key, selected_title)
    try:
        from services.providers.gleif import lookup_gleif

        gleif = await lookup_gleif(selected_title or name, country_code)
        if gleif.selected is None and resolved.canonical_name and resolved.canonical_name.lower() != name.lower():
            alias = await lookup_gleif(resolved.canonical_name, country_code)
            if alias.selected is not None:
                gleif = alias
        resolved = _apply_gleif(resolved, gleif)
    except Exception as exc:
        logger.warning("[Resolver] Query=%r gleif_error=%s", name, type(exc).__name__)
    try:
        from services.providers.sec import lookup_sec_cik

        aliases = list(resolved.aliases)
        if resolved.legal_name and resolved.legal_name not in aliases:
            aliases.append(resolved.legal_name)
        sec = await lookup_sec_cik(selected_title or name, aliases)
        resolved = _apply_sec(resolved, sec)
    except Exception as exc:
        logger.warning("[Resolver] Query=%r sec_error=%s", name, type(exc).__name__)
    return resolved


async def _resolve_from_public_sources(name: str, key: str, selected_title: str | None = None) -> ResolvedCompany:
    try:
        async with ProviderClient(event_hooks=HOOKS, timeout=settings.HTTP_TIMEOUT) as client:
            if selected_title:
                matches = await _wikidata_candidates(client, selected_title, limit=10)
                matching = [(candidate, entity) for candidate, entity in matches if names_match(name, candidate.title)]
                if matching:
                    candidate, entity = max(matching, key=lambda item: item[0].confidence)
                    if candidate.entity_type in SCOREABLE_TYPES and candidate.confidence >= 70:
                        resolved = _resolved_from_candidate(name, key, candidate, entity, [item[0] for item in matching])
                        logger.info("[Resolver] Query=%r selected=%r entity_type=%s confidence=%s status=resolved",
                                    name, selected_title, candidate.entity_type, candidate.confidence)
                        return resolved
                logger.info("[Resolver] Query=%r selected=%r status=unresolved", name, selected_title)
                return _unresolved(name, key)
            ranked = sorted(await _wikidata_candidates(client, name), key=lambda item: item[0].confidence, reverse=True)
            candidates = [item[0] for item in ranked]

            if not ranked:
                logger.info("[Resolver] Query=%r status=unresolved reason=no_candidates", name)
                return _unresolved(name, key)

            scoreable = [item for item in candidates if item.entity_type in SCOREABLE_TYPES]
            if not scoreable and any(item.entity_type == "brand" for item in candidates):
                scoreable = [item for item in candidates if item.entity_type == "brand"]

            if not scoreable:
                logger.info(
                    "[Resolver] Query=%r status=unresolved reason=no_scoreable_entity best=%r entity_type=%s",
                    name,
                    candidates[0].title,
                    candidates[0].entity_type,
                )
                return _unresolved(name, key, candidates)

            best = scoreable[0]
            second = scoreable[1] if len(scoreable) > 1 else None
            margin = best.confidence - (second.confidence if second else 0)
            exact_name = canonical_key(name) == best.canonical_key
            if second is None and not exact_name:
                choices = [item for item in candidates if item.entity_type in SCOREABLE_TYPES or item.entity_type == "brand"]
                return ResolvedCompany(
                    query_name=name, canonical_key=key, canonical_name=name.strip(), legal_name=name.strip(),
                    aliases=[], resolution_confidence=best.confidence, resolution_status="ambiguous",
                    candidates=choices, needs_disambiguation=True, limited_identification=True,
                    entity_type=best.entity_type,
                )
            auto = ((second is None and best.confidence >= 70) or
                    (best.confidence >= AUTO_SELECT_THRESHOLD and margin >= MIN_MARGIN)) and exact_name

            if auto:
                entity = next(item[1] for item in ranked if item[0].title == best.title)
                resolved = _resolved_from_candidate(name, key, best, entity, candidates)
                logger.info(
                    "[Resolver] Query=%r best=%r entity_type=%s confidence=%s status=resolved",
                    name, best.title, best.entity_type, best.confidence,
                )
                return resolved

            logger.info(
                "[Resolver] Query=%r status=ambiguous best=%r confidence=%s second=%r second_confidence=%s",
                name,
                best.title,
                best.confidence,
                second.title if second else None,
                second.confidence if second else None,
            )
            return ResolvedCompany(
                query_name=name,
                canonical_key=key,
                canonical_name=name.strip(),
                legal_name=name.strip(),
                aliases=[],
                resolution_confidence=best.confidence,
                resolution_status="ambiguous",
                candidates=candidates,
                needs_disambiguation=True,
                limited_identification=True,
                entity_type=best.entity_type,
            )
    except Exception as exc:
        logger.warning("[Resolver] Query=%r status=unresolved error_type=%s", name, type(exc).__name__)
        return _unresolved(name, key)

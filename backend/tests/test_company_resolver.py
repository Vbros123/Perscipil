import asyncio
import re

from services.evidence import CompanyIdentity
from services.resolver import (
    _entity_type_from_text,
    canonical_key,
    names_match,
    rank_candidate,
    resolve_company,
    CompanyCandidate,
)


def test_cargill_aliases_share_a_canonical_key():
    keys = {
        canonical_key("Cargill"),
        canonical_key("CARGILL"),
        canonical_key("Cargill Inc"),
        canonical_key("Cargill, Inc."),
        canonical_key("Cargill Incorporated"),
        canonical_key("The Cargill Company"),
    }
    assert keys == {"cargill"}


def test_suffix_and_punctuation_do_not_create_two_cache_keys():
    left = CompanyIdentity(legal_name="Cargill Inc", country_code="US")
    right = CompanyIdentity(legal_name="Cargill Incorporated", country_code="US")
    third = CompanyIdentity(legal_name="Cargill", country_code="US")
    assert left.cache_key() == right.cache_key() == third.cache_key()
    assert left.cache_key().startswith("cargill:US:")


def test_registration_or_postal_code_changes_the_cache_key():
    base = CompanyIdentity(legal_name="Cargill", country_code="US")
    with_reg = CompanyIdentity(legal_name="Cargill Inc", country_code="US", registration_number="12-345")
    with_zip = CompanyIdentity(legal_name="Cargill", country_code="US", postal_code="55440")
    assert base.cache_key() != with_reg.cache_key()
    assert base.cache_key() != with_zip.cache_key()


def test_unrelated_names_do_not_collapse():
    assert canonical_key("Red Stripe") != canonical_key("Stripe")
    assert not names_match("Adidas", "Stripe")
    assert names_match("Stripe, Inc.", "Stripe")


def test_family_is_not_the_same_company():
    assert not names_match("Cargill", "Cargill family")
    assert names_match("Cargill", "Cargill Inc")
    assert names_match("Koch", "Koch Industries")


def test_entity_type_classifier_separates_company_from_family():
    assert _entity_type_from_text(
        "Cargill",
        "American multinational food conglomerate",
        "Cargill, Incorporated is an American privately held global corporation.",
    ) == "company"
    assert _entity_type_from_text(
        "Cargill family",
        "Descendants of William Wallace Cargill",
        "The Cargill family are the descendants of William Wallace Cargill.",
    ) == "family"
    assert _entity_type_from_text(
        "Elon Musk",
        "American businessman",
        "Elon Reeve Musk is a businessman.",
    ) == "person"


def test_family_ranks_far_below_operating_company():
    company = CompanyCandidate(
        title="Cargill",
        description="American multinational food conglomerate",
        extract="Cargill is an American multinational food corporation.",
        canonical_key="cargill",
        entity_type="company",
        domain="cargill.com",
    )
    family = CompanyCandidate(
        title="Cargill family",
        description="Descendants of William Wallace Cargill",
        extract="The Cargill family are the descendants of William Wallace Cargill.",
        canonical_key="cargill family",
        entity_type="family",
    )
    assert rank_candidate("Cargill", company) >= 75
    assert rank_candidate("Cargill", family) < 40
    assert rank_candidate("Cargill", company) - rank_candidate("Cargill", family) >= 15


def test_whitespace_only_name_is_still_rejected():
    for blank in ("   ", "\t\t", "  \n "):
        try:
            CompanyIdentity(legal_name=blank)
        except Exception:
            continue
        raise AssertionError(f"blank name was accepted: {blank!r}")


class _FakeResponse:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, summaries, search_titles):
        self.summaries = summaries
        self.search_titles = search_titles

    async def get(self, url, params=None, headers=None):
        params = params or {}
        if params.get("action") == "wbsearchentities":
            hits = []
            for title, summary in self.summaries.items():
                if title in self.search_titles:
                    hits.append({"id": summary["id"], "label": title})
            return _FakeResponse({"search": hits})
        if params.get("action") == "wbgetentities":
            entities = {summary["id"]: summary for title, summary in self.summaries.items()
                        if summary["id"] in params.get("ids", "").split("|")}
            return _FakeResponse({"entities": entities})
        return _FakeResponse({}, status=404)


def _summary(title, description, extract):
    qid = f"Q{abs(hash(title)) % 1000000}"
    year_match = re.search(r"(?:founded|established) in (\d{4})", extract, re.I)
    instance = "Q5" if "businessman" in description.lower() else "Q783794"
    claims = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": instance}}}}]}
    if year_match:
        claims["P571"] = [{"mainsnak": {"datavalue": {"value": {"time": f"+{year_match.group(1)}-00-00T00:00:00Z"}}}}]
    return {
        "id": qid,
        "labels": {"en": {"value": title}},
        "descriptions": {"en": {"value": description}},
        "claims": claims,
        "aliases": {"en": []},
    }


def _patch_client(monkeypatch, summaries, search_titles):
    entries = {title: {**summary, "aliases": {"en": []}} for title, summary in summaries.items()}
    class _Factory:
        def __init__(self, *args, **kwargs):
            self.client = _FakeClient(entries, search_titles)

        async def __aenter__(self):
            return self.client

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("services.resolver.ProviderClient", lambda *args, **kwargs: _Factory(entries, search_titles))

    async def no_gleif(query, country_code=None):
        from services.providers.gleif import GleifLookup
        return GleifLookup(status="unavailable")

    async def no_sec(query, aliases=None):
        from services.providers.sec import SecLookup
        return SecLookup(status="not_applicable", error_code="NO_CIK")

    monkeypatch.setattr("services.providers.gleif.lookup_gleif", no_gleif)
    monkeypatch.setattr("services.providers.sec.lookup_sec_cik", no_sec)


def test_cargill_auto_selects_company_over_family(monkeypatch):
    summaries = {
        "Cargill": _summary(
            "Cargill",
            "American multinational food conglomerate",
            "Cargill, Incorporated is an American privately held global food corporation founded in 1865.",
        ),
        "Cargill family": _summary(
            "Cargill family",
            "Descendants of William Wallace Cargill",
            "The Cargill family are the descendants of William Wallace Cargill, founder of Cargill.",
        ),
    }
    summaries["Cargill family"]["labels"]["en"]["value"] = "Cargill family"
    summaries["Cargill family"]["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q8436"
    _patch_client(monkeypatch, summaries, ["Cargill", "Cargill family"])
    original = _FakeClient.get
    async def restore_family_label(self, url, params=None, headers=None):
        result = await original(self, url, params=params, headers=headers)
        if (params or {}).get("action") == "wbgetentities":
            family_id = summaries["Cargill family"]["id"]
            result._payload["entities"][family_id]["labels"]["en"]["value"] = "Cargill family"
            result._payload["entities"][family_id]["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q8436"
        return result
    monkeypatch.setattr(_FakeClient, "get", restore_family_label)
    resolved = asyncio.run(resolve_company("Cargill"))
    assert resolved.needs_disambiguation is False
    assert resolved.resolution_status == "resolved"
    assert resolved.canonical_name == "Cargill"
    assert resolved.entity_type == "company"
    assert resolved.resolution_confidence >= 75
    assert resolved.candidates[0].entity_type == "company"


def test_cargill_aliases_auto_resolve(monkeypatch):
    summaries = {
        "Cargill": _summary("Cargill", "American multinational food conglomerate", "Cargill is an American company."),
        "Cargill Inc": _summary("Cargill", "American multinational food conglomerate", "Cargill is an American company."),
        "Cargill Incorporated": _summary("Cargill", "American multinational food conglomerate", "Cargill is an American company."),
        "CARGILL": _summary("Cargill", "American multinational food conglomerate", "Cargill is an American company."),
    }
    for query in ("Cargill Inc", "Cargill Incorporated", "CARGILL"):
        _patch_client(monkeypatch, summaries, ["Cargill"])
        resolved = asyncio.run(resolve_company(query))
        assert resolved.resolution_status == "resolved"
        assert resolved.entity_type == "company"


def test_known_companies_auto_resolve(monkeypatch):
    fixtures = {
        "Microsoft": ("Microsoft", "American multinational technology corporation", "Microsoft Corporation is an American company."),
        "OpenAI": ("OpenAI", "American artificial intelligence company", "OpenAI is an American AI research company."),
        "Stripe": ("Stripe, Inc.", "American multinational financial services and software as a service company", "Stripe, Inc. is an American company."),
        "SpaceX": ("SpaceX", "American aerospace company", "Space Exploration Technologies Corp. is an American company."),
    }
    for query, (title, description, extract) in fixtures.items():
        summaries = {query: _summary(title, description, extract), title: _summary(title, description, extract)}
        _patch_client(monkeypatch, summaries, [title])
        resolved = asyncio.run(resolve_company(query))
        assert resolved.resolution_status == "resolved", query
        assert resolved.entity_type in {"company", "parent_company", "subsidiary"}, query
        assert resolved.needs_disambiguation is False, query


def test_ambiguous_companies_require_selection(monkeypatch):
    summaries = {
        "United Airlines": _summary("United Airlines", "American airline", "United Airlines, Inc. is an American airline."),
            "United Parcel Service": _summary(
            "United Parcel Service",
            "American package delivery company",
            "United Parcel Service is an American shipping company.",
        ),
        "ABC": {**_summary("ABC", "Topics referred to by the same term", ""), "type": "disambiguation"},
        "ABC Television": _summary(
            "ABC Television",
            "American television company",
            "ABC Television is an American broadcasting company.",
        ),
        "ABC Retail": _summary(
            "ABC Retail",
            "Australian retail company",
            "ABC Retail is an Australian retail company.",
        ),
    }
    _patch_client(monkeypatch, summaries, ["United Airlines", "United Parcel Service"])
    united = asyncio.run(resolve_company("United"))
    assert united.resolution_status == "ambiguous"
    assert united.needs_disambiguation is True
    assert all(item.entity_type == "company" for item in united.candidates)

    _patch_client(monkeypatch, summaries, ["ABC Television", "ABC Retail"])
    original = _FakeClient.get
    async def add_abc_aliases(self, url, params=None, headers=None):
        result = await original(self, url, params=params, headers=headers)
        if (params or {}).get("action") == "wbgetentities":
            for entity in result._payload["entities"].values():
                entity["aliases"] = {"en": [{"value": "ABC"}]}
        return result
    monkeypatch.setattr(_FakeClient, "get", add_abc_aliases)
    abc = asyncio.run(resolve_company("ABC"))
    assert abc.resolution_status == "ambiguous"
    assert abc.needs_disambiguation is True


def test_sole_scoreable_company_is_auto_selected(monkeypatch):
    summaries = {
        "Deloitte": _summary(
            "Deloitte",
            "Professional services network",
            "Deloitte Touche Tohmatsu Limited is a multinational professional services company.",
        ),
    }
    _patch_client(monkeypatch, summaries, ["Deloitte"])
    resolved = asyncio.run(resolve_company("Deloitte"))
    assert resolved.needs_disambiguation is False
    assert resolved.resolution_status == "resolved"
    assert resolved.entity_type in {"company", "parent_company", "subsidiary"}


def test_scoreable_company_replaces_same_key_non_company(monkeypatch):
    summaries = {
        "Mars": _summary("Mars", "Planet", "Mars is the fourth planet from the Sun."),
        "Mars, Incorporated": _summary(
            "Mars, Incorporated",
            "American multinational manufacturer of confectionery",
            "Mars, Incorporated is an American multinational manufacturer of confectionery.",
        ),
    }
    _patch_client(monkeypatch, summaries, ["Mars", "Mars, Incorporated"])
    resolved = asyncio.run(resolve_company("Mars"))
    assert resolved.resolution_status == "resolved"
    assert resolved.canonical_name == "Mars, Incorporated"
    assert resolved.entity_type == "company"


def test_person_is_never_auto_selected(monkeypatch):
    summaries = {
        "Elon Musk": _summary("Elon Musk", "American businessman", "Elon Reeve Musk is a businessman."),
    }
    _patch_client(monkeypatch, summaries, ["Elon Musk"])
    resolved = asyncio.run(resolve_company("Elon Musk"))
    assert resolved.needs_disambiguation is False
    assert resolved.resolution_status == "unresolved"
    assert resolved.entity_type != "company"


def test_selected_title_skips_disambiguation(monkeypatch):
    summaries = {
        "United Airlines": _summary("United Airlines", "American airline", "United Airlines, Inc. is an American airline."),
        "United Parcel Service": _summary(
            "United Parcel Service",
            "American package delivery company",
            "United Parcel Service is an American shipping company.",
        ),
    }
    _patch_client(monkeypatch, summaries, ["United Airlines", "United Parcel Service"])
    resolved = asyncio.run(resolve_company("United", selected_title="United Airlines"))
    assert resolved.resolution_status == "resolved"
    assert resolved.needs_disambiguation is False
    assert resolved.canonical_name == "United Airlines"


def test_professional_services_network_is_an_organisation():
    from services.resolver import _wikidata_candidates
    summary = _summary('Deloitte', 'Multinational professional services network',
                       'Deloitte is a multinational professional services network based in London, England.')
    class Client:
        async def get(self, url, params=None, headers=None):
            if params['action'] == 'wbsearchentities':
                return _FakeResponse({'search': [{'id': summary['id'], 'label': 'Deloitte'}]})
            return _FakeResponse({'entities': {summary['id']: summary}})
    candidates = asyncio.run(_wikidata_candidates(Client(), 'Deloitte'))
    assert candidates[0][0].entity_type == 'company'
    assert candidates[0][0].wikidata_id == summary['id']


def test_search_timeout_does_not_prevent_exact_title_resolution(monkeypatch):
    import httpx
    _patch_client(monkeypatch, {'Deloitte': _summary(
        'Deloitte', 'Multinational professional services network',
        'Deloitte is a multinational professional services network.')}, [])
    async def get(self, url, params=None, headers=None):
        if (params or {}).get('action') == 'wbsearchentities':
            raise httpx.ReadTimeout('search timed out')
        return await _FakeClient.get(self, url, params=params, headers=headers)
    monkeypatch.setattr(_FakeClient, 'get', get)
    result = asyncio.run(resolve_company('Deloitte'))
    assert result.resolution_status == 'unresolved'


def test_wikidata_http_failure_is_not_an_absent_entity():
    import httpx
    import pytest
    from services.resolver import _wikidata_candidates
    class Client:
        async def get(self, url, **kwargs):
            return httpx.Response(403, request=httpx.Request('GET', url))
    with pytest.raises(httpx.HTTPStatusError) as error:
        asyncio.run(_wikidata_candidates(Client(), 'Example'))
    assert error.value.response.status_code == 403


def test_wikidata_missing_entity_returns_no_candidates():
    from services.resolver import _wikidata_candidates
    class Client:
        async def get(self, url, params=None, **kwargs):
            return _FakeResponse({'search': []})
    assert asyncio.run(_wikidata_candidates(Client(), 'Nonexistent Example')) == []


def test_wikidata_collector_reports_blocked_requests(monkeypatch):
    import httpx
    from services import collectors
    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url, **kwargs):
            return httpx.Response(403, request=httpx.Request('GET', url))
    monkeypatch.setattr(collectors, 'ProviderClient', lambda **kwargs: Client())
    result = asyncio.run(collectors.collect_wikidata('Example'))
    assert result.status == 'unavailable'
    assert result.error_code == 'BLOCKED'
    assert all(s['raw_score'] is None for s in result.signals)

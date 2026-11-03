from services.company_details import company_details


def snak(value):
    return {"datavalue": {"value": value}}


def claim(value, **extra):
    return {"mainsnak": snak(value), "references": [{"hash": "source"}], **extra}


def employees(amount, year):
    return claim({"amount": f"+{amount}", "unit": "1"}, qualifiers={
        "P585": [snak({"time": f"+{year}-00-00T00:00:00Z", "precision": 9})]})


def test_only_latest_dated_referenced_company_count_is_reported():
    rows = [employees(0, 2024), employees(12, 2023),
            {**employees(700, 2025), "references": []},
            {**employees(999, 2025), "rank": "deprecated"}]
    details = company_details({"P1128": rows}, "Q123")
    assert details["employeeCount"] == {
        "value": 0, "asOf": "2024", "sourceUrl": "https://www.wikidata.org/wiki/Q123#P1128"}
    assert company_details({"P1128": rows + [employees(13, 2024)]}, "Q123")["employeeCount"] is None


def test_report_includes_each_distinct_referenced_street_address():
    rows = [claim({"text": "10 First St"}), claim({"text": "20 Second St"}),
            claim({"text": "10 First St"}), claim({"text": "Old office"}, rank="deprecated")]
    details = company_details({"P6375": rows}, "Q123")
    assert details["streetAddresses"] == ["10 First St", "20 Second St"]
    assert details["employeeCount"] is None


def test_matched_company_report_keeps_headcount_and_both_registry_roles():
    import asyncio
    import httpx
    from services.resolver import _apply_gleif, _enrich_candidate, _resolved_from_candidate
    from services.providers.gleif import GleifEntity, GleifLookup

    claims = {"P1128": [employees(16, 2025)], "P6375": [claim({"text": "22 Branch St"})]}
    async def resolve():
        transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
            "entities": {"Q123": {"claims": claims}}}))
        async with httpx.AsyncClient(transport=transport) as client:
            summary = {"title": "Test Construction", "description": "construction company", "wikibase_item": "Q123"}
            candidate = await _enrich_candidate(client, summary)
            return _resolved_from_candidate("Test Construction", "test construction", candidate, summary, [candidate])
    resolved = asyncio.run(resolve())
    registry = GleifEntity("123", "Test Construction", registered_address="1 Legal St", headquarters_address="2 Main St")
    report = _apply_gleif(resolved, GleifLookup(selected=registry, status="live")).as_dict()
    assert report["details"]["employeeCount"]["value"] == 16
    assert report["details"]["streetAddresses"] == ["22 Branch St"]
    assert report["location"] == "2 Main St"
    assert report["registeredAddress"] == "1 Legal St"

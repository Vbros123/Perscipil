"""SEC EDGAR CIK resolution, XBRL parsing, and collector isolation."""
import asyncio

import httpx
import pytest

from services.collectors import collect_sec_edgar
from services.providers.sec import (
    extract_financials,
    parse_submissions,
    rank_sec_match,
    score_sec_financials,
    select_sec_match,
    pad_cik,
)
from services.resolver import ResolvedCompany
from services.scorer import compute_score


def _facts(revenue=1000, prior=800, assets=4000, liabilities=1500, cash=700, equity=2500, net=200, operating=250):
    def series(*points):
        return {"units": {"USD": [
            {"val": value, "fy": year, "fp": "FY", "form": "10-K", "end": f"{year}-06-30", "filed": f"{year}-07-30"}
            for year, value in points
        ]}}
    return {
        "cik": "0000789019",
        "entityName": "MICROSOFT CORP",
        "facts": {
            "us-gaap": {
                "Revenues": series((2024, prior), (2025, revenue)),
                "Assets": series((2025, assets)),
                "Liabilities": series((2025, liabilities)),
                "CashAndCashEquivalentsAtCarryingValue": series((2025, cash)),
                "StockholdersEquity": series((2025, equity)),
                "NetIncomeLoss": series((2025, net)),
                "OperatingIncomeLoss": series((2025, operating)),
            }
        },
    }


def test_pad_cik_and_name_ranking():
    assert pad_cik(789019) == "0000789019"
    assert rank_sec_match("Microsoft", "MICROSOFT CORP") > rank_sec_match("Microsoft", "MICROSOFT CORP ETF")
    assert select_sec_match("Apple", [
        {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        {"cik_str": 1, "ticker": "APLE", "title": "Apple Hospitality REIT Inc"},
    ])["cik_str"] == 320193
    assert select_sec_match("Cargill", [
        {"cik_str": 99, "ticker": "NONE", "title": "Unrelated Fund Trust"},
    ]) is None


def test_extract_financials_and_score():
    metrics = extract_financials(_facts())
    assert metrics["revenue"] == 1000
    assert metrics["revenueGrowth"] == pytest.approx(0.25)
    assert metrics["netIncome"] == 200
    assert metrics["debtToEquity"] == pytest.approx(0.6)
    assert metrics["period"] == "annual"
    revenue = metrics["facts"]["revenue"]
    assert revenue["source"] == "SEC EDGAR XBRL"
    assert revenue["unit"] == "USD"
    assert revenue["period"] == "annual"
    assert revenue["fiscalYear"] == 2025
    assert revenue["periodEnd"]
    assert revenue["form"] == "10-K"
    assert revenue["filed"] == "2025-07-30"
    score = score_sec_financials(metrics)
    assert 50 <= score <= 86


def test_malformed_facts_are_rejected():
    with pytest.raises(ValueError):
        extract_financials({"facts": {}})
    with pytest.raises(ValueError):
        parse_submissions({"name": "X"})


def test_private_company_is_not_applicable():
    resolved = ResolvedCompany(
        query_name="Cargill",
        canonical_key="cargill",
        canonical_name="Cargill",
        legal_name="CARGILL, INCORPORATED",
        company_type="private",
        sec={"status": "not_applicable", "errorCode": "NO_CIK", "selected": None},
    )
    result = asyncio.run(collect_sec_edgar("Cargill", resolved))
    assert result.status == "not_applicable"
    assert result.signals[0]["availability_status"] == "not_applicable"
    assert result.signals[0]["is_scored"] is False
    assert result.entity_match in {"Private company", "Not an SEC filer"}


def test_public_company_sec_is_scored():
    resolved = ResolvedCompany(
        query_name="Microsoft",
        canonical_key="microsoft",
        canonical_name="Microsoft",
        legal_name="MICROSOFT CORPORATION",
        company_type="public",
        identifiers={"cik": "0000789019"},
        sec={
            "status": "live",
            "selected": {
                "cik": "0000789019",
                "ticker": "MSFT",
                "title": "MICROSOFT CORP",
                "matchScore": 90,
                "submissions": {"filings": [{"form": "10-K", "filed": "2025-07-30"}]},
                "financials": extract_financials(_facts()),
                "sourceUrl": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019",
            },
        },
    )
    result = asyncio.run(collect_sec_edgar("Microsoft", resolved))
    assert result.status == "live"
    signal = result.signals[0]
    assert signal["signal"] == "SEC Financial Evidence"
    assert signal["is_scored"] is True
    assert signal["evidence_quality"] == "high"
    assert signal["evidence_scope"] == "company"
    scored = compute_score(result.signals, model_release_stage="shadow")
    used = next(item for item in scored["breakdown"] if item["signal"] == "SEC Financial Evidence")
    assert used["used_in_score"] is True


def test_sec_timeout_does_not_break_collector(monkeypatch):
    async def boom(name, aliases=None, cik=None):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("services.providers.sec.lookup_sec", boom)
    result = asyncio.run(collect_sec_edgar("Nvidia"))
    assert result.status == "unavailable"
    assert result.error_code == "TIMEOUT"
    assert "Traceback" not in str(result.as_source_card())


def test_live_sec_public_companies_when_reachable():
    from services.providers.sec import lookup_sec

    async def _run():
        return (
            await lookup_sec("Microsoft"),
            await lookup_sec("Apple"),
            await lookup_sec("Nvidia"),
            await lookup_sec("Cargill", aliases=["CARGILL, INCORPORATED"]),
        )

    try:
        microsoft, apple, nvidia, cargill = asyncio.run(_run())
    except Exception as exc:
        pytest.skip(f"SEC not reachable: {type(exc).__name__}")
    if microsoft.error_code in {"TIMEOUT", "RATE_LIMIT", "BLOCKED", "HTTP_ERROR", "PROXYERROR"}:
        pytest.skip(f"SEC blocked: {microsoft.error_code}")
    assert microsoft.selected is not None
    assert microsoft.selected.cik == "0000789019"
    assert microsoft.selected.financials and microsoft.selected.financials.get("revenue")
    assert apple.selected is not None
    assert apple.selected.cik == "0000320193"
    assert nvidia.selected is not None
    assert nvidia.selected.cik == "0001045810"
    assert cargill.selected is None
    assert cargill.status == "not_applicable"

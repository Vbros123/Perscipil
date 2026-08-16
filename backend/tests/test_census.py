"""Census industry context stays industry-level and never scores as company financials."""
import asyncio

from services.collectors import collect_census
from services.providers.census import infer_naics, parse_cbp_table
from services.resolver import ResolvedCompany
from services.scorer import compute_score


def test_infer_naics_for_known_companies():
    assert infer_naics("Cargill", "American multinational food corporation")["naics"] == "311"
    assert infer_naics("Microsoft", "technology company")["naics"] == "5112"
    assert infer_naics("Nvidia", "GPU semiconductor company")["naics"] == "3344"
    assert infer_naics("OpenAI", "artificial intelligence research")["naics"] == "5417"
    assert infer_naics("Stripe", "payments infrastructure")["naics"] == "5223"
    assert infer_naics("Unknown Widget Collective XYZ") is None


def test_parse_cbp_table():
    parsed = parse_cbp_table([
        ["NAME", "NAICS2017", "NAICS2017_LABEL", "ESTAB", "EMP", "PAYANN"],
        ["United States", "311", "Food Manufacturing", "30000", "1600000", "90000000"],
    ])
    assert parsed["establishments"] == 30000
    assert parsed["employment"] == 1600000


def test_missing_key_disables_census(monkeypatch):
    monkeypatch.setattr("services.providers.census.settings.CENSUS_API_KEY", None)
    result = asyncio.run(collect_census("Cargill"))
    assert result.status == "unavailable"
    assert result.error_code == "NOT_CONFIGURED"
    assert result.optional is True
    assert result.signals[0]["is_scored"] is False


def test_census_live_is_industry_context_not_scored(monkeypatch):
    from services.providers.census import CensusContext, CensusLookup

    context = CensusContext(
        naics="311",
        label="Food Manufacturing",
        year=2023,
        establishments=30000,
        employment=1600000,
        annual_payroll=90000000,
        employment_growth=0.01,
        source_url="https://api.census.gov/data/2023/cbp.html",
    )

    lookup = CensusLookup(selected=context, status="live")

    async def fake_lookup(name, industry=None, description=None):
        return lookup

    monkeypatch.setattr("services.providers.census.lookup_census", fake_lookup)
    resolved = ResolvedCompany(
        query_name="Cargill",
        canonical_key="cargill",
        canonical_name="Cargill",
        legal_name="CARGILL, INCORPORATED",
        industry="food conglomerate",
    )
    result = asyncio.run(collect_census("Cargill", resolved))
    assert result.status == "live"
    signal = result.signals[0]
    assert signal["category"] == "industry"
    assert signal["is_scored"] is False
    assert signal["evidence_scope"] == "industry"
    assert "not this company's" in signal["insight"].lower()
    scored = compute_score(result.signals + [{
        "signal": "Brand Legitimacy & Web Presence",
        "raw_score": 56,
        "category": "identity",
        "is_simulated": False,
        "is_scored": True,
        "availability_status": "live",
        "evidence_quality": "low",
    }], model_release_stage="shadow")
    industry = next(item for item in scored["breakdown"] if item["signal"] == "Industry Context")
    assert industry["used_in_score"] is False
    assert scored["category_summary"]["industry"]["score"] is None

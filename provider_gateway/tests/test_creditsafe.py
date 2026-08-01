from datetime import datetime, timezone

from config import Settings
from models import EntityRequest
from providers.creditsafe import CreditsafeAdapter


def adapter():
    return CreditsafeAdapter(Settings())


def test_entity_match_requires_registration_or_name_and_postcode():
    candidate = {
        "id": "US-123",
        "name": "Acme Manufacturing LLC",
        "regNo": "A-123",
        "address": {"postCode": "10001"},
    }
    exact_reg = adapter()._candidate_match(
        EntityRequest(legal_name="Different DBA", registration_number="A-123"),
        candidate,
    )
    exact_name_postal = adapter()._candidate_match(
        EntityRequest(legal_name="Acme Manufacturing", postal_code="10001"),
        candidate,
    )
    name_only = adapter()._candidate_match(
        EntityRequest(legal_name="Acme Manufacturing"),
        candidate,
    )

    assert exact_reg[0:2] == ("exact", 1.0)
    assert exact_name_postal[0:2] == ("exact", 0.99)
    assert name_only[0] == "ambiguous"


def test_report_without_provider_dates_cannot_create_fresh_observations():
    payload = {
        "report": {
            "creditScore": {"currentCreditRating": {"commonValue": 88}},
            "paymentData": {"dbt": 5},
        }
    }
    result = adapter()._observations(
        payload,
        "US-123",
        datetime.now(timezone.utc),
        "urn:creditsafe:company:US-123:credit-report",
    )
    assert result == []


def test_dated_report_creates_raw_observations_not_a_vendor_composite():
    payload = {
        "report": {
            "creditScore": {"currentCreditRating": {"commonValue": 88, "date": "2026-07-30T00:00:00Z"}},
            "paymentData": {"dbt": 5, "asOfDate": "2026-07-29T00:00:00Z"},
        }
    }
    result = adapter()._observations(
        payload,
        "US-123",
        datetime.now(timezone.utc),
        "urn:creditsafe:company:US-123:credit-report",
    )
    assert [item.metric for item in result] == ["creditsafe.credit_score", "creditsafe.days_beyond_terms"]
    assert [item.value for item in result] == [88.0, 5.0]

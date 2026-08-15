from services.evidence import CompanyIdentity
from services.resolver import canonical_key, names_match


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


def test_whitespace_only_name_is_still_rejected():
    for blank in ("   ", "\t\t", "  \n "):
        try:
            CompanyIdentity(legal_name=blank)
        except Exception:
            continue
        raise AssertionError(f"blank name was accepted: {blank!r}")

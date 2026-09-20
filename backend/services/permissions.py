"""Contract permissions are operator assertions, never inferred from API credentials."""
import json
from pydantic import BaseModel, ConfigDict, Field
from core.config import get_settings

class ProviderPermission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contract_reference: str = ''
    may_score: bool = False
    may_display_raw_value: bool = False
    may_display_derived_value: bool = False
    may_retain: bool = False
    retention_days: int = Field(default=0, ge=0, le=3650)
    may_use_for_monitoring: bool = False
    may_use_for_historical_analysis: bool = False
    may_use_for_model_development: bool = False
    may_redistribute_via_api: bool = False

def permission(provider):
    try:
        raw = json.loads(get_settings().PROVIDER_PERMISSIONS_JSON)
        return ProviderPermission.model_validate(raw.get(provider, {}))
    except (ValueError, TypeError, AttributeError):
        return ProviderPermission()

def allowed_providers():
    # Current reports contain raw audit values and persist snapshots. Reject a provider
    # unless every actual use is approved. Narrower contracts need a redacted pathway.
    result=[]
    for provider in ('creditsafe','middesk'):
        # Codat remains disabled until account-specific consent and cache isolation exist.
        p=permission(provider)
        if (p.contract_reference and p.may_score and p.may_display_raw_value and p.may_display_derived_value
            and p.may_retain and p.retention_days >= get_settings().REPORT_RETENTION_DAYS):
            result.append(provider)
    return result

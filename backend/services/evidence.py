"""Licensed evidence models, quality gates, and deterministic signal transforms."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "creditsafe": {
        "name": "Creditsafe Connect",
        "role": "Commercial credit reports and payment behavior",
        "access": "licensed",
        "consent_required": False,
        "official_docs": "https://doc.creditsafe.com/connect-apis-catalog/product-catalog/creditrisk",
        "signals": ["Commercial Credit Risk", "B2B Payment Behavior"],
    },
    "middesk": {
        "name": "Middesk",
        "role": "Business identity, standing, liens, bankruptcies, and litigation",
        "access": "licensed",
        "consent_required": False,
        "official_docs": "https://docs.middesk.com/home",
        "signals": ["Business Identity & Standing", "Liens, Bankruptcy & Litigation"],
    },
    "codat": {
        "name": "Codat",
        "role": "Company-consented accounting and banking aggregates",
        "access": "licensed",
        "consent_required": True,
        "official_docs": "https://docs.codat.io/",
        "signals": ["Cash Flow & Liquidity"],
    },
}


SIGNAL_SPECS: dict[str, dict[str, Any]] = {
    "Commercial Credit Risk": {
        "weight": 0.30,
        "category": "financial",
        "providers": ["creditsafe"],
        "max_age_days": 120,
    },
    "B2B Payment Behavior": {
        "weight": 0.20,
        "category": "financial",
        "providers": ["creditsafe"],
        "max_age_days": 120,
    },
    "Cash Flow & Liquidity": {
        "weight": 0.20,
        "category": "financial",
        "providers": ["codat"],
        "max_age_days": 45,
    },
    "Business Identity & Standing": {
        "weight": 0.15,
        "category": "legal",
        "providers": ["middesk"],
        "max_age_days": 180,
    },
    "Liens, Bankruptcy & Litigation": {
        "weight": 0.15,
        "category": "legal",
        "providers": ["middesk"],
        "max_age_days": 120,
    },
}


class CompanyIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(min_length=2, max_length=180)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    registration_number: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=24)
    address: str | None = Field(default=None, max_length=300)
    provider_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("legal_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip())

    @field_validator("country_code")
    @classmethod
    def clean_country(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", value):
            raise ValueError("country_code must be an ISO-2 country code")
        return value

    @field_validator("registration_number", "postal_code", "address")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", value.strip())
        return cleaned or None

    @field_validator("provider_ids")
    @classmethod
    def clean_provider_ids(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > len(PROVIDER_CATALOG):
            raise ValueError("provider_ids contains too many entries")
        cleaned: dict[str, str] = {}
        for key, provider_id in value.items():
            if key not in PROVIDER_CATALOG:
                raise ValueError(f"unsupported provider key: {key}")
            normalized = provider_id.strip()
            if not normalized or len(normalized) > 180:
                raise ValueError(f"invalid provider ID for {key}")
            cleaned[key] = normalized
        return cleaned

    def cache_key(self) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class ProviderDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["creditsafe", "middesk", "codat"]
    name: str = Field(min_length=2, max_length=120)
    license_reference: str = Field(min_length=3, max_length=180)
    permitted_use: list[str] = Field(min_length=1)


class EntityMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_entity_id: str = Field(min_length=1, max_length=180)
    legal_name: str = Field(min_length=2, max_length=180)
    country_code: str = Field(min_length=2, max_length=2)
    registration_number: str | None = Field(default=None, max_length=80)
    postal_code: str | None = Field(default=None, max_length=24)
    address: str | None = Field(default=None, max_length=300)
    match_status: Literal["exact", "probable", "ambiguous", "not_found"]
    confidence: float = Field(ge=0, le=1)
    matched_fields: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=3, max_length=180)
    metric: str = Field(pattern=r"^[a-z0-9_.]+$", max_length=120)
    value: float | int | str | bool
    unit: str | None = Field(default=None, max_length=40)
    scale_min: float | None = None
    scale_max: float | None = None
    higher_is_better: bool | None = None
    observed_at: datetime
    fetched_at: datetime
    source_ref: str = Field(min_length=1, max_length=500)
    quality_flags: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderDescriptor
    entity_match: EntityMatch
    observations: list[Observation] = Field(default_factory=list)


class GatewayEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["privatelens.evidence.v2"] = Field(alias="schema")
    request_id: str = Field(min_length=8, max_length=180)
    generated_at: datetime
    bundles: list[EvidenceBundle] = Field(default_factory=list)


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalized(observation: Observation) -> float | None:
    value = _number(observation.value)
    if value is None:
        return None
    if observation.scale_min is None or observation.scale_max is None:
        return _clamp(value)
    span = observation.scale_max - observation.scale_min
    if span <= 0:
        return None
    normalized = (value - observation.scale_min) / span * 100
    if observation.higher_is_better is False:
        normalized = 100 - normalized
    return _clamp(normalized)


def _entity_is_resolved(bundle: EvidenceBundle) -> bool:
    match = bundle.entity_match
    matched = set(match.matched_fields)
    registration_exact = "registration_number" in matched and match.match_status == "exact"
    corroborated = (
        match.match_status in {"exact", "probable"}
        and match.confidence >= 0.95
        and "legal_name" in matched
        and bool(matched & {"registration_number", "postal_code", "address"})
    )
    return registration_exact or corroborated


def _normalized_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "company", "co"}
    return " ".join(part for part in value.split() if part not in suffixes)


def _normalized_identifier(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _entity_matches_request(bundle: EvidenceBundle, identity: CompanyIdentity) -> bool:
    match = bundle.entity_match
    fields = set(match.matched_fields)
    if match.country_code.upper() != identity.country_code:
        return False
    expected_provider_id = identity.provider_ids.get(bundle.provider.key)
    if expected_provider_id and match.provider_entity_id != expected_provider_id:
        return False
    if "registration_number" in fields and (
        not identity.registration_number
        or _normalized_identifier(match.registration_number) != _normalized_identifier(identity.registration_number)
    ):
        return False
    if "legal_name" in fields and _normalized_name(match.legal_name) != _normalized_name(identity.legal_name):
        return False
    if "postal_code" in fields and (
        not identity.postal_code
        or _normalized_identifier(match.postal_code) != _normalized_identifier(identity.postal_code)
    ):
        return False
    if "address" in fields and (
        not identity.address
        or re.sub(r"\s+", " ", (match.address or "").strip().lower())
        != re.sub(r"\s+", " ", identity.address.strip().lower())
    ):
        return False
    return True


def _fresh_observations(
    bundle: EvidenceBundle,
    metrics: set[str],
    max_age_days: int,
    now: datetime,
) -> dict[str, Observation]:
    found: dict[str, Observation] = {}
    for observation in bundle.observations:
        if observation.metric not in metrics:
            continue
        observed_at = observation.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        age_days = (now - observed_at.astimezone(timezone.utc)).total_seconds() / 86400
        if age_days < -1 or age_days > max_age_days:
            continue
        current = found.get(observation.metric)
        if current is None or observation.observed_at > current.observed_at:
            found[observation.metric] = observation
    return found


def _base_signal(
    name: str,
    score: float,
    bundle: EvidenceBundle,
    observations: list[Observation],
    display: str,
    insight: str,
    now: datetime,
) -> dict[str, Any]:
    spec = SIGNAL_SPECS[name]
    dates = [item.observed_at for item in observations]
    oldest = min(dates)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    freshness_days = max(0, int((now - oldest.astimezone(timezone.utc)).total_seconds() / 86400))
    return {
        "signal": name,
        "icon": "data",
        "category": spec["category"],
        "display": display,
        "raw_score": round(_clamp(score), 2),
        "is_simulated": False,
        "is_scored": True,
        "availability_status": "verified",
        "source_url": observations[0].source_ref,
        "insight": insight,
        "provider": bundle.provider.name,
        "provider_key": bundle.provider.key,
        "license_reference": bundle.provider.license_reference,
        "evidence_ids": [item.evidence_id for item in observations],
        "observed_at": max(dates).isoformat(),
        "freshness_days": freshness_days,
        "entity_match_confidence": bundle.entity_match.confidence,
        "entity_match_status": bundle.entity_match.match_status,
        "provider_entity_id": bundle.entity_match.provider_entity_id,
        "transform_version": "evidence-transform-1.0",
        "quality_flags": sorted({flag for item in observations for flag in item.quality_flags}),
    }


def _credit_signal(bundle: EvidenceBundle, now: datetime) -> dict[str, Any] | None:
    observations = _fresh_observations(
        bundle,
        {"creditsafe.credit_score"},
        SIGNAL_SPECS["Commercial Credit Risk"]["max_age_days"],
        now,
    )
    item = observations.get("creditsafe.credit_score")
    score = _normalized(item) if item else None
    if item is None or score is None:
        return None
    return _base_signal(
        "Commercial Credit Risk",
        score,
        bundle,
        [item],
        f"Commercial credit index {score:.0f}/100",
        "Normalized from the provider credit scale; PrivateLens applies no name-based or generated adjustment.",
        now,
    )


def _payment_signal(bundle: EvidenceBundle, now: datetime) -> dict[str, Any] | None:
    observations = _fresh_observations(
        bundle,
        {"creditsafe.payment_index", "creditsafe.days_beyond_terms"},
        SIGNAL_SPECS["B2B Payment Behavior"]["max_age_days"],
        now,
    )
    payment_index = observations.get("creditsafe.payment_index")
    days_beyond = observations.get("creditsafe.days_beyond_terms")
    if payment_index is not None:
        score = _normalized(payment_index)
        display = f"Payment index {score:.0f}/100" if score is not None else "Payment index unavailable"
        used = [payment_index]
    elif days_beyond is not None and _number(days_beyond.value) is not None:
        days = max(0, _number(days_beyond.value) or 0)
        score = _clamp(100 - days * 2.5)
        display = f"{days:.0f} days beyond terms"
        used = [days_beyond]
    else:
        return None
    if score is None:
        return None
    return _base_signal(
        "B2B Payment Behavior",
        score,
        bundle,
        used,
        display,
        "Uses verified trade-payment behavior with a fixed, versioned transformation.",
        now,
    )


def _identity_signal(bundle: EvidenceBundle, now: datetime) -> dict[str, Any] | None:
    observations = _fresh_observations(
        bundle,
        {"middesk.registration_status"},
        SIGNAL_SPECS["Business Identity & Standing"]["max_age_days"],
        now,
    )
    item = observations.get("middesk.registration_status")
    if item is None or not isinstance(item.value, str):
        return None
    status = item.value.strip().lower()
    status_scores = {"active": 100, "registered": 95, "inactive": 25, "dissolved": 10, "revoked": 5}
    score = status_scores.get(status)
    if score is None:
        return None
    return _base_signal(
        "Business Identity & Standing",
        score,
        bundle,
        [item],
        f"Registration status: {status.title()}",
        "Business standing is tied to the resolved legal entity and current registration record.",
        now,
    )


def _legal_signal(bundle: EvidenceBundle, now: datetime) -> dict[str, Any] | None:
    metrics = {
        "middesk.active_bankruptcy_count",
        "middesk.recent_lien_count_12m",
        "middesk.active_tax_lien_count",
        "middesk.defendant_litigation_count_24m",
    }
    observations = _fresh_observations(
        bundle,
        metrics,
        SIGNAL_SPECS["Liens, Bankruptcy & Litigation"]["max_age_days"],
        now,
    )
    if len(observations) < 3:
        return None
    bankruptcy = max(0, _number(observations.get("middesk.active_bankruptcy_count", {}).value) or 0) if observations.get("middesk.active_bankruptcy_count") else 0
    liens = max(0, _number(observations.get("middesk.recent_lien_count_12m", {}).value) or 0) if observations.get("middesk.recent_lien_count_12m") else 0
    tax_liens = max(0, _number(observations.get("middesk.active_tax_lien_count", {}).value) or 0) if observations.get("middesk.active_tax_lien_count") else 0
    litigation = max(0, _number(observations.get("middesk.defendant_litigation_count_24m", {}).value) or 0) if observations.get("middesk.defendant_litigation_count_24m") else 0
    score = _clamp(100 - min(100, bankruptcy * 100) - min(45, liens * 12) - min(60, tax_liens * 25) - min(35, litigation * 7))
    return _base_signal(
        "Liens, Bankruptcy & Litigation",
        score,
        bundle,
        list(observations.values()),
        f"{bankruptcy:.0f} active bankruptcies, {liens + tax_liens:.0f} recent/active liens, {litigation:.0f} defendant cases",
        "Fixed penalties are applied only to entity-resolved, recent legal records; record absence is not treated as proof of no risk.",
        now,
    )


def _cash_flow_signal(bundle: EvidenceBundle, now: datetime) -> dict[str, Any] | None:
    metrics = {
        "codat.current_ratio",
        "codat.debt_service_coverage_ratio",
        "codat.operating_cash_flow_margin",
        "codat.months_cash_on_hand",
        "codat.revenue_growth_yoy",
    }
    observations = _fresh_observations(
        bundle,
        metrics,
        SIGNAL_SPECS["Cash Flow & Liquidity"]["max_age_days"],
        now,
    )
    component_scores: list[float] = []
    if (item := observations.get("codat.current_ratio")) and (value := _number(item.value)) is not None:
        component_scores.append(_clamp(value / 2 * 100))
    if (item := observations.get("codat.debt_service_coverage_ratio")) and (value := _number(item.value)) is not None:
        component_scores.append(_clamp(value / 2 * 100))
    if (item := observations.get("codat.operating_cash_flow_margin")) and (value := _number(item.value)) is not None:
        component_scores.append(_clamp((value + 0.10) / 0.35 * 100))
    if (item := observations.get("codat.months_cash_on_hand")) and (value := _number(item.value)) is not None:
        component_scores.append(_clamp(value / 12 * 100))
    if (item := observations.get("codat.revenue_growth_yoy")) and (value := _number(item.value)) is not None:
        component_scores.append(_clamp((value + 0.20) / 0.70 * 100))
    if len(component_scores) < 3:
        return None
    score = sum(component_scores) / len(component_scores)
    return _base_signal(
        "Cash Flow & Liquidity",
        score,
        bundle,
        list(observations.values()),
        f"{len(component_scores)} consented financial metrics",
        "Computed from company-authorized accounting or banking aggregates; transaction-level data is not stored by PrivateLens.",
        now,
    )


TRANSFORMS = {
    "creditsafe": (_credit_signal, _payment_signal),
    "middesk": (_identity_signal, _legal_signal),
    "codat": (_cash_flow_signal,),
}


def unavailable_signal(name: str) -> dict[str, Any]:
    spec = SIGNAL_SPECS[name]
    provider_names = [PROVIDER_CATALOG[key]["name"] for key in spec["providers"]]
    return {
        "signal": name,
        "icon": "data",
        "category": spec["category"],
        "display": "Verified licensed evidence unavailable - not scored",
        "raw_score": 50,
        "is_simulated": True,
        "is_scored": False,
        "availability_status": "unavailable",
        "source_url": PROVIDER_CATALOG[spec["providers"][0]]["official_docs"],
        "insight": f"Requires entity-resolved evidence from {' or '.join(provider_names)}. No company value was inferred.",
        "expected_providers": provider_names,
    }


def build_licensed_signals(
    response: GatewayEvidenceResponse | None,
    identity: CompanyIdentity,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    signals: dict[str, dict[str, Any]] = {}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    if response is not None:
        for bundle in response.bundles:
            provider_key = bundle.provider.key
            if "company_intelligence" not in bundle.provider.permitted_use:
                rejected.append({"provider": provider_key, "reason": "permitted_use_missing"})
                continue
            if not _entity_is_resolved(bundle):
                rejected.append({"provider": provider_key, "reason": "entity_match_below_threshold"})
                continue
            if not _entity_matches_request(bundle, identity):
                rejected.append({"provider": provider_key, "reason": "entity_match_request_mismatch"})
                continue
            produced: list[str] = []
            for transform in TRANSFORMS[provider_key]:
                signal = transform(bundle, now)
                if signal is not None:
                    signals[signal["signal"]] = signal
                    produced.append(signal["signal"])
            accepted.append({
                "provider": provider_key,
                "provider_name": bundle.provider.name,
                "provider_entity_id": bundle.entity_match.provider_entity_id,
                "entity_match_status": bundle.entity_match.match_status,
                "entity_match_confidence": bundle.entity_match.confidence,
                "matched_fields": bundle.entity_match.matched_fields,
                "license_reference": bundle.provider.license_reference,
                "signals": produced,
                "evidence_ids": [item.evidence_id for item in bundle.observations],
                "observations": [
                    {
                        "evidence_id": item.evidence_id,
                        "metric": item.metric,
                        "value": item.value,
                        "unit": item.unit,
                        "observed_at": item.observed_at.isoformat(),
                        "fetched_at": item.fetched_at.isoformat(),
                        "source_ref": item.source_ref,
                        "quality_flags": item.quality_flags,
                    }
                    for item in bundle.observations
                ],
            })

    for name in SIGNAL_SPECS:
        signals.setdefault(name, unavailable_signal(name))

    return list(signals.values()), {
        "schema": "privatelens.evidence.audit.v1",
        "requested_entity": identity.model_dump(mode="json", exclude_none=True),
        "gateway_request_id": response.request_id if response else None,
        "gateway_generated_at": response.generated_at.isoformat() if response else None,
        "accepted_bundles": accepted,
        "rejected_bundles": rejected,
        "provider_count": len({item["provider"] for item in accepted if item["signals"]}),
    }


def evidence_hash(
    signals: list[dict[str, Any]],
    audit: dict[str, Any],
    identity: CompanyIdentity | None = None,
) -> str:
    scored = [
        {
            "signal": signal.get("signal"),
            "raw_score": signal.get("raw_score"),
            "provider_key": signal.get("provider_key"),
            "evidence_ids": signal.get("evidence_ids", []),
            "observed_at": signal.get("observed_at"),
            "transform_version": signal.get("transform_version"),
        }
        for signal in signals
        if signal.get("is_scored") and not signal.get("is_simulated")
    ]
    payload = {
        "identity": identity.model_dump(mode="json", exclude_none=True) if identity else None,
        "scored_signals": scored,
        "audit": audit,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()

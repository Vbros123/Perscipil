"""Creditsafe Connect adapter with strict entity and freshness handling."""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from config import Settings
from models import EntityRequest, EvidenceBundle, Observation


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "company", "co"}
    return " ".join(part for part in value.split() if part not in suffixes)


def _nested(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value is not None:
            return value
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CreditsafeAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self.settings.CREDITSAFE_ENABLED

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        if self._token and self._token_expires_at - time.time() > 60:
            return self._token
        async with self._token_lock:
            if self._token and self._token_expires_at - time.time() > 60:
                return self._token
            response = await client.post(
                f"{self.settings.CREDITSAFE_BASE_URL.rstrip('/')}/authenticate",
                json={
                    "username": self.settings.CREDITSAFE_USERNAME,
                    "password": self.settings.CREDITSAFE_PASSWORD,
                },
            )
            response.raise_for_status()
            token = response.json().get("token")
            if not token:
                raise RuntimeError("Creditsafe authentication response did not contain a token.")
            self._token = token
            self._token_expires_at = time.time() + 3600
            return token

    @staticmethod
    def _candidate_match(entity: EntityRequest, candidate: dict[str, Any]) -> tuple[str, float, list[str]]:
        candidate_name = candidate.get("name") or ""
        candidate_reg = str(candidate.get("regNo") or "").strip()
        candidate_address = candidate.get("address") or {}
        candidate_postal = str(candidate_address.get("postCode") or "").replace(" ", "").upper()
        requested_postal = (entity.postal_code or "").replace(" ", "").upper()

        fields: list[str] = []
        if _normalize(candidate_name) == _normalize(entity.legal_name):
            fields.append("legal_name")
        if entity.registration_number and candidate_reg.upper() == entity.registration_number.upper():
            fields.append("registration_number")
        if requested_postal and candidate_postal == requested_postal:
            fields.append("postal_code")

        if "registration_number" in fields:
            return "exact", 1.0, fields
        if {"legal_name", "postal_code"}.issubset(fields):
            return "exact", 0.99, fields
        if "legal_name" in fields:
            return "ambiguous", 0.75, fields
        return "not_found", 0.0, fields

    async def fetch(self, entity: EntityRequest, request_id: str) -> EvidenceBundle | None:
        if not self.enabled:
            return None
        # Creditsafe itself recommends regNo, or name plus postcode. Name-only
        # search is not allowed to become score evidence in this gateway.
        if not entity.registration_number and not entity.postal_code:
            return None

        async with httpx.AsyncClient(timeout=self.settings.PROVIDER_TIMEOUT, follow_redirects=False) as client:
            token = await self._authenticate(client)
            headers = {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}
            params: dict[str, Any] = {
                "countries": entity.country_code,
                "name": entity.legal_name,
                "exact": "true",
                "page": 1,
                "pageSize": 10,
            }
            if entity.registration_number:
                params["regNo"] = entity.registration_number
            if entity.postal_code:
                params["postCode"] = entity.postal_code
            search_response = await client.get(
                f"{self.settings.CREDITSAFE_BASE_URL.rstrip('/')}/companies",
                params=params,
                headers=headers,
            )
            search_response.raise_for_status()
            candidates = search_response.json().get("companies") or []
            ranked = [(self._candidate_match(entity, candidate), candidate) for candidate in candidates]
            ranked.sort(key=lambda item: item[0][1], reverse=True)
            if not ranked:
                return None
            (match_status, confidence, matched_fields), candidate = ranked[0]
            connect_id = str(candidate.get("id") or "")
            if not connect_id:
                return None

            entity_match = {
                "provider_entity_id": connect_id,
                "legal_name": candidate.get("name") or entity.legal_name,
                "country_code": candidate.get("country") or entity.country_code,
                "registration_number": candidate.get("regNo"),
                "postal_code": (candidate.get("address") or {}).get("postCode"),
                "address": (candidate.get("address") or {}).get("simpleValue"),
                "match_status": match_status,
                "confidence": confidence,
                "matched_fields": matched_fields,
            }
            if match_status != "exact":
                return EvidenceBundle(
                    provider=self._provider_descriptor(),
                    entity_match=entity_match,
                    observations=[],
                )

            report_response = await client.get(
                f"{self.settings.CREDITSAFE_BASE_URL.rstrip('/')}/companies/{connect_id}",
                headers=headers,
            )
            report_response.raise_for_status()
            report_payload = report_response.json()

        fetched_at = datetime.now(timezone.utc)
        source_ref = f"urn:creditsafe:company:{connect_id}:credit-report"
        observations = self._observations(report_payload, connect_id, fetched_at, source_ref)
        return EvidenceBundle(
            provider=self._provider_descriptor(),
            entity_match=entity_match,
            observations=observations,
        )

    def _provider_descriptor(self) -> dict[str, Any]:
        return {
            "key": "creditsafe",
            "name": "Creditsafe Connect",
            "license_reference": self.settings.CREDITSAFE_LICENSE_REFERENCE or "missing-license",
            "permitted_use": ["company_intelligence"],
        }

    @staticmethod
    def _observations(
        payload: dict[str, Any],
        connect_id: str,
        fetched_at: datetime,
        source_ref: str,
    ) -> list[Observation]:
        score = _as_number(_nested(
            payload,
            ("report", "creditScore", "currentCreditRating", "commonValue"),
            ("creditScore", "currentCreditRating", "commonValue"),
            ("report", "creditScore", "currentCreditRating", "score"),
        ))
        rating_date = _parse_datetime(_nested(
            payload,
            ("report", "creditScore", "currentCreditRating", "date"),
            ("creditScore", "currentCreditRating", "date"),
            ("report", "creditScore", "latestRatingChangeDate"),
        ))
        dbt = _as_number(_nested(
            payload,
            ("report", "paymentData", "dbt"),
            ("paymentData", "dbt"),
            ("report", "paymentData", "daysBeyondTerms"),
        ))
        payment_date = _parse_datetime(_nested(
            payload,
            ("report", "paymentData", "asOfDate"),
            ("paymentData", "asOfDate"),
            ("report", "paymentData", "date"),
        ))

        observations: list[Observation] = []
        if score is not None and rating_date is not None:
            observations.append(Observation(
                evidence_id=f"creditsafe:{connect_id}:credit:{rating_date.date().isoformat()}",
                metric="creditsafe.credit_score",
                value=score,
                scale_min=0,
                scale_max=100,
                higher_is_better=True,
                observed_at=rating_date,
                fetched_at=fetched_at,
                source_ref=source_ref,
            ))
        if dbt is not None and payment_date is not None:
            observations.append(Observation(
                evidence_id=f"creditsafe:{connect_id}:dbt:{payment_date.date().isoformat()}",
                metric="creditsafe.days_beyond_terms",
                value=dbt,
                unit="days",
                observed_at=payment_date,
                fetched_at=fetched_at,
                source_ref=source_ref,
            ))
        return observations

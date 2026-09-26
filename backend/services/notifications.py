"""Durable notification delivery; operator-approved destinations only.

Receivers MUST reject timestamps older than five minutes and persist event IDs
before acting. Retries preserve event ID; every request gets a fresh signature.
"""

import asyncio, hashlib, hmac, json, secrets, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import httpx
from sqlalchemy import select, update, or_
from core.database import SessionLocal
from core.config import get_settings
from models.organizations import Delivery, OrganizationResource


def signature(secret, timestamp, event_id, body):
    signed = str(timestamp).encode() + b"." + event_id.encode() + b"." + body
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def verify_signature(secret, timestamp, event_id, body, supplied, now=None):
    try:
        if abs((now or time.time()) - int(timestamp)) > 300:
            return False
    except (TypeError, ValueError):
        return False
    return isinstance(supplied, str) and hmac.compare_digest(signature(secret, timestamp, event_id, body), supplied)


class TestDeliveryProvider:
    """Explicit fixture provider; never selected from production configuration."""

    def __init__(self):
        self.events = {}

    async def deliver(self, channel, destination, event_id, payload):
        self.events.setdefault(event_id, {"channel": channel, "payload": payload})


class ConfiguredDeliveryProvider:
    async def deliver(self, channel, destination, event_id, payload):
        config = json.loads(get_settings().NOTIFICATION_DESTINATIONS_JSON)
        target = config.get(destination)
        if not target or target.get("channel") != channel:
            raise PermissionError("Destination is not activated")
        if channel == "email":
            from core.email import _send_email

            if get_settings().EMAIL_DELIVERY_MODE not in ("smtp", "resend"):
                raise PermissionError("Email delivery not activated")
            await asyncio.to_thread(
                _send_email,
                target["address"],
                "PrivateLens scheduled monitoring update",
                f"A material research change was detected. Event: {event_id}. Sign in to review the evidence.",
            )
            return
        if channel != "webhook":
            raise PermissionError("Unsupported delivery channel")
        url = target["url"]
        parsed = urlparse(url)
        # Destinations are provisioned by an operator, not arbitrary tenant input.
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise PermissionError("Invalid destination")
        secret = target["signing_secret"]
        if len(secret) < 32:
            raise PermissionError("Signing secret is too short")
        timestamp = str(int(time.time()))
        body = json.dumps(
            {"id": event_id, "type": "monitoring.material_change", "data": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "X-PrivateLens-Event": event_id,
            "X-PrivateLens-Timestamp": timestamp,
            "X-PrivateLens-Signature": signature(secret, timestamp, event_id, body),
            "Idempotency-Key": event_id,
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(url, content=body, headers=headers)
            if 300 <= response.status_code < 400:
                raise PermissionError("Redirects are not allowed")
            response.raise_for_status()


def enqueue_configured(db, event):
    config = json.loads(get_settings().NOTIFICATION_DESTINATIONS_JSON)
    for name, target in config.items():
        if target.get("organization_id") != event.organization_id or target.get(
            "channel"
        ) not in ("email", "webhook"):
            continue
        db.add(
            Delivery(
                organization_id=event.organization_id,
                event_id=event.id,
                channel=target["channel"],
                destination=name,
            )
        )


async def deliver_due(limit=50, provider=None):
    provider = provider or ConfiguredDeliveryProvider()
    now = datetime.now(timezone.utc)
    count = 0
    with SessionLocal() as db:
        db.execute(
            update(Delivery)
            .where(Delivery.state == "running", Delivery.lease_until < now)
            .values(state="retry", claim_token=None)
        )
        db.execute(
            update(Delivery)
            .where(Delivery.state == "retry", Delivery.attempts >= 6)
            .values(state="failed", error_code="RETRY_EXHAUSTED")
        )
        ids = list(
            db.scalars(
                select(Delivery.id)
                .where(
                    Delivery.state.in_(["queued", "retry"]),
                    Delivery.available_at <= now,
                    Delivery.attempts < 6,
                )
                .order_by(Delivery.available_at)
                .limit(limit)
            )
        )
        db.commit()
    for did in ids:
        with SessionLocal() as db:
            token = secrets.token_hex(24)
            claimed = db.execute(
                update(Delivery)
                .where(Delivery.id == did, Delivery.state.in_(["queued", "retry"]), Delivery.available_at <= datetime.now(timezone.utc), Delivery.attempts < 6)
                .values(
                    state="running",
                    claim_token=token,
                    attempts=Delivery.attempts + 1,
                    last_attempt_at=now,
                    lease_until=now + timedelta(minutes=2),
                )
            )
            db.commit()
            if not claimed.rowcount:
                continue
            row = db.get(Delivery, did)
            event = db.get(OrganizationResource, row.event_id)
            event_id = f"org-{row.organization_id}-event-{row.event_id}"
            retry_seconds = min(3600, 30 * 2**row.attempts)
            try:
                await asyncio.wait_for(
                    provider.deliver(
                        row.channel, row.destination, event_id, event.payload
                    ),
                    30,
                )
                state = "delivered"
                error = None
            except PermissionError:
                state = "failed"
                error = "DESTINATION_NOT_ACTIVATED"
            except httpx.HTTPStatusError as exc:
                state = "failed" if row.attempts >= 6 else "retry"
                error = "HTTP_" + str(exc.response.status_code)
                if exc.response.status_code in (429, 503):
                    from email.utils import parsedate_to_datetime
                    hint = exc.response.headers.get("Retry-After", "")
                    try:
                        delay = float(hint) if hint.isdecimal() else (parsedate_to_datetime(hint) - datetime.now(timezone.utc)).total_seconds()
                        retry_seconds = max(retry_seconds, min(86400, max(0, delay)))
                    except (ValueError, TypeError, OverflowError):
                        pass
            except Exception:
                state = "failed" if row.attempts >= 6 else "retry"
                error = "DELIVERY_FAILED"
            db.execute(
                update(Delivery)
                .where(
                    Delivery.id == did,
                    Delivery.claim_token == token,
                    Delivery.state == "running",
                )
                .values(
                    state=state,
                    error_code=error,
                    claim_token=None,
                    lease_until=None,
                    delivered_at=datetime.now(timezone.utc)
                    if state == "delivered"
                    else None,
                    available_at=datetime.now(timezone.utc)
                    + timedelta(seconds=retry_seconds),
                )
            )
            db.commit()
            count += 1
    return count

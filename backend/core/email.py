"""Transactional email delivery."""
from __future__ import annotations

from html import escape
import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

import httpx

from core.brand import NAME
from core.config import get_settings

logger = logging.getLogger("privatelens.email")
settings = get_settings()


class EmailDeliveryError(RuntimeError):
    pass


def _send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if html_body:
        logo_url = escape(f"{settings.APP_PUBLIC_URL.rstrip('/')}/brand/perspicil-32.png", quote=True)
        html_body = (
            f'<div style="font-family:Arial,sans-serif;color:#182d2a">'
            f'<p><img src="{logo_url}" width="32" height="32" alt="" '
            f'style="vertical-align:middle;margin-right:8px" />'
            f'<strong>{escape(NAME)}</strong></p>{html_body}</div>'
        )
    if settings.EMAIL_DELIVERY_MODE == "disabled":
        return

    if settings.EMAIL_DELIVERY_MODE == "console":
        logger.info("email.console delivery suppressed; configure a local mail sink for development")
        return

    if settings.EMAIL_DELIVERY_MODE == "resend":
        payload = {
            "from": f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "text": text_body,
        }
        if html_body:
            payload["html"] = html_body
        try:
            response = httpx.post(
                settings.RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                timeout=15,
            )
            response.raise_for_status()
            return
        except Exception as exc:
            raise EmailDeliveryError("Failed to deliver transactional email through Resend.") from exc

    if not settings.SMTP_HOST:
        raise EmailDeliveryError("SMTP_HOST is required for SMTP email delivery.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        raise EmailDeliveryError("Failed to deliver transactional email.") from exc


def send_password_reset_email(to_email: str, token: str) -> None:
    query = urlencode({"token": token})
    reset_url = f"{settings.APP_PUBLIC_URL.rstrip('/')}/reset-password?{query}"
    text = (
        f"Reset your {NAME} password using this secure link:\n\n"
        f"{reset_url}\n\n"
        "This link expires soon. If you did not request it, ignore this email."
    )
    html = (
        f"<p>Reset your {NAME} password using this secure link:</p>"
        f'<p><a href="{reset_url}">Reset password</a></p>'
        "<p>This link expires soon. If you did not request it, ignore this email.</p>"
    )
    _send_email(to_email, f"Reset your {NAME} password", text, html)


def send_email_verification(to_email: str, token: str) -> None:
    query = urlencode({"token": token})
    verify_url = f"{settings.APP_PUBLIC_URL.rstrip('/')}/verify-email?{query}"
    text = (
        f"Verify your {NAME} email using this secure link:\n\n"
        f"{verify_url}\n\n"
        f"If you did not create a {NAME} account, ignore this email."
    )
    html = (
        f"<p>Verify your {NAME} email using this secure link:</p>"
        f'<p><a href="{verify_url}">Verify email</a></p>'
        f"<p>If you did not create a {NAME} account, ignore this email.</p>"
    )
    _send_email(to_email, f"Verify your {NAME} email", text, html)

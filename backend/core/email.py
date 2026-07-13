"""Transactional email delivery."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from core.config import get_settings

logger = logging.getLogger("privatelens.email")
settings = get_settings()


class EmailDeliveryError(RuntimeError):
    pass


def _send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if settings.EMAIL_DELIVERY_MODE == "disabled":
        return

    if settings.EMAIL_DELIVERY_MODE == "console":
        logger.info("email.console to=%s subject=%s body=%s", to_email, subject, text_body)
        return

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
        "Reset your PrivateLens password using this secure link:\n\n"
        f"{reset_url}\n\n"
        "This link expires soon. If you did not request it, ignore this email."
    )
    html = (
        "<p>Reset your PrivateLens password using this secure link:</p>"
        f'<p><a href="{reset_url}">Reset password</a></p>'
        "<p>This link expires soon. If you did not request it, ignore this email.</p>"
    )
    _send_email(to_email, "Reset your PrivateLens password", text, html)


def send_email_verification(to_email: str, token: str) -> None:
    query = urlencode({"token": token})
    verify_url = f"{settings.APP_PUBLIC_URL.rstrip('/')}/verify-email?{query}"
    text = (
        "Verify your PrivateLens email using this secure link:\n\n"
        f"{verify_url}\n\n"
        "If you did not create a PrivateLens account, ignore this email."
    )
    html = (
        "<p>Verify your PrivateLens email using this secure link:</p>"
        f'<p><a href="{verify_url}">Verify email</a></p>'
        "<p>If you did not create a PrivateLens account, ignore this email.</p>"
    )
    _send_email(to_email, "Verify your PrivateLens email", text, html)

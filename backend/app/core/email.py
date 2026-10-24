"""Transactional SMTP email delivery for verification and password recovery."""
import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailDeliveryNotConfigured(RuntimeError):
    """Raised when SMTP settings are missing."""


def _send_sync(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    required = (settings.SMTP_HOST, settings.SMTP_FROM_EMAIL)
    if not all(required):
        raise EmailDeliveryNotConfigured("SMTP_HOST and SMTP_FROM_EMAIL must be configured")
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
        smtp.send_message(message)


async def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    await asyncio.to_thread(_send_sync, to_email, subject, text_body, html_body)

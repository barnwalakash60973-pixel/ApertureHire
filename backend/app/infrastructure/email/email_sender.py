"""
Email sending - NO LLM, just SMTP. Two implementations:
  - SMTPEmailSender: real delivery via smtplib, used when SMTP_* env vars
    are configured.
  - ConsoleEmailSender: logs the email instead of sending it. Used
    automatically when no SMTP credentials are configured, so the whole
    workflow (screening -> shortlist email -> assignment -> approval ->
    assignment email) is fully runnable/testable without real credentials.
    Swap to real delivery just by setting the SMTP_* env vars - no code
    change needed.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailSender(Protocol):
    def send(self, to_email: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Fallback used when SMTP isn't configured - logs instead of sending.
    Lets the whole recruitment workflow run end-to-end locally without
    real email credentials."""

    def send(self, to_email: str, subject: str, body: str) -> None:
        logger.info(
            "[EMAIL NOT SENT - no SMTP configured] To: %s | Subject: %s\n%s",
            to_email, subject, body,
        )


class SMTPEmailSender:
    """Real delivery via smtplib. Configure SMTP_HOST/PORT/USERNAME/
    PASSWORD/FROM_EMAIL in .env to activate (see .env.example)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, to_email: str, subject: str, body: str) -> None:
        message = MIMEMultipart()
        message["From"] = self._settings.smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))
        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.set_debuglevel(1)
                server.starttls()
                server.login(self._settings.smtp_username, self._settings.smtp_password)
                server.sendmail(self._settings.smtp_from_email, to_email, message.as_string())

            logger.info("Email sent to %s | Subject: %s", to_email, subject)
        except Exception:
            logger.exception("SMTP send failed")
            raise

def get_email_sender(settings: Settings) -> EmailSender:
    """Picks SMTP or console fallback based on whether credentials are
    configured. This is the ONLY place that decision is made."""
    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        return SMTPEmailSender(settings)
    logger.warning(
        "SMTP not configured (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD) - "
        "emails will be logged instead of sent. See .env.example."
    )
    return ConsoleEmailSender()

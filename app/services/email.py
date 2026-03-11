from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_auth_code(self, *, email: str, full_name: str, code: str, purpose: str) -> None:
        subject = "RistoAI verification code"
        body = (
            f"Hello {full_name},\n\n"
            f"Your RistoAI {purpose.replace('_', ' ')} code is: {code}\n\n"
            "This code expires in 10 minutes.\n"
            "If you did not request this, you can ignore this email.\n"
        )
        if not self.settings.smtp_enabled:
            logger.info("SMTP disabled. Verification code for %s (%s): %s", email, purpose, code)
            return
        await asyncio.to_thread(self._send_email, email, subject, body)

    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        if self.settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port) as server:
                server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
            if self.settings.smtp_use_tls:
                server.starttls()
            server.login(self.settings.smtp_username, self.settings.smtp_password)
            server.send_message(message)

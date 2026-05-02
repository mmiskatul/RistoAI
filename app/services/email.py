from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

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
        html_body = (
            f"<p>Hello {full_name},</p>"
            f"<p>Your RistoAI {purpose.replace('_', ' ')} code is: "
            f"<strong style=\"font-size:20px;letter-spacing:2px;\">{code}</strong></p>"
            "<p>This code expires in 10 minutes.</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        )
        if self.settings.resend_enabled:
            await self._send_email_via_resend(email, subject, body, html_body)
            return
        if self.settings.smtp_enabled:
            await asyncio.to_thread(self._send_email_via_smtp, email, subject, body)
            return
        logger.info("Email provider disabled. Verification code for %s (%s): %s", email, purpose, code)

    async def _send_email_via_resend(self, to_email: str, subject: str, text_body: str, html_body: str) -> None:
        payload = {
            "from": f"{self.settings.resend_from_name} <{self.settings.resend_from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.resend_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self.settings.resend_base_url, timeout=30.0) as client:
            response = await client.post("/emails", headers=headers, json=payload)
            response.raise_for_status()

    def _send_email_via_smtp(self, to_email: str, subject: str, body: str) -> None:
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

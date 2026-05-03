from __future__ import annotations

import logging

import httpx

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_auth_code(self, *, email: str, full_name: str, code: str, purpose: str) -> None:
        recipient_name = full_name.strip() or "there"
        subject = "Your RistoAI Verification Code"
        body = (
            f"Hello {recipient_name},\n\n"
            "Your verification code for RistoAI is:\n\n"
            f"{code}\n\n"
            "Please enter this code to complete your account verification.\n\n"
            "This code expires in 10 minutes.\n\n"
            "If you did not request this code, you can ignore this email.\n\n"
            "Best regards,\n"
            "RistoAI Team"
        )
        html_body = (
            "<div style=\"margin:0;padding:24px;background:#f5f7fa;font-family:Arial,sans-serif;color:#1f2937;\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"border-collapse:collapse;\">"
            "<tr><td align=\"center\">"
            "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:560px;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;\">"
            "<tr><td style=\"padding:24px 32px 12px;font-size:22px;font-weight:700;color:#111827;\">RistoAI</td></tr>"
            f"<tr><td style=\"padding:0 32px 16px;font-size:14px;line-height:1.6;color:#374151;\">Hello {recipient_name},</td></tr>"
            "<tr><td style=\"padding:0 32px 16px;font-size:14px;line-height:1.6;color:#374151;\">Your verification code for RistoAI is:</td></tr>"
            "<tr><td style=\"padding:0 32px 20px;\">"
            "<div style=\"border:1px solid #d1d5db;background:#f9fafb;padding:16px 20px;text-align:center;\">"
            f"<div style=\"font-size:32px;line-height:1.2;font-weight:700;letter-spacing:6px;color:#111827;\">{code}</div>"
            "</div>"
            "</td></tr>"
            "<tr><td style=\"padding:0 32px 12px;font-size:14px;line-height:1.6;color:#374151;\">Please enter this code to complete your account verification.</td></tr>"
            "<tr><td style=\"padding:0 32px 12px;font-size:14px;line-height:1.6;color:#374151;\">This code will expire in 10 minutes.</td></tr>"
            "<tr><td style=\"padding:0 32px 24px;font-size:14px;line-height:1.6;color:#374151;\">If you did not request this code, you can safely ignore this email.</td></tr>"
            "<tr><td style=\"padding:0 32px 24px;font-size:14px;line-height:1.6;color:#374151;\">Best regards,<br /><strong>RistoAI Team</strong></td></tr>"
            "<tr><td style=\"padding:16px 32px;border-top:1px solid #e5e7eb;font-size:12px;line-height:1.6;color:#6b7280;\">This is an automated account security message from RistoAI.</td></tr>"
            "</table>"
            "</td></tr>"
            "</table>"
            "</div>"
        )
        if self.settings.resend_enabled:
            await self._send_email_via_resend(email, subject, body, html_body)
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

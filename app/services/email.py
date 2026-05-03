from __future__ import annotations

import logging

import httpx

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_auth_code(self, *, email: str, full_name: str, code: str, purpose: str) -> None:
        purpose_label = purpose.replace('_', ' ').strip().title()
        subject = f"Your RistoAI Verification Code"
        body = (
            f"Hello {full_name},\n\n"
            f"We received a request for {purpose_label.lower()} on your RistoAI account.\n\n"
            f"Verification code: {code}\n\n"
            "This code will expire in 10 minutes.\n\n"
            "For your security, do not share this code with anyone.\n"
            "If you did not request this, you can safely ignore this email.\n\n"
            "RistoAI\n"
            "Restaurant operations, simplified."
        )
        html_body = (
            "<div style=\"margin:0;padding:32px 16px;background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#172033;\">"
            "<div style=\"max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e6eaf2;border-radius:18px;overflow:hidden;\">"
            "<div style=\"padding:28px 32px;background:linear-gradient(135deg,#fff4ec 0%,#ffffff 100%);border-bottom:1px solid #eef2f7;\">"
            "<div style=\"font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#fa8c4c;margin-bottom:10px;\">RistoAI Security</div>"
            "<div style=\"font-size:28px;line-height:1.2;font-weight:800;color:#172033;\">Verify your account</div>"
            f"<div style=\"margin-top:10px;font-size:14px;line-height:1.7;color:#5f6b7a;\">We received a request for {purpose_label.lower()} on your RistoAI account. Use the verification code below to continue.</div>"
            "</div>"
            "<div style=\"padding:32px;\">"
            f"<p style=\"margin:0 0 16px;font-size:15px;line-height:1.7;color:#172033;\">Hello {full_name},</p>"
            "<div style=\"margin:22px 0;padding:22px 20px;border:1px solid #ffd7bf;border-radius:16px;background:#fff8f3;text-align:center;\">"
            "<div style=\"font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#fa8c4c;margin-bottom:8px;\">Verification Code</div>"
            f"<div style=\"font-size:34px;font-weight:800;letter-spacing:6px;color:#172033;\">{code}</div>"
            "</div>"
            "<p style=\"margin:0 0 12px;font-size:14px;line-height:1.7;color:#5f6b7a;\">This code will expire in <strong>10 minutes</strong>.</p>"
            "<p style=\"margin:0 0 12px;font-size:14px;line-height:1.7;color:#5f6b7a;\">For your security, do not share this code with anyone.</p>"
            "<p style=\"margin:0;font-size:14px;line-height:1.7;color:#5f6b7a;\">If you did not request this, you can safely ignore this email.</p>"
            "</div>"
            "<div style=\"padding:18px 32px;border-top:1px solid #eef2f7;background:#fbfcfe;font-size:12px;line-height:1.6;color:#7b8794;\">"
            "<strong style=\"color:#172033;\">RistoAI</strong><br/>Restaurant operations, simplified."
            "</div>"
            "</div>"
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

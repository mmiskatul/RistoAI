from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config.settings import get_settings


class OpenAIOperationsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key) and not self.settings.testing

    async def extract_invoice(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._fallback_invoice(file_name=file_name)

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract the supplier invoice into JSON with keys: supplier_name, invoice_number, "
                                "invoice_date, total_amount, currency, ai_summary, and line_items. "
                                "Each line item must include product_name, quantity, unit_price, total_price. "
                                "Return only JSON."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": f"Filename: {file_name}. Content type: {content_type}."},
                        {
                            "type": "input_file",
                            "filename": file_name,
                            "file_data": base64.b64encode(file_bytes).decode("utf-8"),
                        },
                    ],
                },
            ],
        }
        response_payload = await self._responses_create(payload)
        parsed = self._try_parse_json(response_payload.get("output_text", ""))
        if parsed:
            return parsed
        return self._fallback_invoice(file_name=file_name)

    async def generate_chat_reply(
        self,
        *,
        prompt: str,
        metrics_context: dict[str, Any],
        recent_messages: Sequence[dict[str, Any]],
    ) -> str:
        if not self.enabled:
            revenue = metrics_context.get("revenue_total", 0.0)
            expenses = metrics_context.get("expenses_total", 0.0)
            return (
                f"Current revenue is EUR {revenue:,.2f} and expenses are EUR {expenses:,.2f}. "
                f"Focus on supplier spend, daily cash reconciliation, and the weakest weekday trend."
            )

        transcript = "\n".join(f"{item['role']}: {item['message']}" for item in recent_messages[-6:])
        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You are an operations copilot for a restaurant back office mobile app. "
                                "Keep replies concise, practical, and grounded in the supplied metrics."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Metrics context: {json.dumps(metrics_context)}\n"
                                f"Recent messages:\n{transcript}\n"
                                f"User question: {prompt}"
                            ),
                        }
                    ],
                },
            ],
        }
        response_payload = await self._responses_create(payload)
        return response_payload.get("output_text") or "I could not generate a response."

    async def _responses_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.settings.openai_base_url, timeout=45.0) as client:
            response = await client.post(
                "/responses",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            data["output_text"] = self._extract_output_text(data)
            return data

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        text_chunks: list[str] = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_chunks.append(content.get("text", ""))
        return "\n".join(chunk for chunk in text_chunks if chunk).strip()

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any] | None:
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _fallback_invoice(*, file_name: str) -> dict[str, Any]:
        stem = file_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        return {
            "supplier_name": "Fresh Food Supplier Ltd",
            "invoice_number": "INV-2045",
            "invoice_date": datetime(2026, 3, 10, tzinfo=UTC).date().isoformat(),
            "total_amount": 165.0,
            "currency": "EUR",
            "ai_summary": f"Fallback extraction generated for {stem}.",
            "line_items": [
                {"product_name": "Tomato Sauce", "quantity": 10, "unit_price": 5.0, "total_price": 50.0},
                {"product_name": "Cheese", "quantity": 5, "unit_price": 8.0, "total_price": 40.0},
                {"product_name": "Chicken", "quantity": 10, "unit_price": 6.0, "total_price": 60.0},
            ],
        }

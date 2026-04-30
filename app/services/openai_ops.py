from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, ClassVar

import httpx

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class OpenAIOperationsService:
    _CACHE_TTL_SECONDS: ClassVar[float] = 60.0
    _generation_cache: ClassVar[dict[str, tuple[float, Any]]] = {}
    _inflight_generations: ClassVar[dict[str, asyncio.Task[Any]]] = {}

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openai_api_key) and not self.settings.testing

    @staticmethod
    def _resolve_language(language: str | None) -> str:
        candidate = str(language or "").strip().lower()
        return "it" if candidate.startswith("it") else "en"

    @staticmethod
    def _build_attachment_note(*, summary: str | None, language: str) -> str:
        if not summary:
            return ""
        if language == "it":
            return f" Documento allegato: {summary}"
        return f" Attached document: {summary}"

    def _build_chat_fallback_reply(
        self,
        *,
        prompt: str,
        language: str,
        metrics_context: dict[str, Any],
        attachment_context: dict[str, Any] | None = None,
    ) -> str:
        revenue = float(metrics_context.get("revenue_total", 0.0) or 0.0)
        expenses = float(metrics_context.get("expenses_total", 0.0) or 0.0)
        profit = revenue - expenses
        attachment_note = self._build_attachment_note(
            summary=(attachment_context or {}).get("summary"),
            language=language,
        )
        if language == "it":
            return (
                f"Panoramica attuale: ricavi EUR {revenue:,.2f}, spese EUR {expenses:,.2f}, "
                f"profitto stimato EUR {profit:,.2f}. "
                f"In base alla tua richiesta \"{prompt}\", ti consiglio di controllare la voce di costo piu alta, "
                f"verificare i giorni con ricavi piu bassi e riconciliare i movimenti di cassa."
                f"{attachment_note}"
            )
        return (
            f"Current snapshot: revenue EUR {revenue:,.2f}, expenses EUR {expenses:,.2f}, "
            f"estimated profit EUR {profit:,.2f}. "
            f"Based on your request \"{prompt}\", focus on the highest cost area, review the lowest-revenue days, "
            f"and reconcile cash movements."
            f"{attachment_note}"
        )

    async def extract_invoice(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._fallback_invoice(file_name=file_name)

        try:
            payload = await self._build_invoice_payload(
                file_name=file_name,
                content_type=content_type,
                file_bytes=file_bytes,
            )
            response_payload = await self._responses_create(payload)
            parsed = self._try_parse_json(response_payload.get("output_text", ""))
            if parsed:
                return parsed
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenAI invoice extraction rejected request for %s (%s): %s", file_name, content_type, exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI invoice extraction failed for %s", file_name, exc_info=exc)
        return self._fallback_invoice(file_name=file_name)

    async def generate_business_insight(
        self,
        *,
        analytics_context: dict[str, Any],
        fallback_title: str,
        fallback_subtitle: str,
    ) -> dict[str, str]:
        if not self.enabled:
            return {"title": fallback_title, "subtitle": fallback_subtitle}

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You generate one concise restaurant analytics banner from structured business metrics. "
                                "Return only valid JSON with keys title and subtitle. "
                                "The title must start with 'Optimization Tip:'. "
                                "Be specific, numeric when possible, and grounded only in the supplied data."
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
                                f"Analytics context: {json.dumps(analytics_context)}\n"
                                f"Fallback title: {fallback_title}\n"
                                f"Fallback subtitle: {fallback_subtitle}\n"
                                "Generate the strongest single optimization insight banner."
                            ),
                        }
                    ],
                },
            ],
        }
        cache_key = self._generation_cache_key(
            "business_insight",
            {
                "analytics_context": analytics_context,
                "fallback_title": fallback_title,
                "fallback_subtitle": fallback_subtitle,
            },
        )

        async def _generate() -> dict[str, str]:
            try:
                response_payload = await self._responses_create(payload)
                parsed = self._try_parse_json(response_payload.get("output_text", ""))
                if isinstance(parsed, dict):
                    title = str(parsed.get("title") or "").strip()
                    subtitle = str(parsed.get("subtitle") or "").strip()
                    if title and subtitle:
                        if not title.startswith("Optimization Tip:"):
                            title = f"Optimization Tip: {title}"
                        return {"title": title, "subtitle": subtitle}
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("OpenAI business insight rate limited; using fallback insight.")
                else:
                    logger.exception("OpenAI business insight generation failed", exc_info=exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("OpenAI business insight generation failed", exc_info=exc)
            return {"title": fallback_title, "subtitle": fallback_subtitle}

        return await self._run_cached_generation(cache_key, _generate)

    async def generate_supplier_alerts(
        self,
        *,
        analytics_context: dict[str, Any],
        fallback_alerts: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        if not self.enabled:
            return fallback_alerts

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You generate concise supplier price alerts for a restaurant analytics dashboard from structured metrics. "
                                "Return only valid JSON with key alerts. "
                                "alerts must be an array of 1 to 3 objects, each with title and subtitle. "
                                "Keep each alert short, numeric when possible, and grounded only in the supplied data."
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
                                f"Supplier analytics context: {json.dumps(analytics_context)}\n"
                                f"Fallback alerts: {json.dumps(fallback_alerts)}\n"
                                "Generate the strongest supplier price alerts for the dashboard."
                            ),
                        }
                    ],
                },
            ],
        }
        cache_key = self._generation_cache_key(
            "supplier_alerts",
            {
                "analytics_context": analytics_context,
                "fallback_alerts": fallback_alerts,
            },
        )

        async def _generate() -> list[dict[str, str]]:
            try:
                response_payload = await self._responses_create(payload)
                parsed = self._try_parse_json(response_payload.get("output_text", ""))
                if isinstance(parsed, dict):
                    alerts = parsed.get("alerts")
                    if isinstance(alerts, list):
                        normalized: list[dict[str, str]] = []
                        for item in alerts[:3]:
                            if not isinstance(item, dict):
                                continue
                            title = str(item.get("title") or "").strip()
                            subtitle = str(item.get("subtitle") or "").strip()
                            if title and subtitle:
                                normalized.append({"title": title, "subtitle": subtitle})
                        if normalized:
                            return normalized
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("OpenAI supplier alerts rate limited; using fallback alerts.")
                else:
                    logger.exception("OpenAI supplier alert generation failed", exc_info=exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("OpenAI supplier alert generation failed", exc_info=exc)
            return fallback_alerts

        return await self._run_cached_generation(cache_key, _generate)

    async def generate_restaurant_insight(
        self,
        *,
        metrics_context: dict[str, Any],
        fallback_insight: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.enabled:
            return fallback_insight

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You generate the primary real-time restaurant operations insight for a mobile app. "
                                "Return only valid JSON with keys title, summary, priority, metric_value, metric_caption, "
                                "root_causes, and recommended_actions. "
                                "priority must be one of high, medium, low. "
                                "root_causes must be exactly 3 short strings. "
                                "recommended_actions must be exactly 3 objects with title and description. "
                                "Be specific, practical, and grounded only in the supplied metrics."
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
                                f"Fallback insight: {json.dumps(fallback_insight)}\n"
                                "Generate the strongest current insight that matches what a restaurant owner expects "
                                "to see in the frontend right now."
                            ),
                        }
                    ],
                },
            ],
        }
        cache_key = self._generation_cache_key(
            "restaurant_insight",
            {
                "metrics_context": metrics_context,
                "fallback_insight": fallback_insight,
            },
        )

        async def _generate() -> dict[str, Any]:
            try:
                response_payload = await self._responses_create(payload)
                parsed = self._try_parse_json(response_payload.get("output_text", ""))
                if isinstance(parsed, dict):
                    return self._normalize_restaurant_insight(parsed, fallback_insight)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("OpenAI restaurant insight rate limited; using fallback insight.")
                else:
                    logger.exception("OpenAI restaurant insight generation failed", exc_info=exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("OpenAI restaurant insight generation failed", exc_info=exc)
            return fallback_insight

        return await self._run_cached_generation(cache_key, _generate)

    @staticmethod
    def _normalize_restaurant_insight(parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(fallback)
        title = str(parsed.get("title") or "").strip()
        summary = str(parsed.get("summary") or "").strip()
        priority = str(parsed.get("priority") or "").strip().lower()
        metric_value = str(parsed.get("metric_value") or "").strip()
        metric_caption = str(parsed.get("metric_caption") or "").strip()

        if title:
            normalized["title"] = title[:120]
        if summary:
            normalized["summary"] = summary[:240]
        if priority in {"high", "medium", "low"}:
            normalized["priority"] = priority
        if metric_value:
            normalized["metric_value"] = metric_value[:32]
        if metric_caption:
            normalized["metric_caption"] = metric_caption[:80]

        root_causes = parsed.get("root_causes")
        if isinstance(root_causes, list):
            causes = [str(item).strip()[:120] for item in root_causes if str(item).strip()]
            if causes:
                normalized["root_causes"] = (causes + fallback.get("root_causes", []))[:3]

        recommended_actions = parsed.get("recommended_actions")
        if isinstance(recommended_actions, list):
            actions: list[dict[str, str]] = []
            for item in recommended_actions:
                if not isinstance(item, dict):
                    continue
                action_title = str(item.get("title") or "").strip()
                action_description = str(item.get("description") or "").strip()
                if action_title and action_description:
                    actions.append(
                        {
                            "title": action_title[:80],
                            "description": action_description[:160],
                        }
                    )
            if actions:
                normalized["recommended_actions"] = (actions + fallback.get("recommended_actions", []))[:3]

        return normalized

    async def generate_chat_reply(
        self,
        *,
        prompt: str,
        language: str = "en",
        metrics_context: dict[str, Any],
        recent_messages: Sequence[dict[str, Any]],
        attachment_context: dict[str, Any] | None = None,
    ) -> str:
        resolved_language = self._resolve_language(language)
        if not self.enabled:
            return self._build_chat_fallback_reply(
                prompt=prompt,
                language=resolved_language,
                metrics_context=metrics_context,
                attachment_context=attachment_context,
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
                            "You are an operations copilot for a restaurant back office app. "
                                "Keep replies concise, practical, and grounded in the supplied metrics. "
                                f"Always answer in {'Italian' if resolved_language == 'it' else 'English'}."
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
                                f"Attachment context: {json.dumps(attachment_context) if attachment_context else "none"}\n"
                                f"User question: {prompt}"
                            ),
                        }
                    ],
                },
            ],
        }
        try:
            response_payload = await self._responses_create(payload)
            output_text = str(response_payload.get("output_text") or "").strip()
            if output_text:
                return output_text
            return self._build_chat_fallback_reply(
                prompt=prompt,
                language=resolved_language,
                metrics_context=metrics_context,
                attachment_context=attachment_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI chat generation failed", exc_info=exc)
            return self._build_chat_fallback_reply(
                prompt=prompt,
                language=resolved_language,
                metrics_context=metrics_context,
                attachment_context=attachment_context,
            )

    async def summarize_chat_attachment(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        language: str = "en",
    ) -> dict[str, str]:
        resolved_language = self._resolve_language(language)
        fallback = self._fallback_attachment_summary(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
            language=resolved_language,
        )
        if not self.enabled:
            return fallback

        user_content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Filename: {file_name}. Content type: {content_type}. "
                    f"Summarize this attachment for restaurant operations chat in "
                    f"{'Italian' if resolved_language == 'it' else 'English'}."
                ),
            }
        ]
        if content_type.startswith("image/"):
            data_url = f"data:{content_type};base64,{base64.b64encode(file_bytes).decode('utf-8')}"
            user_content.append({"type": "input_image", "image_url": data_url, "detail": "high"})
        elif content_type in {"text/csv", "application/csv", "text/plain"}:
            user_content.append({"type": "input_text", "text": file_bytes.decode("utf-8", errors="replace")[:12000]})
        else:
            file_id = await self._upload_file(file_name=file_name, file_bytes=file_bytes)
            user_content.append({"type": "input_file", "file_id": file_id})

        payload = {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Return only valid JSON with keys title and summary. "
                                "Summarize the attached restaurant-related document briefly and practically. "
                                f"Return the title and summary in {'Italian' if resolved_language == 'it' else 'English'}. "
                                "Do not invent missing facts."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        try:
            response_payload = await self._responses_create(payload)
            parsed = self._try_parse_json(response_payload.get("output_text", ""))
            if isinstance(parsed, dict):
                title = str(parsed.get("title") or "").strip()
                summary = str(parsed.get("summary") or "").strip()
                if title and summary:
                    return {"title": title, "summary": summary}
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI attachment summarization failed", exc_info=exc)
        return fallback

    async def _responses_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.settings.openai_base_url, timeout=45.0) as client:
            headers = {
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            }
            for attempt in range(3):
                response = await client.post("/responses", headers=headers, json=payload)
                if response.status_code != 429:
                    response.raise_for_status()
                    data = response.json()
                    data["output_text"] = self._extract_output_text(data)
                    return data

                retry_after_header = response.headers.get("retry-after")
                try:
                    retry_after = float(retry_after_header) if retry_after_header else 0.0
                except ValueError:
                    retry_after = 0.0
                if attempt == 2:
                    response.raise_for_status()
                await asyncio.sleep(max(retry_after, 0.5 * (attempt + 1)))

            raise RuntimeError("OpenAI responses request retry loop exited unexpectedly")

    @classmethod
    def _generation_cache_key(cls, prefix: str, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    @classmethod
    async def _run_cached_generation(
        cls,
        cache_key: str,
        generator: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = time.monotonic()
        cached = cls._generation_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

        inflight = cls._inflight_generations.get(cache_key)
        if inflight is not None:
            return await inflight

        task = asyncio.create_task(generator())
        cls._inflight_generations[cache_key] = task
        try:
            result = await task
            cls._generation_cache[cache_key] = (time.monotonic() + cls._CACHE_TTL_SECONDS, result)
            return result
        finally:
            current = cls._inflight_generations.get(cache_key)
            if current is task:
                cls._inflight_generations.pop(cache_key, None)

    async def _upload_file(self, *, file_name: str, file_bytes: bytes) -> str:
        async with httpx.AsyncClient(base_url=self.settings.openai_base_url, timeout=45.0) as client:
            response = await client.post(
                "/files",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                data={"purpose": "user_data"},
                files={"file": (file_name, file_bytes)},
            )
            response.raise_for_status()
            return response.json()["id"]

    async def _build_invoice_payload(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        system_prompt = (
            "Classify the uploaded restaurant finance document and extract it into JSON. "
            "Return only valid JSON with keys: "
            "document_type, document_label, counterparty_name, supplier_name, invoice_number, "
            "invoice_date, total_amount, currency, expense_amount, cash_amount, revenue_amount, "
            "profit_amount, ai_summary, and line_items. "
            "document_type must be one of expense, cash, revenue, profit, unknown. "
            "Use expense for supplier invoices, bills, and purchase receipts. "
            "Use cash for bank deposits, till counts, cash movement, or cash reconciliation documents. "
            "Use revenue for sales reports, receipts, POS summaries, or turnover documents. "
            "Use profit for P&L, income statement, margin report, or documents explicitly showing profit. "
            "Each line item must include product_name, quantity, unit_price, total_price. "
            "Use 0 for missing numeric fields and [] for missing line_items."
        )
        user_content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Filename: {file_name}. Content type: {content_type}. "
                    "Extract the document classification and any expense, cash, revenue, or profit values."
                ),
            }
        ]

        if content_type.startswith("image/"):
            data_url = f"data:{content_type};base64,{base64.b64encode(file_bytes).decode('utf-8')}"
            user_content.append({"type": "input_image", "image_url": data_url, "detail": "high"})
        elif content_type in {"text/csv", "application/csv"}:
            csv_text = file_bytes.decode("utf-8", errors="replace")
            user_content.append({"type": "input_text", "text": f"CSV invoice content:\n{csv_text[:12000]}"})
        else:
            file_id = await self._upload_file(file_name=file_name, file_bytes=file_bytes)
            user_content.append({"type": "input_file", "file_id": file_id})

        return {
            "model": self.settings.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }

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
    def _fallback_attachment_summary(
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        language: str = "en",
    ) -> dict[str, str]:
        stem = file_name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title() or 'Uploaded File'
        if content_type in {'text/csv', 'application/csv'}:
            preview = file_bytes.decode('utf-8', errors='replace').strip().splitlines()[:3]
            snippet = ' | '.join(line[:80] for line in preview if line)
            if language == "it":
                summary = (
                    f'Allegato CSV caricato. Anteprima: {snippet}'
                    if snippet else
                    'Allegato CSV caricato per la revisione.'
                )
            else:
                summary = f'CSV attachment uploaded. Preview: {snippet}' if snippet else 'CSV attachment uploaded for review.'
        elif content_type == 'text/plain':
            preview = file_bytes.decode('utf-8', errors='replace').strip()[:160]
            if language == "it":
                summary = (
                    f'Allegato di testo caricato. Anteprima: {preview}'
                    if preview else
                    'Allegato di testo caricato per la revisione.'
                )
            else:
                summary = f'Text attachment uploaded. Preview: {preview}' if preview else 'Text attachment uploaded for review.'
        elif content_type == 'application/pdf':
            summary = 'Documento PDF caricato per la revisione del ristorante.' if language == "it" else 'PDF document uploaded for restaurant review.'
        elif content_type.startswith('image/'):
            summary = 'Immagine caricata per la revisione del ristorante.' if language == "it" else 'Image attachment uploaded for restaurant review.'
        else:
            summary = 'Documento caricato per la revisione del ristorante.' if language == "it" else 'Document attachment uploaded for restaurant review.'
        return {'title': stem, 'summary': summary}

    @staticmethod
    def _fallback_invoice(*, file_name: str) -> dict[str, Any]:
        stem = file_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
        return {
            "document_type": "expense",
            "document_label": "Expense",
            "counterparty_name": "Fresh Food Supplier Ltd",
            "supplier_name": "Fresh Food Supplier Ltd",
            "invoice_number": "INV-2045",
            "invoice_date": datetime(2026, 3, 10, tzinfo=UTC).date().isoformat(),
            "total_amount": 165.0,
            "currency": "EUR",
            "expense_amount": 165.0,
            "cash_amount": 0.0,
            "revenue_amount": 0.0,
            "profit_amount": 0.0,
            "ai_summary": f"Fallback extraction generated for {stem}.",
            "line_items": [
                {"product_name": "Tomato Sauce", "quantity": 10, "unit_price": 5.0, "total_price": 50.0},
                {"product_name": "Cheese", "quantity": 5, "unit_price": 8.0, "total_price": 40.0},
                {"product_name": "Chicken", "quantity": 10, "unit_price": 6.0, "total_price": 60.0},
            ],
        }

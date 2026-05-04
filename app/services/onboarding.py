from __future__ import annotations

from fastapi import UploadFile

from app.core.exceptions import ValidationException
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.onboarding import (
    OnboardingFeatureScreenListResponse,
    OnboardingFeatureScreenResponse,
    OnboardingProfileResponse,
    OnboardingProfileUpsertRequest,
)
from app.services.base import BaseService
from app.services.image_storage import ImageStorageService, UploadedImage


class OnboardingService(BaseService):
    """Service Layer Pattern: encapsulates onboarding persistence and response mapping."""

    FEATURE_SCREENS = [
        {
            "key": "profit_tracking",
            "icon": "trending-up",
            "en": {
                "title": "Understand What Drives Profit",
                "description": "Risto AI connects your daily sales and costs so you can see why profit moves, not just whether it went up or down.",
                "points": [
                    "Monitor estimated profit after operating costs.",
                    "Find slow periods and revenue opportunities.",
                    "Use insights to adjust pricing, spending, and stock.",
                ],
            },
            "it": {
                "title": "Capisci cosa guida il profitto",
                "description": "Risto AI collega vendite e costi giornalieri per mostrarti perche il profitto cambia, non solo se sale o scende.",
                "points": [
                    "Monitora il profitto stimato dopo i costi operativi.",
                    "Trova periodi lenti e opportunita di ricavo.",
                    "Usa gli insight per regolare prezzi, spese e stock.",
                ],
            },
        },
        {
            "key": "invoice_photo_upload",
            "icon": "camera",
            "en": {
                "title": "Turn Invoices Into Records",
                "description": "Photo upload helps convert supplier paperwork into structured data for expenses, inventory checks, and VAT review.",
                "points": [
                    "Extract totals, VAT, dates, and invoice numbers.",
                    "Keep document history organized by supplier.",
                    "Use saved invoice data across reporting screens.",
                ],
            },
            "it": {
                "title": "Trasforma le fatture in dati",
                "description": "Il caricamento foto converte i documenti fornitore in dati strutturati per spese, inventario e controllo IVA.",
                "points": [
                    "Estrai totali, IVA, date e numeri fattura.",
                    "Mantieni lo storico documenti organizzato per fornitore.",
                    "Usa i dati salvati nelle schermate di report.",
                ],
            },
        },
        {
            "key": "inventory",
            "icon": "archive",
            "en": {
                "title": "Know What Is In Stock",
                "description": "Inventory tools help you understand what you have, what it costs, and when it needs attention.",
                "points": [
                    "Update stock after purchases or usage.",
                    "Group items by category and supplier.",
                    "Reduce waste by catching stock changes early.",
                ],
            },
            "it": {
                "title": "Sai sempre cosa hai in stock",
                "description": "Gli strumenti inventario aiutano a capire cosa hai, quanto costa e quando serve intervenire.",
                "points": [
                    "Aggiorna lo stock dopo acquisti o utilizzo.",
                    "Raggruppa articoli per categoria e fornitore.",
                    "Riduci gli sprechi notando subito i cambiamenti.",
                ],
            },
        },
        {
            "key": "vat_management",
            "icon": "file-text",
            "en": {
                "title": "Keep VAT Visible",
                "description": "VAT management connects daily data, expenses, and invoice details so tax-related numbers stay easy to review.",
                "points": [
                    "Keep VAT figures linked to real business activity.",
                    "Review estimated balances before filing.",
                    "Use invoice data to support VAT records.",
                ],
            },
            "it": {
                "title": "Tieni l IVA sempre visibile",
                "description": "La gestione IVA collega dati giornalieri, spese e fatture per rendere i numeri fiscali facili da controllare.",
                "points": [
                    "Collega i valori IVA all attivita reale.",
                    "Controlla i saldi stimati prima della dichiarazione.",
                    "Usa i dati fattura per supportare i registri IVA.",
                ],
            },
        },
    ]

    def __init__(
        self,
        onboarding_repository: OnboardingProfileRepository,
        user_repository: UserRepository,
        image_storage_service: ImageStorageService | None = None,
    ) -> None:
        self.onboarding_repository = onboarding_repository
        self.user_repository = user_repository
        self.image_storage_service = image_storage_service

    async def save_profile(self, current_user: dict, payload: OnboardingProfileUpsertRequest) -> OnboardingProfileResponse:
        return await self._save_profile(
            current_user,
            payload.model_dump(mode="json"),
            restaurant_name=payload.restaurant_name,
            city_location=payload.city_location,
        )

    async def save_profile_with_uploads(
        self,
        current_user: dict,
        payload: OnboardingProfileUpsertRequest,
        *,
        profile_image: UploadFile | None = None,
        interior_photo: UploadFile | None = None,
        exterior_photo: UploadFile | None = None,
    ) -> OnboardingProfileResponse:
        data = payload.model_dump(mode="json")
        if profile_image:
            data["profile_image_url"] = await self._upload_image(current_user, profile_image, field_name="profile_image_url")
        if interior_photo:
            data["interior_photo_url"] = await self._upload_image(current_user, interior_photo, field_name="interior_photo_url")
        if exterior_photo:
            data["exterior_photo_url"] = await self._upload_image(current_user, exterior_photo, field_name="exterior_photo_url")
        return await self._save_profile(
            current_user,
            data,
            restaurant_name=payload.restaurant_name,
            city_location=payload.city_location,
        )

    async def get_profile(self, current_user: dict) -> OnboardingProfileResponse | None:
        profile = await self.onboarding_repository.get_by_user_id(str(current_user["_id"]))
        if not profile:
            return None
        return self._to_response(profile)

    def get_feature_screens(self, language: str | None = None) -> OnboardingFeatureScreenListResponse:
        resolved_language = "it" if str(language or "").lower().startswith("it") else "en"
        screens = []
        for screen in self.FEATURE_SCREENS:
            copy = screen[resolved_language]
            screens.append(
                OnboardingFeatureScreenResponse(
                    key=str(screen["key"]),
                    icon=str(screen["icon"]),
                    title=str(copy["title"]),
                    description=str(copy["description"]),
                    points=list(copy["points"]),
                )
            )
        return OnboardingFeatureScreenListResponse(language=resolved_language, screens=screens)

    async def _upload_image(self, current_user: dict, file: UploadFile, *, field_name: str) -> str:
        if not self.image_storage_service:
            raise ValidationException("Image upload service is not configured")
        uploaded: UploadedImage = await self.image_storage_service.upload_file(
            file=file,
            prefix=f"onboarding/{current_user['_id']}/{field_name}",
        )
        return uploaded.url

    async def _save_profile(
        self,
        current_user: dict,
        payload: dict,
        *,
        restaurant_name: str,
        city_location: str,
    ) -> OnboardingProfileResponse:
        next_profile_image = (
            payload.get("profile_image_url")
            or current_user.get("profile_image_url")
            or current_user.get("avatar_url")
        )
        profile = await self.onboarding_repository.upsert_by_user_id(
            str(current_user["_id"]),
            {
                **payload,
                "onboarding_completed": True,
            },
        )
        await self.user_repository.update(
            current_user["_id"],
            {
                "restaurant_name": restaurant_name,
                "restaurant_type": payload.get("restaurant_type"),
                "city_location": city_location,
                "location": city_location,
                "number_of_seats": payload.get("number_of_seats"),
                "average_spend_per_customer": payload.get("average_spend_per_customer"),
                "main_business_goal": payload.get("main_business_goal"),
                "biggest_problem": payload.get("biggest_problem"),
                "improvement_focus": payload.get("improvement_focus"),
                "profile_image_url": next_profile_image,
                "avatar_url": next_profile_image,
                "onboarding_completed": True,
            },
        )
        return self._to_response(profile)

    def _to_response(self, profile: dict) -> OnboardingProfileResponse:
        serialized = self.serialize(profile)
        if self.image_storage_service:
            serialized["profile_image_url"] = self.image_storage_service.resolve_public_url(serialized.get("profile_image_url"))
            serialized["interior_photo_url"] = self.image_storage_service.resolve_public_url(serialized.get("interior_photo_url"))
            serialized["exterior_photo_url"] = self.image_storage_service.resolve_public_url(serialized.get("exterior_photo_url"))
        return OnboardingProfileResponse(**serialized)

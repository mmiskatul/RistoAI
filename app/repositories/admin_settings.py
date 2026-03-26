from __future__ import annotations

from datetime import UTC, datetime

from app.db.collections import CoreCollections
from app.repositories.base import BaseRepository


class AdminSettingsRepository(BaseRepository[dict]):
    collection_name = CoreCollections.ADMIN_SETTINGS

    async def get_settings_document(self) -> dict:
        document = await self.get_one({'singleton_key': 'platform_settings'})
        if document:
            return document
        now = datetime.now(UTC)
        return await self.create(
            {
                'singleton_key': 'platform_settings',
                'platform_name': 'Risto AI',
                'support_email': 'support@risto-ai.com',
                'default_language': 'English (United States)',
                'legal_documents': {
                    'terms_of_service': {
                        'title': 'Terms of Service',
                        'content': '# Terms of Service\n\n## 1. Acceptance of Terms\nBy accessing and using our platform, you agree to be bound by these Terms of Service and all applicable laws and regulations.',
                        'updated_at': now,
                    },
                    'privacy_policy': {
                        'title': 'Privacy Policy',
                        'content': '# Privacy Policy\n\n## 1. Information We Collect\nWe collect account, restaurant, and operational data required to provide and improve the platform.',
                        'updated_at': now,
                    },
                },
            }
        )

    async def update_settings_fields(self, payload: dict) -> dict:
        document = await self.get_settings_document()
        return await self.update(document['_id'], payload)

    async def update_legal_document(self, document_key: str, content: str, updated_by: str) -> dict:
        document = await self.get_settings_document()
        legal_documents = document.get('legal_documents', {})
        legal_document = legal_documents.get(document_key, {})
        legal_documents[document_key] = {
            'title': legal_document.get('title', document_key.replace('_', ' ').title()),
            'content': content,
            'updated_at': datetime.now(UTC),
            'updated_by': updated_by,
        }
        return await self.update(document['_id'], {'legal_documents': legal_documents})

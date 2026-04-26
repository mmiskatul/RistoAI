from __future__ import annotations

from datetime import UTC, datetime

from app.db.collections import CoreCollections
from app.repositories.base import BaseRepository

DEFAULT_TERMS_CONTENT = """# Terms of Service

## 1. Agreement to Use the Platform
By creating an account or using the platform, you agree to these Terms of Service and to all applicable laws and regulations. If you do not agree with these terms, you must stop using the service.

## 2. Restaurant Account Responsibility
You are responsible for maintaining the confidentiality of your login credentials and for all activity performed through your restaurant account. You must ensure that account information, staff access, and contact details remain accurate and up to date.

## 3. Operational and Financial Data
The platform allows you to upload invoices, restaurant records, operational metrics, and related business information. You confirm that you have the right to upload and process this data and that the information you provide is accurate to the best of your knowledge.

## 4. Billing and Subscription
Some features are available only through a paid subscription. Subscription charges, renewal periods, trial access, and billing management are handled according to the plan selected by your restaurant. Failure to maintain an active subscription may limit access to premium features.

## 5. Acceptable Use
You agree not to misuse the platform, attempt unauthorized access, interfere with system performance, upload malicious content, or use the service in a way that could harm other users or the platform infrastructure.

## 6. Service Availability
We aim to keep the service available and reliable, but uninterrupted access is not guaranteed. Maintenance, updates, security actions, or third-party outages may occasionally affect availability.

## 7. Limitation of Liability
The platform is provided to support restaurant operations and decision-making, but final business, legal, tax, and financial decisions remain your responsibility. We are not liable for indirect losses, business interruption, or decisions made solely on automated outputs.

## 8. Changes to These Terms
We may update these Terms of Service from time to time. Continued use of the platform after updates become effective means you accept the revised terms.
"""

LEGACY_TERMS_CONTENT = "# Terms of Service\n\n## 1. Acceptance of Terms\nBy accessing and using our platform, you agree to be bound by these Terms of Service and all applicable laws and regulations."

DEFAULT_PRIVACY_CONTENT = """# Privacy Policy

## 1. Information We Collect
We collect account information, restaurant profile details, uploaded invoices, operational records, and settings data that are required to provide and improve the platform.

## 2. How We Use Information
We use your information to operate the service, secure your account, process uploaded business records, provide analytics, support billing workflows, and improve product performance.

## 3. Data Protection
We apply reasonable technical and organizational measures to protect your information from unauthorized access, loss, misuse, or disclosure. No online system can guarantee absolute security, but we work to maintain appropriate safeguards.

## 4. Data Sharing
We do not sell your restaurant data. Information may be shared only with service providers or infrastructure partners who support hosting, analytics, payments, or communications and only where needed to operate the platform.

## 5. Data Retention
We retain data for as long as necessary to provide the service, comply with legal obligations, resolve disputes, and enforce platform policies.

## 6. Policy Updates
We may update this Privacy Policy from time to time. The most recent version will always be available through the platform settings and public legal pages.
"""

LEGACY_PRIVACY_CONTENT = "# Privacy Policy\n\n## 1. Information We Collect\nWe collect account, restaurant, and operational data required to provide and improve the platform."


class AdminSettingsRepository(BaseRepository[dict]):
    collection_name = CoreCollections.ADMIN_SETTINGS

    async def get_settings_document(self) -> dict:
        document = await self.get_one({'singleton_key': 'platform_settings'})
        if document:
            legal_documents = document.get('legal_documents', {})
            updates: dict[str, object] = {}

            terms_document = legal_documents.get('terms_of_service', {})
            privacy_document = legal_documents.get('privacy_policy', {})

            if not terms_document.get('content') or terms_document.get('content') == LEGACY_TERMS_CONTENT:
                legal_documents = {**legal_documents}
                legal_documents['terms_of_service'] = {
                    **terms_document,
                    'title': terms_document.get('title', 'Terms of Service'),
                    'content': DEFAULT_TERMS_CONTENT,
                    'updated_at': terms_document.get('updated_at', datetime.now(UTC)),
                }
                updates['legal_documents'] = legal_documents

            if not privacy_document.get('content') or privacy_document.get('content') == LEGACY_PRIVACY_CONTENT:
                if 'legal_documents' not in updates:
                    legal_documents = {**legal_documents}
                legal_documents['privacy_policy'] = {
                    **privacy_document,
                    'title': privacy_document.get('title', 'Privacy Policy'),
                    'content': DEFAULT_PRIVACY_CONTENT,
                    'updated_at': privacy_document.get('updated_at', datetime.now(UTC)),
                }
                updates['legal_documents'] = legal_documents

            if updates:
                return await self.update(document['_id'], updates)
            return document
        now = datetime.now(UTC)
        return await self.create(
            {
                'singleton_key': 'platform_settings',
                'platform_name': 'Risto AI',
                'support_email': 'support@risto-ai.com',
                'default_language': 'en-US',
                'legal_documents': {
                    'terms_of_service': {
                        'title': 'Terms of Service',
                        'content': DEFAULT_TERMS_CONTENT,
                        'updated_at': now,
                    },
                    'privacy_policy': {
                        'title': 'Privacy Policy',
                        'content': DEFAULT_PRIVACY_CONTENT,
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

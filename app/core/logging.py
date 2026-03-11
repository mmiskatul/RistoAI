from __future__ import annotations

import logging

from app.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure application-wide logging."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

from __future__ import annotations

import logging

from app.config.settings import Settings


NOISY_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "pymongo",
    "pymongo.command",
    "pymongo.connection",
    "pymongo.serverSelection",
    "pymongo.topology",
    "motor",
    "passlib",
)


def configure_logging(settings: Settings) -> None:
    """Configure application-wide logging."""
    level_name = settings.log_level.upper()
    resolved_level = getattr(logging, level_name, logging.ERROR)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    for logger_name in NOISY_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        if logger_name == "uvicorn.access":
            logger.disabled = True

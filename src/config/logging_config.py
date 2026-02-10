"""
Logging Configuration

Setup structured logging for the application.
"""

import logging
import sys
from typing import Optional

from .settings import Settings


def setup_logging(settings: Optional[Settings] = None) -> None:
    """
    Configure application logging.

    Args:
        settings: Application settings (uses defaults if not provided)
    """
    if settings is None:
        from .settings import get_settings
        settings = get_settings()

    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set specific logger levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # More verbose in development
    if settings.is_development:
        logging.getLogger("src").setLevel(logging.DEBUG)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at level: {settings.log_level}")

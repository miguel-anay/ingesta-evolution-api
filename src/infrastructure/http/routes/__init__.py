"""
API Routes

FastAPI route definitions organized by capability.
"""

from .messaging_routes import router as messaging_router
from .instance_routes import router as instance_router
from .health_routes import router as health_router
from .ingestion_routes import ingestion_router
from .search_routes import router as search_router

__all__ = [
    "messaging_router",
    "instance_router",
    "health_router",
    "ingestion_router",
    "search_router",
]

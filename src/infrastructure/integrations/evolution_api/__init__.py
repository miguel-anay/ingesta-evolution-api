"""
Evolution API Integration

Adapters implementing ports for Evolution API integration.
"""

from .client import EvolutionApiClient
from .whatsapp_adapter import EvolutionApiWhatsAppAdapter
from .instance_adapter import EvolutionApiInstanceAdapter
from .image_source_adapter import EvolutionApiImageSourceAdapter
from .exceptions import EvolutionApiError, EvolutionApiConnectionError

__all__ = [
    "EvolutionApiClient",
    "EvolutionApiWhatsAppAdapter",
    "EvolutionApiInstanceAdapter",
    "EvolutionApiImageSourceAdapter",
    "EvolutionApiError",
    "EvolutionApiConnectionError",
]

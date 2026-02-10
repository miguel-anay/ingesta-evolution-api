"""
Infrastructure Layer

Contains adapters that implement ports, external API clients,
database repositories, HTTP controllers, and framework code.

RULES:
- CAN import from domain and application layers
- Implements ports defined in application layer
- Contains all framework-specific code (FastAPI, SQLAlchemy, etc.)
- External API clients (Evolution API) live here
"""

"""
Application Layer

Contains use cases (application services) and port definitions (interfaces).
Orchestrates domain objects to fulfill business requirements.

RULES:
- CAN import from domain layer
- CANNOT import from infrastructure layer
- Defines ports (interfaces) that infrastructure implements
- Use cases receive ports via dependency injection
"""

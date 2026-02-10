# Architecture Guide

## Overview

This microservice implements **Hexagonal Architecture** (also known as Ports and Adapters) to achieve:

- **Independence from frameworks**: Business logic doesn't depend on FastAPI
- **Testability**: Use cases can be tested without infrastructure
- **Flexibility**: Easy to swap implementations (e.g., different databases)
- **Maintainability**: Clear boundaries prevent spaghetti code

## Core Principles

### 1. The Scope Rule

> Code used by exactly ONE feature MUST remain local to that feature.
> Code used by TWO OR MORE features gets extracted to `shared/`.

**Why?** Prevents premature abstraction and over-engineering.

**Example:**
```python
# BAD: Creating shared utility "just in case"
# shared/utils/formatters.py
def format_phone(number): ...  # Only used in messaging

# GOOD: Keep it local until actually shared
# domain/messaging/value_objects.py
class PhoneNumber:
    def format(self): ...  # Local to messaging domain
```

### 2. Dependency Direction

Dependencies flow INWARD:

```
[Infrastructure] → [Application] → [Domain]
```

- **Domain** imports NOTHING external
- **Application** imports only Domain
- **Infrastructure** can import everything

**Violation Example:**
```python
# BAD: Domain importing infrastructure
# domain/messaging/entities.py
from httpx import Client  # VIOLATION!

# GOOD: Domain is pure
# domain/messaging/entities.py
from dataclasses import dataclass
from datetime import datetime
```

### 3. Ports and Adapters

**Ports** (interfaces) define what the application needs:
```python
# application/messaging/ports/whatsapp_gateway.py
class IWhatsAppGateway(ABC):
    @abstractmethod
    async def send_text_message(self, ...): ...
```

**Adapters** (implementations) provide what the application needs:
```python
# infrastructure/integrations/evolution_api/whatsapp_adapter.py
class EvolutionApiWhatsAppAdapter(IWhatsAppGateway):
    async def send_text_message(self, ...):
        # Actual Evolution API calls here
```

## Layer Responsibilities

### Domain Layer

**Location:** `src/domain/`

**Contains:**
- Entities (e.g., `Message`, `Instance`)
- Value Objects (e.g., `PhoneNumber`, `MessageContent`)
- Domain Exceptions
- Domain Services (business logic that doesn't fit in entities)

**Rules:**
- NO imports from `application/` or `infrastructure/`
- NO framework imports (no FastAPI, no SQLAlchemy)
- Only pure Python and standard library
- Contains ALL business rules and validation

**Example:**
```python
# domain/messaging/entities.py
@dataclass
class Message:
    recipient: PhoneNumber  # Value object
    content: MessageContent  # Value object
    status: MessageStatus = MessageStatus.PENDING

    def mark_as_sent(self, external_id: str) -> None:
        """Domain logic for status transition."""
        self.status = MessageStatus.SENT
        self.external_id = external_id
```

### Application Layer

**Location:** `src/application/`

**Contains:**
- Use Cases (application services)
- Port Definitions (interfaces)
- DTOs for input/output

**Rules:**
- CAN import from `domain/`
- CANNOT import from `infrastructure/`
- Orchestrates domain objects
- Defines what infrastructure must provide (via ports)

**Example:**
```python
# application/messaging/use_cases/send_text_message.py
class SendTextMessageUseCase:
    def __init__(
        self,
        whatsapp_gateway: IWhatsAppGateway,  # Port injection
        message_repository: IMessageRepository,
    ):
        self._gateway = whatsapp_gateway
        self._repository = message_repository

    async def execute(self, request: SendTextMessageRequest):
        # 1. Create domain objects
        message = Message(...)

        # 2. Use port (don't know implementation)
        external_id = await self._gateway.send_text_message(...)

        # 3. Update domain state
        message.mark_as_sent(external_id)

        # 4. Persist via port
        await self._repository.save(message)
```

### Infrastructure Layer

**Location:** `src/infrastructure/`

**Contains:**
- Adapter implementations
- HTTP routes (FastAPI)
- Database repositories
- External API clients
- Message broker publishers

**Rules:**
- CAN import from `domain/` and `application/`
- Implements ports defined in application
- Contains all framework-specific code

**Example:**
```python
# infrastructure/integrations/evolution_api/whatsapp_adapter.py
class EvolutionApiWhatsAppAdapter(IWhatsAppGateway):
    def __init__(self, client: EvolutionApiClient):
        self._client = client  # HTTP client is infrastructure detail

    async def send_text_message(self, ...) -> str:
        # Translate domain concepts to API calls
        response = await self._client.send_text(...)
        return response["key"]["id"]
```

## Dependency Injection

The **Composition Root** (`infrastructure/http/dependencies.py`) wires everything:

```python
# dependencies.py - The ONLY place creating concrete instances
def get_send_text_use_case(
    whatsapp_adapter: EvolutionApiWhatsAppAdapter = Depends(get_whatsapp_adapter),
    message_repository: InMemoryMessageRepository = Depends(get_message_repository),
) -> SendTextMessageUseCase:
    return SendTextMessageUseCase(
        whatsapp_gateway=whatsapp_adapter,  # Adapter implements port
        message_repository=message_repository,
    )
```

## Testing Strategy

### Unit Tests (domain + application)

```python
# tests/unit/application/test_send_message.py
def test_send_message(mock_gateway, mock_repository):
    use_case = SendTextMessageUseCase(
        whatsapp_gateway=mock_gateway,  # Mock port
        message_repository=mock_repository,
    )
    # Test business logic without real infrastructure
```

### Integration Tests

```python
# tests/integration/test_api.py
def test_send_endpoint(client, mock_evolution_api):
    # Test HTTP layer with mocked external services
    response = client.post("/messages/text", json={...})
```

### E2E Tests

```python
# tests/e2e/test_full_flow.py
def test_real_message_flow(real_evolution_client):
    # Test with real Evolution API (requires running instance)
```

## Adding New Features Checklist

1. [ ] Define domain entities in `domain/[capability]/entities.py`
2. [ ] Define value objects in `domain/[capability]/value_objects.py`
3. [ ] Define exceptions in `domain/[capability]/exceptions.py`
4. [ ] Define port(s) in `application/[capability]/ports/`
5. [ ] Implement use case(s) in `application/[capability]/use_cases/`
6. [ ] Implement adapter(s) in `infrastructure/`
7. [ ] Add dependency injection in `dependencies.py`
8. [ ] Add HTTP routes in `infrastructure/http/routes/`
9. [ ] Write unit tests for domain and use cases
10. [ ] Write integration tests for endpoints

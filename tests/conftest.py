"""
Pytest Configuration and Fixtures

Shared fixtures for all test types.
"""

import pytest
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import create_app
from src.config.settings import Settings
from src.domain.messaging.value_objects import PhoneNumber, MessageContent
from src.domain.messaging.entities import Message, MessageType
from src.domain.instances.value_objects import InstanceName
from src.domain.instances.entities import Instance
from src.infrastructure.persistence.repositories import (
    InMemoryMessageRepository,
    InMemoryInstanceRepository,
)
from src.infrastructure.messaging.rabbitmq import InMemoryEventPublisher


# --- Settings Fixtures ---

@pytest.fixture
def test_settings() -> Settings:
    """Test settings with safe defaults."""
    return Settings(
        environment="test",
        debug=True,
        evolution_api_url="http://test-evolution:8080",
        evolution_api_key="test-api-key",
        log_level="DEBUG",
    )


# --- Domain Fixtures ---

@pytest.fixture
def sample_phone_number() -> PhoneNumber:
    """Sample phone number for testing."""
    return PhoneNumber(number="5551234567", country_code="52")


@pytest.fixture
def sample_message_content() -> MessageContent:
    """Sample message content for testing."""
    return MessageContent(text="Hello, this is a test message!")


@pytest.fixture
def sample_message(
    sample_phone_number: PhoneNumber,
    sample_message_content: MessageContent,
) -> Message:
    """Sample message entity for testing."""
    return Message(
        recipient=sample_phone_number,
        content=sample_message_content,
        message_type=MessageType.TEXT,
    )


@pytest.fixture
def sample_instance_name() -> InstanceName:
    """Sample instance name for testing."""
    return InstanceName(value="test-instance")


@pytest.fixture
def sample_instance(sample_instance_name: InstanceName) -> Instance:
    """Sample instance entity for testing."""
    return Instance(name=sample_instance_name)


# --- Repository Fixtures ---

@pytest.fixture
def message_repository() -> InMemoryMessageRepository:
    """Fresh in-memory message repository."""
    return InMemoryMessageRepository()


@pytest.fixture
def instance_repository() -> InMemoryInstanceRepository:
    """Fresh in-memory instance repository."""
    return InMemoryInstanceRepository()


@pytest.fixture
def event_publisher() -> InMemoryEventPublisher:
    """Fresh in-memory event publisher."""
    return InMemoryEventPublisher()


# --- Mock Fixtures ---

@pytest.fixture
def mock_whatsapp_gateway() -> AsyncMock:
    """Mock WhatsApp gateway for testing use cases."""
    mock = AsyncMock()
    mock.send_text_message.return_value = "msg_12345"
    mock.send_media_message.return_value = "msg_67890"
    mock.check_number_exists.return_value = True
    return mock


@pytest.fixture
def mock_instance_gateway() -> AsyncMock:
    """Mock instance gateway for testing use cases."""
    mock = AsyncMock()
    mock.create_instance.return_value = {"instanceName": "test-instance"}
    mock.list_instances.return_value = []
    mock.get_instance_status.return_value = {"state": "close"}
    return mock


# --- HTTP Fixtures ---

@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """Synchronous test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(app) -> AsyncClient:
    """Asynchronous test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

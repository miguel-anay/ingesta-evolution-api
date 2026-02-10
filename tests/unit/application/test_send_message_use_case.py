"""
Send Text Message Use Case Tests

Unit tests for SendTextMessageUseCase.
"""

import pytest
from unittest.mock import AsyncMock

from src.application.messaging.use_cases import (
    SendTextMessageUseCase,
    SendTextMessageRequest,
)
from src.domain.messaging.exceptions import MessageDeliveryError
from src.domain.instances.exceptions import InstanceNotConnectedError
from src.infrastructure.persistence.repositories import InMemoryMessageRepository
from src.infrastructure.messaging.rabbitmq import InMemoryEventPublisher


class TestSendTextMessageUseCase:
    """Tests for SendTextMessageUseCase."""

    @pytest.fixture
    def use_case(
        self,
        mock_whatsapp_gateway: AsyncMock,
        message_repository: InMemoryMessageRepository,
        event_publisher: InMemoryEventPublisher,
    ) -> SendTextMessageUseCase:
        """Create use case with mocked dependencies."""
        return SendTextMessageUseCase(
            whatsapp_gateway=mock_whatsapp_gateway,
            message_repository=message_repository,
            event_publisher=event_publisher,
        )

    @pytest.fixture
    def valid_request(self) -> SendTextMessageRequest:
        """Create a valid request."""
        return SendTextMessageRequest(
            instance_name="test-instance",
            recipient_number="5551234567",
            text="Hello, World!",
            country_code="52",
        )

    @pytest.mark.asyncio
    async def test_send_message_success(
        self,
        use_case: SendTextMessageUseCase,
        valid_request: SendTextMessageRequest,
        mock_whatsapp_gateway: AsyncMock,
        message_repository: InMemoryMessageRepository,
        event_publisher: InMemoryEventPublisher,
    ):
        """Should successfully send a message."""
        result = await use_case.execute(valid_request)

        # Verify response
        assert result.message_id is not None
        assert result.external_id == "msg_12345"
        assert result.status == "sent"
        assert result.recipient == "525551234567"

        # Verify gateway was called
        mock_whatsapp_gateway.send_text_message.assert_called_once()

        # Verify message was persisted
        assert await message_repository.count() == 1

        # Verify event was published
        events = event_publisher.get_events("message.sent")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_send_message_with_reply(
        self,
        use_case: SendTextMessageUseCase,
        mock_whatsapp_gateway: AsyncMock,
    ):
        """Should send message with reply_to reference."""
        request = SendTextMessageRequest(
            instance_name="test-instance",
            recipient_number="5551234567",
            text="This is a reply",
            reply_to_message_id="original_msg_123",
        )

        result = await use_case.execute(request)

        # Verify reply_to was passed to gateway
        call_args = mock_whatsapp_gateway.send_text_message.call_args
        assert call_args.kwargs.get("reply_to") == "original_msg_123"

    @pytest.mark.asyncio
    async def test_send_message_invalid_phone(
        self,
        use_case: SendTextMessageUseCase,
    ):
        """Should fail with invalid phone number."""
        request = SendTextMessageRequest(
            instance_name="test-instance",
            recipient_number="123",  # Too short
            text="Hello",
        )

        with pytest.raises(ValueError, match="at least 10 digits"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_send_message_empty_text(
        self,
        use_case: SendTextMessageUseCase,
    ):
        """Should fail with empty message text."""
        request = SendTextMessageRequest(
            instance_name="test-instance",
            recipient_number="5551234567",
            text="",
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_send_message_gateway_failure(
        self,
        use_case: SendTextMessageUseCase,
        valid_request: SendTextMessageRequest,
        mock_whatsapp_gateway: AsyncMock,
        message_repository: InMemoryMessageRepository,
        event_publisher: InMemoryEventPublisher,
    ):
        """Should handle gateway failure gracefully."""
        mock_whatsapp_gateway.send_text_message.side_effect = Exception("API Error")

        with pytest.raises(MessageDeliveryError):
            await use_case.execute(valid_request)

        # Message should still be persisted (with failed status)
        assert await message_repository.count() == 1

        # Failure event should be published
        events = event_publisher.get_events("message.failed")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_send_message_instance_not_connected(
        self,
        use_case: SendTextMessageUseCase,
        valid_request: SendTextMessageRequest,
        mock_whatsapp_gateway: AsyncMock,
    ):
        """Should handle instance not connected error."""
        mock_whatsapp_gateway.send_text_message.side_effect = InstanceNotConnectedError(
            "test-instance"
        )

        with pytest.raises(MessageDeliveryError):
            await use_case.execute(valid_request)

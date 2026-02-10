"""
Messaging Domain Entity Tests

Unit tests for Message entity and related domain logic.
"""

import pytest
from datetime import datetime

from src.domain.messaging.entities import Message, MessageStatus, MessageType
from src.domain.messaging.value_objects import PhoneNumber, MessageContent


class TestPhoneNumber:
    """Tests for PhoneNumber value object."""

    def test_create_valid_phone_number(self):
        """Should create phone number with valid input."""
        phone = PhoneNumber(number="5551234567", country_code="52")

        assert phone.number == "5551234567"
        assert phone.country_code == "52"
        assert phone.full_number == "525551234567"

    def test_phone_number_strips_non_digits(self):
        """Should remove non-digit characters."""
        phone = PhoneNumber(number="+52 555 123 4567")

        assert phone.number == "525551234567"

    def test_phone_number_whatsapp_id(self):
        """Should generate correct WhatsApp JID format."""
        phone = PhoneNumber(number="5551234567", country_code="52")

        assert phone.whatsapp_id == "525551234567@s.whatsapp.net"

    def test_phone_number_too_short_raises_error(self):
        """Should reject phone numbers that are too short."""
        with pytest.raises(ValueError, match="at least 10 digits"):
            PhoneNumber(number="123")

    def test_phone_number_too_long_raises_error(self):
        """Should reject phone numbers that are too long."""
        with pytest.raises(ValueError, match="cannot exceed 15 digits"):
            PhoneNumber(number="1234567890123456789")


class TestMessageContent:
    """Tests for MessageContent value object."""

    def test_create_valid_content(self):
        """Should create content with valid text."""
        content = MessageContent(text="Hello, World!")

        assert str(content) == "Hello, World!"

    def test_empty_content_raises_error(self):
        """Should reject empty content."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MessageContent(text="")

    def test_whitespace_only_raises_error(self):
        """Should reject whitespace-only content."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MessageContent(text="   ")

    def test_content_preview_short(self):
        """Should return full text for short messages."""
        content = MessageContent(text="Hello")

        assert content.preview == "Hello"

    def test_content_preview_long(self):
        """Should truncate long messages."""
        long_text = "x" * 100
        content = MessageContent(text=long_text)

        assert len(content.preview) == 50
        assert content.preview.endswith("...")


class TestMessage:
    """Tests for Message entity."""

    @pytest.fixture
    def message(self) -> Message:
        """Create a sample message for testing."""
        return Message(
            recipient=PhoneNumber(number="5551234567"),
            content=MessageContent(text="Test message"),
            message_type=MessageType.TEXT,
        )

    def test_message_creation_defaults(self, message: Message):
        """Should create message with correct defaults."""
        assert message.status == MessageStatus.PENDING
        assert message.id is not None
        assert message.created_at is not None
        assert message.sent_at is None
        assert message.external_id is None

    def test_mark_as_sent(self, message: Message):
        """Should update status when marked as sent."""
        message.mark_as_sent(external_id="ext_123")

        assert message.status == MessageStatus.SENT
        assert message.external_id == "ext_123"
        assert message.sent_at is not None

    def test_mark_as_delivered(self, message: Message):
        """Should update status when marked as delivered."""
        message.mark_as_sent("ext_123")
        message.mark_as_delivered()

        assert message.status == MessageStatus.DELIVERED
        assert message.delivered_at is not None

    def test_mark_as_read(self, message: Message):
        """Should update status when marked as read."""
        message.mark_as_sent("ext_123")
        message.mark_as_read()

        assert message.status == MessageStatus.READ
        assert message.read_at is not None

    def test_cannot_mark_failed_as_delivered(self, message: Message):
        """Should not allow marking failed message as delivered."""
        message.mark_as_failed()

        with pytest.raises(ValueError, match="Cannot mark failed message"):
            message.mark_as_delivered()

    def test_is_media_message_text(self, message: Message):
        """Text message should not be media."""
        assert message.is_media_message is False

    def test_is_media_message_image(self):
        """Image message should be media."""
        message = Message(
            recipient=PhoneNumber(number="5551234567"),
            content=MessageContent(text="[image]"),
            message_type=MessageType.IMAGE,
        )

        assert message.is_media_message is True

    def test_message_equality_by_id(self, message: Message):
        """Messages should be equal if they have the same ID."""
        same_message = Message(
            id=message.id,
            recipient=PhoneNumber(number="9999999999"),
            content=MessageContent(text="Different"),
            message_type=MessageType.TEXT,
        )

        assert message == same_message

    def test_message_hash(self, message: Message):
        """Messages should be hashable."""
        message_set = {message}
        assert message in message_set

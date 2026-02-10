"""
Instance Domain Entity Tests

Unit tests for Instance entity and related domain logic.
"""

import pytest
from datetime import datetime

from src.domain.instances.entities import Instance, InstanceStatus, ConnectionState
from src.domain.instances.value_objects import InstanceName, QRCode


class TestInstanceName:
    """Tests for InstanceName value object."""

    def test_create_valid_name(self):
        """Should create instance name with valid input."""
        name = InstanceName(value="my-instance")

        assert str(name) == "my-instance"

    def test_name_too_short_raises_error(self):
        """Should reject names that are too short."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            InstanceName(value="ab")

    def test_name_too_long_raises_error(self):
        """Should reject names that are too long."""
        with pytest.raises(ValueError, match="cannot exceed 50"):
            InstanceName(value="a" * 51)

    def test_name_must_start_with_letter(self):
        """Should reject names not starting with letter."""
        with pytest.raises(ValueError, match="must start with a letter"):
            InstanceName(value="123instance")

    def test_name_invalid_characters(self):
        """Should reject names with invalid characters."""
        with pytest.raises(ValueError, match="must start with a letter"):
            InstanceName(value="my instance!")

    def test_valid_name_with_numbers_and_dash(self):
        """Should accept names with numbers, dashes, underscores."""
        name = InstanceName(value="my-instance_123")
        assert str(name) == "my-instance_123"


class TestQRCode:
    """Tests for QRCode value object."""

    def test_create_valid_qr_code(self):
        """Should create QR code with valid data."""
        qr = QRCode(
            code="2@ABC123...",
            base64_image="data:image/png;base64,...",
            created_at=datetime.utcnow(),
        )

        assert qr.code == "2@ABC123..."
        assert not qr.is_expired

    def test_empty_code_raises_error(self):
        """Should reject empty QR code."""
        with pytest.raises(ValueError, match="cannot be empty"):
            QRCode(
                code="",
                base64_image="data:...",
                created_at=datetime.utcnow(),
            )

    def test_qr_code_expiry_calculation(self):
        """Should correctly calculate time until expiry."""
        qr = QRCode(
            code="test",
            base64_image="data:...",
            created_at=datetime.utcnow(),
        )

        # Fresh QR code should have ~60 seconds
        assert qr.seconds_until_expiry > 50
        assert qr.seconds_until_expiry <= 60


class TestInstance:
    """Tests for Instance entity."""

    @pytest.fixture
    def instance(self) -> Instance:
        """Create a sample instance for testing."""
        return Instance(name=InstanceName(value="test-instance"))

    def test_instance_creation_defaults(self, instance: Instance):
        """Should create instance with correct defaults."""
        assert instance.status == InstanceStatus.CREATED
        assert instance.connection_state == ConnectionState.CLOSE
        assert instance.is_connected is False
        assert instance.phone_number is None

    def test_connect_changes_status(self, instance: Instance):
        """Should change status when connecting."""
        instance.connect()

        assert instance.status == InstanceStatus.CONNECTING
        assert instance.connection_state == ConnectionState.CONNECTING

    def test_mark_connected(self, instance: Instance):
        """Should update state when connected."""
        instance.mark_connected(
            phone_number="525551234567",
            profile_name="Test User",
        )

        assert instance.status == InstanceStatus.CONNECTED
        assert instance.connection_state == ConnectionState.OPEN
        assert instance.phone_number == "525551234567"
        assert instance.profile_name == "Test User"
        assert instance.is_connected is True

    def test_disconnect(self, instance: Instance):
        """Should update state when disconnected."""
        instance.mark_connected("525551234567")
        instance.disconnect()

        assert instance.status == InstanceStatus.DISCONNECTED
        assert instance.connection_state == ConnectionState.CLOSE
        assert instance.is_connected is False

    def test_is_ready_to_send(self, instance: Instance):
        """Should be ready to send when connected with phone."""
        assert instance.is_ready_to_send is False

        instance.mark_connected("525551234567")

        assert instance.is_ready_to_send is True

    def test_update_qr_code(self, instance: Instance):
        """Should update QR code and status."""
        qr = QRCode(
            code="test-code",
            base64_image="data:...",
            created_at=datetime.utcnow(),
        )

        instance.update_qr_code(qr)

        assert instance.qr_code == qr
        assert instance.status == InstanceStatus.CONNECTING

    def test_cannot_update_qr_when_connected(self, instance: Instance):
        """Should not allow QR update when connected."""
        instance.mark_connected("525551234567")
        qr = QRCode(
            code="test",
            base64_image="data:...",
            created_at=datetime.utcnow(),
        )

        with pytest.raises(ValueError, match="Cannot update QR code"):
            instance.update_qr_code(qr)

    def test_mark_deleted(self, instance: Instance):
        """Should mark instance as deleted."""
        instance.mark_deleted()

        assert instance.status == InstanceStatus.DELETED
        assert instance.connection_state == ConnectionState.CLOSE

    def test_cannot_connect_deleted_instance(self, instance: Instance):
        """Should not allow connecting deleted instance."""
        instance.mark_deleted()

        with pytest.raises(ValueError, match="Cannot connect deleted"):
            instance.connect()

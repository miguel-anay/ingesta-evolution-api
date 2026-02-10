"""
Unit Tests for Image Ingestion Value Objects

Tests for domain value objects ensuring correct validation and behavior.
"""

import pytest

from src.domain.ingestion.value_objects import (
    SequentialId,
    ImageHash,
    ImagePath,
    MessageId,
    PhoneNumber,
    UserName,
    SourceType,
    Instance,
)


class TestSequentialId:
    """Tests for SequentialId value object."""

    def test_valid_sequential_id(self):
        """Sequential ID with positive value is valid."""
        seq_id = SequentialId(1)
        assert seq_id.value == 1

    def test_large_sequential_id(self):
        """Large sequential ID values are valid."""
        seq_id = SequentialId(999999)
        assert seq_id.value == 999999

    def test_invalid_zero_sequential_id(self):
        """Zero sequential ID raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            SequentialId(0)

    def test_invalid_negative_sequential_id(self):
        """Negative sequential ID raises ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            SequentialId(-1)

    def test_next_sequential_id(self):
        """Next() returns incremented ID."""
        seq_id = SequentialId(5)
        next_id = seq_id.next()
        assert next_id.value == 6

    def test_sequential_id_str(self):
        """String conversion returns value as string."""
        seq_id = SequentialId(42)
        assert str(seq_id) == "42"

    def test_sequential_id_int(self):
        """Int conversion returns value."""
        seq_id = SequentialId(42)
        assert int(seq_id) == 42


class TestImageHash:
    """Tests for ImageHash value object."""

    def test_valid_hash(self):
        """Valid SHA-256 hash is accepted."""
        valid_hash = "a" * 64
        image_hash = ImageHash(valid_hash)
        assert image_hash.value == valid_hash

    def test_hash_normalized_to_lowercase(self):
        """Hash is normalized to lowercase."""
        upper_hash = "A" * 64
        image_hash = ImageHash(upper_hash)
        assert image_hash.value == "a" * 64

    def test_empty_hash_raises_error(self):
        """Empty hash raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            ImageHash("")

    def test_short_hash_raises_error(self):
        """Hash shorter than 64 chars raises ValueError."""
        with pytest.raises(ValueError, match="64 hexadecimal"):
            ImageHash("a" * 63)

    def test_long_hash_raises_error(self):
        """Hash longer than 64 chars raises ValueError."""
        with pytest.raises(ValueError, match="64 hexadecimal"):
            ImageHash("a" * 65)

    def test_invalid_chars_raises_error(self):
        """Hash with non-hex characters raises ValueError."""
        with pytest.raises(ValueError, match="64 hexadecimal"):
            ImageHash("g" * 64)

    def test_hash_equality(self):
        """Hashes are equal if values match (case insensitive)."""
        hash1 = ImageHash("a" * 64)
        hash2 = ImageHash("A" * 64)
        assert hash1 == hash2


class TestImagePath:
    """Tests for ImagePath value object."""

    def test_valid_path(self):
        """Valid path components are accepted."""
        path = ImagePath(base_directory="/data/images", filename="1.jpg")
        assert path.base_directory == "/data/images"
        assert path.filename == "1.jpg"

    def test_full_path(self):
        """Full path is correctly constructed."""
        path = ImagePath(base_directory="/data/images", filename="42.jpg")
        assert path.full_path == "/data/images/42.jpg"

    def test_full_path_strips_trailing_slash(self):
        """Trailing slashes are stripped from base directory."""
        path = ImagePath(base_directory="/data/images/", filename="1.jpg")
        assert path.full_path == "/data/images/1.jpg"

    def test_empty_base_directory_raises_error(self):
        """Empty base directory raises ValueError."""
        with pytest.raises(ValueError, match="Base directory cannot be empty"):
            ImagePath(base_directory="", filename="1.jpg")

    def test_empty_filename_raises_error(self):
        """Empty filename raises ValueError."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            ImagePath(base_directory="/data", filename="")

    def test_invalid_filename_format_raises_error(self):
        """Filename not matching pattern raises ValueError."""
        with pytest.raises(ValueError, match="Invalid filename format"):
            ImagePath(base_directory="/data", filename="image.png")

    def test_from_sequential_id(self):
        """Path can be created from sequential ID."""
        seq_id = SequentialId(123)
        path = ImagePath.from_sequential_id("/data/images", seq_id)
        assert path.filename == "123.jpg"
        assert path.full_path == "/data/images/123.jpg"


class TestMessageId:
    """Tests for MessageId value object."""

    def test_valid_message_id(self):
        """Valid message ID is accepted."""
        msg_id = MessageId("abc123")
        assert msg_id.value == "abc123"

    def test_empty_message_id_raises_error(self):
        """Empty message ID raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MessageId("")

    def test_long_message_id_raises_error(self):
        """Message ID over 500 chars raises ValueError."""
        with pytest.raises(ValueError, match="too long"):
            MessageId("a" * 501)

    def test_message_id_equality(self):
        """Message IDs are equal if values match."""
        id1 = MessageId("test123")
        id2 = MessageId("test123")
        assert id1 == id2

    def test_message_id_inequality(self):
        """Different message IDs are not equal."""
        id1 = MessageId("test123")
        id2 = MessageId("test456")
        assert id1 != id2


class TestPhoneNumber:
    """Tests for PhoneNumber value object."""

    def test_valid_phone_number(self):
        """Valid phone number is accepted."""
        phone = PhoneNumber("5511999999999")
        assert phone.value == "5511999999999"

    def test_phone_with_plus_normalized(self):
        """Phone number with + prefix is normalized."""
        phone = PhoneNumber("+5511999999999")
        assert phone.value == "5511999999999"

    def test_phone_with_formatting_normalized(self):
        """Phone number with formatting is normalized."""
        phone = PhoneNumber("+55 (11) 99999-9999")
        assert phone.value == "5511999999999"

    def test_empty_phone_raises_error(self):
        """Empty phone number raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PhoneNumber("")

    def test_short_phone_raises_error(self):
        """Phone number with less than 10 digits raises ValueError."""
        with pytest.raises(ValueError, match="at least 10 digits"):
            PhoneNumber("123456789")

    def test_long_phone_raises_error(self):
        """Phone number with more than 15 digits raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 15 digits"):
            PhoneNumber("1234567890123456")


class TestUserName:
    """Tests for UserName value object."""

    def test_valid_username(self):
        """Valid username is accepted."""
        name = UserName("John Doe")
        assert name.value == "John Doe"

    def test_empty_username_allowed(self):
        """Empty username is allowed."""
        name = UserName("")
        assert name.value == ""
        assert name.is_empty

    def test_long_username_truncated(self):
        """Username over max length is truncated."""
        long_name = "a" * 300
        name = UserName(long_name)
        assert len(name.value) == 256

    def test_is_empty_whitespace_only(self):
        """Whitespace-only username is considered empty."""
        name = UserName("   ")
        assert name.is_empty


class TestSourceType:
    """Tests for SourceType enum."""

    def test_chat_value(self):
        """Chat source type has correct value."""
        assert SourceType.CHAT.value == "chat"

    def test_status_value(self):
        """Status source type has correct value."""
        assert SourceType.STATUS.value == "estado"

    def test_from_string_chat(self):
        """from_string recognizes chat variants."""
        assert SourceType.from_string("chat") == SourceType.CHAT
        assert SourceType.from_string("CHAT") == SourceType.CHAT
        assert SourceType.from_string("mensaje") == SourceType.CHAT

    def test_from_string_status(self):
        """from_string recognizes status variants."""
        assert SourceType.from_string("estado") == SourceType.STATUS
        assert SourceType.from_string("status") == SourceType.STATUS
        assert SourceType.from_string("story") == SourceType.STATUS
        assert SourceType.from_string("stories") == SourceType.STATUS

    def test_from_string_invalid(self):
        """from_string raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid source type"):
            SourceType.from_string("invalid")


class TestInstance:
    """Tests for Instance value object."""

    def test_valid_instance(self):
        """Valid instance identifier is accepted."""
        instance = Instance("my-instance")
        assert instance.value == "my-instance"

    def test_instance_stripped(self):
        """Instance identifier is stripped of whitespace."""
        instance = Instance("  my-instance  ")
        assert instance.value == "my-instance"

    def test_empty_instance_raises_error(self):
        """Empty instance identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Instance("")

    def test_whitespace_only_raises_error(self):
        """Whitespace-only instance raises ValueError."""
        with pytest.raises(ValueError, match="cannot be whitespace only"):
            Instance("   ")

    def test_long_instance_raises_error(self):
        """Instance over 100 chars raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100 characters"):
            Instance("a" * 101)

    def test_instance_equality(self):
        """Instances are equal if values match."""
        inst1 = Instance("test-instance")
        inst2 = Instance("test-instance")
        assert inst1 == inst2

    def test_instance_inequality(self):
        """Different instances are not equal."""
        inst1 = Instance("instance-1")
        inst2 = Instance("instance-2")
        assert inst1 != inst2

    def test_instance_str(self):
        """String conversion returns value."""
        instance = Instance("my-instance")
        assert str(instance) == "my-instance"

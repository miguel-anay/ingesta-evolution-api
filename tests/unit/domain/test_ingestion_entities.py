"""
Unit Tests for Image Ingestion Entities

Tests for domain entities ensuring correct behavior and business rules.
"""

import pytest
from datetime import datetime

from src.domain.ingestion.entities import (
    ImageMetadata,
    RawImageData,
    IngestionResult,
)
from src.domain.ingestion.value_objects import (
    SequentialId,
    MessageId,
    SourceType,
    ImageHash,
    ImagePath,
    PhoneNumber,
    UserName,
    Instance,
)


class TestImageMetadata:
    """Tests for ImageMetadata entity."""

    @pytest.fixture
    def sample_metadata(self):
        """Create a sample ImageMetadata for testing."""
        return ImageMetadata(
            id_secuencial=SequentialId(1),
            id_mensaje=MessageId("msg123"),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime(2024, 1, 15, 10, 30, 0),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("John Doe"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data/images", "1.jpg"),
            hash_imagen=ImageHash("a" * 64),
        )

    def test_metadata_creation(self, sample_metadata):
        """Metadata can be created with all required fields."""
        assert sample_metadata.id_secuencial.value == 1
        assert str(sample_metadata.id_mensaje) == "msg123"
        assert sample_metadata.tipo_origen == SourceType.CHAT

    def test_is_from_chat(self, sample_metadata):
        """is_from_chat returns True for chat messages."""
        assert sample_metadata.is_from_chat is True
        assert sample_metadata.is_from_status is False

    def test_is_from_status(self):
        """is_from_status returns True for status images."""
        metadata = ImageMetadata(
            id_secuencial=SequentialId(1),
            id_mensaje=MessageId("status123"),
            tipo_origen=SourceType.STATUS,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Jane"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data/images", "1.jpg"),
            hash_imagen=ImageHash("b" * 64),
        )
        assert metadata.is_from_status is True
        assert metadata.is_from_chat is False

    def test_metadata_equality(self, sample_metadata):
        """Metadata equality is based on sequential ID."""
        other = ImageMetadata(
            id_secuencial=SequentialId(1),  # Same ID
            id_mensaje=MessageId("different"),
            tipo_origen=SourceType.STATUS,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5522888888888"),
            nombre_usuario=UserName("Different"),
            instancia=Instance("other-instance"),
            ruta_archivo=ImagePath("/other/path", "1.jpg"),
            hash_imagen=ImageHash("c" * 64),
        )
        assert sample_metadata == other

    def test_metadata_inequality(self, sample_metadata):
        """Metadata with different IDs are not equal."""
        other = ImageMetadata(
            id_secuencial=SequentialId(2),  # Different ID
            id_mensaje=MessageId("msg123"),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("John Doe"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data/images", "2.jpg"),
            hash_imagen=ImageHash("a" * 64),
        )
        assert sample_metadata != other

    def test_metadata_hash(self, sample_metadata):
        """Metadata can be used in sets (hashable)."""
        metadata_set = {sample_metadata}
        assert sample_metadata in metadata_set


class TestRawImageData:
    """Tests for RawImageData entity."""

    @pytest.fixture
    def sample_raw_image(self):
        """Create a sample RawImageData for testing."""
        return RawImageData(
            message_id=MessageId("msg123"),
            source_type=SourceType.CHAT,
            phone_number=PhoneNumber("5511999999999"),
            user_name=UserName("John"),
            instance=Instance("test-instance"),
            image_bytes=b"\x89PNG\r\n\x1a\n",
            original_mime_type="image/png",
        )

    def test_raw_image_creation(self, sample_raw_image):
        """RawImageData can be created with all required fields."""
        assert str(sample_raw_image.message_id) == "msg123"
        assert sample_raw_image.source_type == SourceType.CHAT
        assert sample_raw_image.original_mime_type == "image/png"

    def test_is_valid_image_type_png(self, sample_raw_image):
        """PNG is a valid image type."""
        assert sample_raw_image.is_valid_image_type is True

    def test_is_valid_image_type_jpeg(self):
        """JPEG is a valid image type."""
        raw = RawImageData(
            message_id=MessageId("msg"),
            source_type=SourceType.CHAT,
            phone_number=PhoneNumber("5511999999999"),
            user_name=UserName("Test"),
            instance=Instance("test-instance"),
            image_bytes=b"jpeg data",
            original_mime_type="image/jpeg",
        )
        assert raw.is_valid_image_type is True

    def test_is_valid_image_type_webp(self):
        """WebP is a valid image type."""
        raw = RawImageData(
            message_id=MessageId("msg"),
            source_type=SourceType.CHAT,
            phone_number=PhoneNumber("5511999999999"),
            user_name=UserName("Test"),
            instance=Instance("test-instance"),
            image_bytes=b"webp data",
            original_mime_type="image/webp",
        )
        assert raw.is_valid_image_type is True

    def test_is_valid_image_type_invalid(self):
        """Video type is not a valid image type."""
        raw = RawImageData(
            message_id=MessageId("msg"),
            source_type=SourceType.CHAT,
            phone_number=PhoneNumber("5511999999999"),
            user_name=UserName("Test"),
            instance=Instance("test-instance"),
            image_bytes=b"video data",
            original_mime_type="video/mp4",
        )
        assert raw.is_valid_image_type is False

    def test_timestamp_defaults_to_now(self):
        """Timestamp defaults to current time."""
        before = datetime.utcnow()
        raw = RawImageData(
            message_id=MessageId("msg"),
            source_type=SourceType.CHAT,
            phone_number=PhoneNumber("5511999999999"),
            user_name=UserName("Test"),
            instance=Instance("test-instance"),
            image_bytes=b"data",
            original_mime_type="image/jpeg",
        )
        after = datetime.utcnow()
        assert before <= raw.timestamp <= after


class TestIngestionResult:
    """Tests for IngestionResult entity."""

    def test_empty_result(self):
        """Empty result has zero counts."""
        result = IngestionResult()
        assert result.total_processed == 0
        assert result.new_images_downloaded == 0
        assert result.duplicates_skipped == 0
        assert result.has_errors is False

    def test_add_success(self):
        """add_success increments counters correctly."""
        result = IngestionResult()
        metadata = ImageMetadata(
            id_secuencial=SequentialId(1),
            id_mensaje=MessageId("msg1"),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Test"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data", "1.jpg"),
            hash_imagen=ImageHash("a" * 64),
        )

        result.add_success(metadata)

        assert result.total_processed == 1
        assert result.new_images_downloaded == 1
        assert result.duplicates_skipped == 0
        assert len(result.downloaded_images) == 1

    def test_add_duplicate(self):
        """add_duplicate increments counters correctly."""
        result = IngestionResult()
        result.add_duplicate()

        assert result.total_processed == 1
        assert result.new_images_downloaded == 0
        assert result.duplicates_skipped == 1

    def test_add_error(self):
        """add_error increments counters and records error."""
        result = IngestionResult()
        result.add_error("Test error message")

        assert result.total_processed == 1
        assert result.has_errors is True
        assert len(result.errors) == 1
        assert "Test error" in result.errors[0]

    def test_success_rate_all_success(self):
        """Success rate is 1.0 when all successful."""
        result = IngestionResult()
        metadata = ImageMetadata(
            id_secuencial=SequentialId(1),
            id_mensaje=MessageId("msg1"),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Test"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data", "1.jpg"),
            hash_imagen=ImageHash("a" * 64),
        )
        result.add_success(metadata)
        result.add_duplicate()

        assert result.success_rate == 1.0

    def test_success_rate_with_errors(self):
        """Success rate accounts for errors."""
        result = IngestionResult()
        metadata = ImageMetadata(
            id_secuencial=SequentialId(1),
            id_mensaje=MessageId("msg1"),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Test"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data", "1.jpg"),
            hash_imagen=ImageHash("a" * 64),
        )
        result.add_success(metadata)
        result.add_error("Error")

        assert result.success_rate == 0.5

    def test_success_rate_empty(self):
        """Success rate is 1.0 when no processing done."""
        result = IngestionResult()
        assert result.success_rate == 1.0

    def test_merge_results(self):
        """Two results can be merged."""
        result1 = IngestionResult()
        result1.add_duplicate()

        result2 = IngestionResult()
        result2.add_error("Error")

        merged = result1.merge(result2)

        assert merged.total_processed == 2
        assert merged.duplicates_skipped == 1
        assert len(merged.errors) == 1

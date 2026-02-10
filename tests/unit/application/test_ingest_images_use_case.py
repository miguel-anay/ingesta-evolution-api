"""
Unit Tests for Image Ingestion Use Cases

Tests for application layer use cases with mocked ports.
"""

import pytest
from datetime import datetime
from typing import AsyncIterator, List, Optional
from unittest.mock import AsyncMock, MagicMock

from src.application.ingestion.use_cases import IngestImagesUseCase
from src.application.ingestion.dto import IngestImagesRequest, IngestImagesResponse
from src.application.ingestion.ports import (
    IImageSourcePort,
    IImageStoragePort,
    IMetadataRepositoryPort,
)
from src.domain.ingestion.entities import RawImageData, ImageMetadata
from src.domain.ingestion.value_objects import (
    SourceType,
    MessageId,
    PhoneNumber,
    UserName,
    SequentialId,
    ImageHash,
    ImagePath,
    Instance,
)
from src.domain.ingestion.exceptions import MissingRequiredParameterError


class MockImageSourcePort(IImageSourcePort):
    """Mock implementation of IImageSourcePort for testing."""

    def __init__(self, chat_images: List[RawImageData] = None, status_images: List[RawImageData] = None):
        self._chat_images = chat_images or []
        self._status_images = status_images or []

    async def fetch_chat_images(
        self, instance_name: str, phone_number: str, limit: Optional[int] = None
    ) -> AsyncIterator[RawImageData]:
        for i, img in enumerate(self._chat_images):
            if limit and i >= limit:
                break
            yield img

    async def fetch_status_images(
        self, instance_name: str, phone_number: str, limit: Optional[int] = None
    ) -> AsyncIterator[RawImageData]:
        for i, img in enumerate(self._status_images):
            if limit and i >= limit:
                break
            yield img

    async def download_media(self, instance_name: str, message_id: str) -> bytes:
        return b"mock image data"

    async def get_available_instances(self) -> List[str]:
        return ["test-instance"]


class MockImageStoragePort(IImageStoragePort):
    """Mock implementation of IImageStoragePort for testing."""

    def __init__(self):
        self._stored_images = {}
        self._hash_counter = 0

    async def store_image(self, image_data: bytes, sequential_id: SequentialId) -> ImagePath:
        path = ImagePath("/data/images", f"{sequential_id.value}.jpg")
        self._stored_images[sequential_id.value] = image_data
        return path

    async def calculate_hash(self, image_data: bytes) -> ImageHash:
        self._hash_counter += 1
        # Generate unique hash based on counter
        hash_value = f"{self._hash_counter:064x}"
        return ImageHash(hash_value)

    async def image_exists(self, path: ImagePath) -> bool:
        return False

    async def ensure_storage_directory(self) -> None:
        pass

    def get_base_directory(self) -> str:
        return "/data/images"

    async def delete_image(self, path: ImagePath) -> bool:
        return True


class MockMetadataRepositoryPort(IMetadataRepositoryPort):
    """Mock implementation of IMetadataRepositoryPort for testing."""

    def __init__(self, existing_message_ids: set = None, existing_hashes: set = None):
        self._records: List[ImageMetadata] = []
        self._existing_message_ids = existing_message_ids or set()
        self._existing_hashes = existing_hashes or set()
        self._next_id = 1

    async def save(self, metadata: ImageMetadata) -> None:
        self._records.append(metadata)
        self._existing_message_ids.add(str(metadata.id_mensaje))
        self._existing_hashes.add(str(metadata.hash_imagen))
        self._next_id = max(self._next_id, metadata.id_secuencial.value + 1)

    async def exists_by_message_id(self, message_id: MessageId) -> bool:
        return str(message_id) in self._existing_message_ids

    async def exists_by_hash(self, image_hash: ImageHash) -> bool:
        return str(image_hash) in self._existing_hashes

    async def get_next_sequential_id(self) -> SequentialId:
        return SequentialId(self._next_id)

    async def get_all(self) -> List[ImageMetadata]:
        return self._records

    async def get_by_sequential_id(self, sequential_id: SequentialId) -> Optional[ImageMetadata]:
        for record in self._records:
            if record.id_secuencial == sequential_id:
                return record
        return None

    async def get_by_message_id(self, message_id: MessageId) -> Optional[ImageMetadata]:
        for record in self._records:
            if record.id_mensaje == message_id:
                return record
        return None

    async def count(self) -> int:
        return len(self._records)

    async def ensure_storage_exists(self) -> None:
        pass


def create_raw_image(
    message_id: str,
    source: SourceType = SourceType.CHAT,
    instance_name: str = "test-instance",
) -> RawImageData:
    """Helper to create a RawImageData for testing."""
    return RawImageData(
        message_id=MessageId(message_id),
        source_type=source,
        phone_number=PhoneNumber("5511999999999"),
        user_name=UserName("Test User"),
        instance=Instance(instance_name),
        image_bytes=b"fake image data",
        original_mime_type="image/jpeg",
        timestamp=datetime.utcnow(),
    )


class TestIngestImagesUseCase:
    """Tests for IngestImagesUseCase."""

    # Default test parameters
    TEST_PHONE = "5511999999999"
    TEST_INSTANCE = "test-instance"

    @pytest.fixture
    def use_case(self):
        """Create use case with fresh mocks."""
        return IngestImagesUseCase(
            image_source=MockImageSourcePort(),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

    @pytest.mark.asyncio
    async def test_ingest_empty_source(self, use_case):
        """Ingestion with no images returns empty result."""
        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.total_processed == 0
        assert response.new_images_downloaded == 0

    @pytest.mark.asyncio
    async def test_ingest_single_chat_image(self):
        """Single chat image is downloaded and stored."""
        raw_image = create_raw_image("msg1", SourceType.CHAT)

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=[raw_image]),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.total_processed == 1
        assert response.new_images_downloaded == 1
        assert response.duplicates_skipped == 0
        assert len(response.downloaded_images) == 1

    @pytest.mark.asyncio
    async def test_ingest_multiple_images(self):
        """Multiple images are downloaded sequentially."""
        raw_images = [
            create_raw_image("msg1"),
            create_raw_image("msg2"),
            create_raw_image("msg3"),
        ]

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=raw_images),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.total_processed == 3
        assert response.new_images_downloaded == 3

        # Check sequential IDs
        ids = [img.id_secuencial for img in response.downloaded_images]
        assert ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_skip_duplicate_by_message_id(self):
        """Images with existing message ID are skipped."""
        raw_image = create_raw_image("existing-msg")

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=[raw_image]),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(
                existing_message_ids={"existing-msg"}
            ),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.total_processed == 1
        assert response.new_images_downloaded == 0
        assert response.duplicates_skipped == 1

    @pytest.mark.asyncio
    async def test_ingest_both_chat_and_status(self):
        """Both chat and status images are ingested when source_type is None."""
        chat_images = [create_raw_image("chat1", SourceType.CHAT)]
        status_images = [create_raw_image("status1", SourceType.STATUS)]

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(
                chat_images=chat_images,
                status_images=status_images,
            ),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=None,  # Both sources
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.total_processed == 2
        assert response.new_images_downloaded == 2

    @pytest.mark.asyncio
    async def test_ingest_with_limit(self):
        """Limit parameter restricts number of images processed."""
        raw_images = [create_raw_image(f"msg{i}") for i in range(10)]

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=raw_images),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
            limit=3,
        )

        response = await use_case.execute(request)

        assert response.total_processed == 3
        assert response.new_images_downloaded == 3

    @pytest.mark.asyncio
    async def test_idempotency_same_request_twice(self):
        """Running same request twice doesn't duplicate images."""
        raw_images = [create_raw_image("msg1"), create_raw_image("msg2")]

        metadata_repo = MockMetadataRepositoryPort()
        storage = MockImageStoragePort()

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=raw_images),
            image_storage=storage,
            metadata_repository=metadata_repo,
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        # First run
        response1 = await use_case.execute(request)
        assert response1.new_images_downloaded == 2

        # Second run - same use case instance with same mocks
        # Reset image source to provide same images again
        use_case._image_source = MockImageSourcePort(chat_images=raw_images)

        response2 = await use_case.execute(request)
        assert response2.new_images_downloaded == 0
        assert response2.duplicates_skipped == 2

    @pytest.mark.asyncio
    async def test_sequential_ids_continue_after_restart(self):
        """Sequential IDs continue from where they left off."""
        # Use shared storage to maintain hash counter state
        shared_storage = MockImageStoragePort()
        metadata_repo = MockMetadataRepositoryPort()

        # First batch
        batch1 = [create_raw_image("msg1"), create_raw_image("msg2")]

        use_case1 = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=batch1),
            image_storage=shared_storage,
            metadata_repository=metadata_repo,
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response1 = await use_case1.execute(request)
        assert response1.downloaded_images[-1].id_secuencial == 2

        # Second batch with same metadata repo (simulating restart)
        batch2 = [create_raw_image("msg3"), create_raw_image("msg4")]

        use_case2 = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=batch2),
            image_storage=shared_storage,  # Same storage
            metadata_repository=metadata_repo,  # Same repo
        )

        response2 = await use_case2.execute(request)

        # IDs should continue from 3
        ids = [img.id_secuencial for img in response2.downloaded_images]
        assert ids == [3, 4]

    @pytest.mark.asyncio
    async def test_response_contains_execution_time(self):
        """Response includes execution time."""
        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.execution_time_seconds >= 0
        assert response.timestamp is not None

    @pytest.mark.asyncio
    async def test_missing_phone_number_raises_error(self):
        """Request without phone number raises MissingRequiredParameterError."""
        with pytest.raises(MissingRequiredParameterError, match="numero_celular"):
            IngestImagesRequest(
                numero_celular="",
                instancia=self.TEST_INSTANCE,
            )

    @pytest.mark.asyncio
    async def test_missing_instance_raises_error(self):
        """Request without instance raises MissingRequiredParameterError."""
        with pytest.raises(MissingRequiredParameterError, match="instancia"):
            IngestImagesRequest(
                numero_celular=self.TEST_PHONE,
                instancia="",
            )

    @pytest.mark.asyncio
    async def test_metadata_includes_instancia(self):
        """Downloaded images metadata includes instancia field."""
        raw_image = create_raw_image("msg1", SourceType.CHAT, "my-instance")

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=[raw_image]),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia="my-instance",
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert len(response.downloaded_images) == 1
        assert response.downloaded_images[0].instancia == "my-instance"

    @pytest.mark.asyncio
    async def test_metadata_includes_numero_celular(self):
        """Downloaded images metadata includes numero_celular field."""
        raw_image = create_raw_image("msg1", SourceType.CHAT)

        use_case = IngestImagesUseCase(
            image_source=MockImageSourcePort(chat_images=[raw_image]),
            image_storage=MockImageStoragePort(),
            metadata_repository=MockMetadataRepositoryPort(),
        )

        request = IngestImagesRequest(
            numero_celular=self.TEST_PHONE,
            instancia=self.TEST_INSTANCE,
            source_type=SourceType.CHAT,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert len(response.downloaded_images) == 1
        assert response.downloaded_images[0].numero_celular == self.TEST_PHONE

"""
Integration Tests for Image Ingestion Adapters

Tests for infrastructure adapters against real implementations.
"""

import os
import tempfile
import pytest
from datetime import datetime
from io import BytesIO

from PIL import Image

from src.infrastructure.storage import FileSystemImageStorageAdapter
from src.infrastructure.persistence.repositories import CsvMetadataRepository
from src.domain.ingestion.value_objects import (
    SequentialId,
    MessageId,
    ImageHash,
    ImagePath,
    PhoneNumber,
    UserName,
    SourceType,
    Instance,
)
from src.domain.ingestion.entities import ImageMetadata
from src.domain.ingestion.exceptions import InvalidImageError, DuplicateImageError


def create_sample_png():
    """Generate a valid 1x1 red PNG image."""
    img = Image.new('RGB', (10, 10), color='red')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def create_sample_jpeg():
    """Generate a valid 1x1 blue JPEG image."""
    img = Image.new('RGB', (10, 10), color='blue')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


class TestFileSystemImageStorageAdapter:
    """Integration tests for FileSystemImageStorageAdapter."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_dir):
        """Create storage adapter with temp directory."""
        return FileSystemImageStorageAdapter(temp_dir)

    @pytest.fixture
    def sample_png(self):
        """Create sample PNG image data."""
        return create_sample_png()

    @pytest.mark.asyncio
    async def test_ensure_storage_directory_creates_dir(self, temp_dir):
        """Storage directory is created if it doesn't exist."""
        new_dir = os.path.join(temp_dir, "new_subdir")
        storage = FileSystemImageStorageAdapter(new_dir)

        await storage.ensure_storage_directory()

        assert os.path.isdir(new_dir)

    @pytest.mark.asyncio
    async def test_store_image_creates_jpeg(self, storage, temp_dir, sample_png):
        """Storing image creates JPEG file."""
        await storage.ensure_storage_directory()

        seq_id = SequentialId(1)
        path = await storage.store_image(sample_png, seq_id)

        assert path.filename == "1.jpg"
        assert os.path.exists(os.path.join(temp_dir, "1.jpg"))

        # Verify file is JPEG (starts with JPEG magic bytes)
        with open(os.path.join(temp_dir, "1.jpg"), "rb") as f:
            header = f.read(2)
            assert header == b"\xff\xd8"

    @pytest.mark.asyncio
    async def test_store_image_sequential_naming(self, storage, temp_dir, sample_png):
        """Images are stored with sequential filenames."""
        await storage.ensure_storage_directory()

        for i in range(1, 4):
            seq_id = SequentialId(i)
            await storage.store_image(sample_png, seq_id)

        assert os.path.exists(os.path.join(temp_dir, "1.jpg"))
        assert os.path.exists(os.path.join(temp_dir, "2.jpg"))
        assert os.path.exists(os.path.join(temp_dir, "3.jpg"))

    @pytest.mark.asyncio
    async def test_calculate_hash_consistent(self, storage, sample_png):
        """Same image data produces same hash."""
        hash1 = await storage.calculate_hash(sample_png)
        hash2 = await storage.calculate_hash(sample_png)

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_calculate_hash_different_data(self, storage, sample_png):
        """Different image data produces different hash."""
        hash1 = await storage.calculate_hash(sample_png)
        hash2 = await storage.calculate_hash(b"different data")

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_calculate_hash_empty_raises_error(self, storage):
        """Empty data raises InvalidImageError."""
        with pytest.raises(InvalidImageError):
            await storage.calculate_hash(b"")

    @pytest.mark.asyncio
    async def test_image_exists_false_when_not_stored(self, storage, temp_dir):
        """image_exists returns False for non-existent file."""
        await storage.ensure_storage_directory()

        path = ImagePath(temp_dir, "999.jpg")
        exists = await storage.image_exists(path)

        assert exists is False

    @pytest.mark.asyncio
    async def test_image_exists_true_when_stored(self, storage, temp_dir, sample_png):
        """image_exists returns True for stored file."""
        await storage.ensure_storage_directory()

        seq_id = SequentialId(42)
        path = await storage.store_image(sample_png, seq_id)

        exists = await storage.image_exists(path)
        assert exists is True

    @pytest.mark.asyncio
    async def test_delete_image(self, storage, temp_dir, sample_png):
        """Stored image can be deleted."""
        await storage.ensure_storage_directory()

        seq_id = SequentialId(1)
        path = await storage.store_image(sample_png, seq_id)

        assert os.path.exists(path.full_path)

        deleted = await storage.delete_image(path)

        assert deleted is True
        assert not os.path.exists(path.full_path)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_image(self, storage, temp_dir):
        """Deleting non-existent image returns False."""
        await storage.ensure_storage_directory()

        path = ImagePath(temp_dir, "999.jpg")
        deleted = await storage.delete_image(path)

        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_base_directory(self, storage, temp_dir):
        """get_base_directory returns correct path."""
        assert storage.get_base_directory() == temp_dir


class TestCsvMetadataRepository:
    """Integration tests for CsvMetadataRepository."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def csv_path(self, temp_dir):
        """Get path for test CSV file."""
        return os.path.join(temp_dir, "metadata", "images.csv")

    @pytest.fixture
    def repository(self, csv_path, temp_dir):
        """Create repository with test CSV file."""
        return CsvMetadataRepository(
            csv_file_path=csv_path,
            images_base_directory=os.path.join(temp_dir, "images"),
        )

    def create_metadata(self, seq_id: int, msg_id: str) -> ImageMetadata:
        """Helper to create test metadata."""
        return ImageMetadata(
            id_secuencial=SequentialId(seq_id),
            id_mensaje=MessageId(msg_id),
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Test User"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data/images", f"{seq_id}.jpg"),
            hash_imagen=ImageHash(f"{seq_id:064x}"),
        )

    @pytest.mark.asyncio
    async def test_ensure_storage_creates_csv(self, repository, csv_path):
        """ensure_storage_exists creates CSV file with headers."""
        await repository.ensure_storage_exists()

        assert os.path.exists(csv_path)

        with open(csv_path, "r") as f:
            header = f.readline().strip()
            assert "id_secuencial" in header
            assert "id_mensaje" in header
            assert "hash_imagen" in header

    @pytest.mark.asyncio
    async def test_save_and_retrieve(self, repository):
        """Saved metadata can be retrieved."""
        await repository.ensure_storage_exists()

        metadata = self.create_metadata(1, "msg1")
        await repository.save(metadata)

        retrieved = await repository.get_by_sequential_id(SequentialId(1))

        assert retrieved is not None
        assert retrieved.id_secuencial.value == 1
        assert str(retrieved.id_mensaje) == "msg1"

    @pytest.mark.asyncio
    async def test_exists_by_message_id(self, repository):
        """exists_by_message_id returns correct result."""
        await repository.ensure_storage_exists()

        metadata = self.create_metadata(1, "existing-msg")
        await repository.save(metadata)

        exists = await repository.exists_by_message_id(MessageId("existing-msg"))
        not_exists = await repository.exists_by_message_id(MessageId("other-msg"))

        assert exists is True
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_exists_by_hash(self, repository):
        """exists_by_hash returns correct result."""
        await repository.ensure_storage_exists()

        metadata = self.create_metadata(1, "msg1")
        await repository.save(metadata)

        existing_hash = ImageHash(f"{1:064x}")
        other_hash = ImageHash(f"{999:064x}")

        exists = await repository.exists_by_hash(existing_hash)
        not_exists = await repository.exists_by_hash(other_hash)

        assert exists is True
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_get_next_sequential_id_empty(self, repository):
        """Next ID is 1 for empty repository."""
        await repository.ensure_storage_exists()

        next_id = await repository.get_next_sequential_id()

        assert next_id.value == 1

    @pytest.mark.asyncio
    async def test_get_next_sequential_id_after_save(self, repository):
        """Next ID increments after save."""
        await repository.ensure_storage_exists()

        for i in range(1, 4):
            metadata = self.create_metadata(i, f"msg{i}")
            await repository.save(metadata)

        next_id = await repository.get_next_sequential_id()

        assert next_id.value == 4

    @pytest.mark.asyncio
    async def test_get_all(self, repository):
        """get_all returns all records sorted by ID."""
        await repository.ensure_storage_exists()

        # Save in random order
        await repository.save(self.create_metadata(3, "msg3"))
        await repository.save(self.create_metadata(1, "msg1"))
        await repository.save(self.create_metadata(2, "msg2"))

        all_records = await repository.get_all()

        assert len(all_records) == 3
        assert all_records[0].id_secuencial.value == 1
        assert all_records[1].id_secuencial.value == 2
        assert all_records[2].id_secuencial.value == 3

    @pytest.mark.asyncio
    async def test_count(self, repository):
        """count returns correct number of records."""
        await repository.ensure_storage_exists()

        assert await repository.count() == 0

        await repository.save(self.create_metadata(1, "msg1"))
        await repository.save(self.create_metadata(2, "msg2"))

        assert await repository.count() == 2

    @pytest.mark.asyncio
    async def test_duplicate_message_id_raises_error(self, repository):
        """Saving duplicate message ID raises DuplicateImageError."""
        await repository.ensure_storage_exists()

        metadata1 = self.create_metadata(1, "duplicate-msg")
        await repository.save(metadata1)

        metadata2 = ImageMetadata(
            id_secuencial=SequentialId(2),
            id_mensaje=MessageId("duplicate-msg"),  # Same message ID
            tipo_origen=SourceType.CHAT,
            fecha_descarga=datetime.utcnow(),
            numero_celular=PhoneNumber("5511999999999"),
            nombre_usuario=UserName("Test"),
            instancia=Instance("test-instance"),
            ruta_archivo=ImagePath("/data/images", "2.jpg"),
            hash_imagen=ImageHash(f"{999:064x}"),  # Different hash
        )

        with pytest.raises(DuplicateImageError):
            await repository.save(metadata2)

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, csv_path, temp_dir):
        """Data persists when creating new repository instance."""
        # First instance
        repo1 = CsvMetadataRepository(csv_path, os.path.join(temp_dir, "images"))
        await repo1.ensure_storage_exists()
        await repo1.save(self.create_metadata(1, "msg1"))
        await repo1.save(self.create_metadata(2, "msg2"))

        # New instance with same file
        repo2 = CsvMetadataRepository(csv_path, os.path.join(temp_dir, "images"))

        count = await repo2.count()
        next_id = await repo2.get_next_sequential_id()

        assert count == 2
        assert next_id.value == 3

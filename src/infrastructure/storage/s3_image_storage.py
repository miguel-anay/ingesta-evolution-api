"""
S3 Image Storage Adapter

Infrastructure adapter that implements IImageStoragePort
for storing images to AWS S3 / MinIO.
"""

import asyncio
import hashlib
import logging
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from ...application.ingestion.ports import IImageStoragePort
from ...domain.ingestion.value_objects import ImagePath, SequentialId, ImageHash
from ...domain.ingestion.exceptions import StorageError, InvalidImageError
from .image_converter import convert_to_jpeg


logger = logging.getLogger(__name__)


class S3ImageStorageAdapter(IImageStoragePort):
    """
    Adapter for storing images to S3-compatible storage (AWS S3 / MinIO).

    Implements IImageStoragePort to provide:
    - Image upload with sequential filenames
    - Automatic conversion to JPEG format
    - SHA-256 hash calculation for deduplication
    - Bucket management
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "images/",
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket_name = bucket_name
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""

        kwargs: dict = {"region_name": region}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key

        self._s3 = boto3.client("s3", **kwargs)
        logger.info(f"Initialized S3 storage: bucket={bucket_name}, prefix={self._prefix}")

    async def store_image(
        self,
        image_data: bytes,
        sequential_id: SequentialId,
    ) -> ImagePath:
        """Store an image to S3 with the given sequential ID."""
        filename = f"{sequential_id.value}.jpg"
        s3_key = f"{self._prefix}{filename}"

        try:
            jpeg_data = await asyncio.get_event_loop().run_in_executor(
                None, convert_to_jpeg, image_data
            )

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.put_object(
                    Bucket=self._bucket_name,
                    Key=s3_key,
                    Body=jpeg_data,
                    ContentType="image/jpeg",
                ),
            )

            logger.info(f"Stored image {sequential_id} to s3://{self._bucket_name}/{s3_key}")

            return ImagePath(base_directory=f"s3://{self._bucket_name}/{self._prefix}", filename=filename)

        except InvalidImageError:
            raise
        except ClientError as e:
            raise StorageError(operation="upload", path=s3_key, reason=str(e))
        except Exception as e:
            raise StorageError(operation="store", path=s3_key, reason=f"Unexpected error: {str(e)}")

    async def calculate_hash(self, image_data: bytes) -> ImageHash:
        """Calculate SHA-256 hash of image data."""
        if not image_data:
            raise InvalidImageError(reason="Empty image data", message_id=None)

        hash_value = await asyncio.get_event_loop().run_in_executor(
            None, lambda: hashlib.sha256(image_data).hexdigest()
        )
        return ImageHash(hash_value)

    async def image_exists(self, path: ImagePath) -> bool:
        """Check if an image exists in S3."""
        s3_key = f"{self._prefix}{path.filename}"
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.head_object(Bucket=self._bucket_name, Key=s3_key),
            )
            return True
        except ClientError:
            return False

    async def ensure_storage_directory(self) -> None:
        """Ensure S3 bucket exists. Creates it if running with MinIO."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.head_bucket(Bucket=self._bucket_name),
            )
        except ClientError:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._s3.create_bucket(Bucket=self._bucket_name),
                )
                logger.info(f"Created S3 bucket: {self._bucket_name}")
            except ClientError as e:
                raise StorageError(
                    operation="create_bucket",
                    path=self._bucket_name,
                    reason=str(e),
                )

    def get_base_directory(self) -> str:
        return f"s3://{self._bucket_name}/{self._prefix}"

    async def delete_image(self, path: ImagePath) -> bool:
        """Delete an image from S3."""
        s3_key = f"{self._prefix}{path.filename}"
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.delete_object(Bucket=self._bucket_name, Key=s3_key),
            )
            logger.info(f"Deleted image: s3://{self._bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.warning(f"Failed to delete {s3_key}: {e}")
            return False

    async def download_image(self, s3_key: str) -> bytes:
        """Download image bytes from S3. Used by workers."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._s3.get_object(Bucket=self._bucket_name, Key=s3_key),
            )
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: response["Body"].read()
            )
        except ClientError as e:
            raise StorageError(operation="download", path=s3_key, reason=str(e))

    def get_s3_key(self, sequential_id: SequentialId) -> str:
        """Get the S3 key for a given sequential ID."""
        return f"{self._prefix}{sequential_id.value}.jpg"

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for an S3 object (default 1 hour)."""
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": s3_key},
            ExpiresIn=expiration,
        )

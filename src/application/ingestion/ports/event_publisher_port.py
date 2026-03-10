"""
Ingestion Event Publisher Port

Defines the interface for publishing ingestion events to message queues.
This is a DRIVEN port (outbound).
"""

from abc import ABC, abstractmethod


class IIngestionEventPort(ABC):
    """
    Port for publishing image processing events.

    After an image is uploaded to S3 and metadata saved,
    events are published for async workers (OCR, CLIP).
    """

    @abstractmethod
    async def publish_image_ready(self, metadata_id: int, s3_key: str) -> None:
        """
        Publish an event indicating an image is ready for processing.

        Workers (CLIP, OCR) will consume this event.

        Args:
            metadata_id: Database ID of the image metadata record
            s3_key: S3 object key where image is stored

        Raises:
            IngestionError: If publishing fails
        """
        pass

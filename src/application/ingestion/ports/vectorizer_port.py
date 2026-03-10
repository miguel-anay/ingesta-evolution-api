"""
Vectorizer Port

Defines the interface for generating vector embeddings from images and text.
This is a DRIVEN port (outbound).
"""

from abc import ABC, abstractmethod

from ....domain.ingestion.value_objects import ImageEmbedding, TextEmbedding


class IVectorizerPort(ABC):
    """
    Port for generating vector embeddings.

    Multimodal models embed both images and text into the same vector space,
    enabling cross-modal similarity search.
    """

    @abstractmethod
    async def embed_image(self, image_data: bytes) -> ImageEmbedding:
        """
        Generate a vector embedding from image bytes.

        Args:
            image_data: Raw image bytes (JPEG/PNG)

        Returns:
            ImageEmbedding with 1024-dim vector

        Raises:
            VectorizationError: If embedding generation fails
        """
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> TextEmbedding:
        """
        Generate a vector embedding from text.

        Args:
            text: Text string to embed

        Returns:
            TextEmbedding with 1024-dim vector

        Raises:
            VectorizationError: If embedding generation fails
        """
        pass

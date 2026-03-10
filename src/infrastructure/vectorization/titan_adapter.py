"""
AWS Titan Multimodal Embeddings Adapter (Bedrock)

Infrastructure adapter that implements IVectorizerPort
for generating vector embeddings using Amazon Titan Multimodal
Embeddings via AWS Bedrock.

Produces 1024-dimensional embeddings for both images and text.
"""

import asyncio
import base64
import json
import logging

import boto3

from ...application.ingestion.ports.vectorizer_port import IVectorizerPort
from ...domain.ingestion.value_objects import ImageEmbedding, TextEmbedding
from ...domain.ingestion.exceptions import VectorizationError


logger = logging.getLogger(__name__)


class TitanVectorizerAdapter(IVectorizerPort):
    """
    AWS Titan Multimodal Embeddings adapter via Bedrock.

    Generates 1024-dimensional embeddings for both images and text
    in the same vector space, enabling cross-modal similarity search.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "amazon.titan-embed-image-v1",
    ) -> None:
        self._model_id = model_id
        self._client = boto3.client("bedrock-runtime", region_name=region)
        logger.info(f"Titan adapter initialized: model={model_id}, region={region}")

    async def embed_image(self, image_data: bytes) -> ImageEmbedding:
        """Generate a 1024-dim embedding from image bytes via Titan."""
        try:
            values = await asyncio.get_event_loop().run_in_executor(
                None, self._do_image_embedding, image_data
            )
            return ImageEmbedding(values=tuple(values))
        except VectorizationError:
            raise
        except Exception as e:
            raise VectorizationError(
                reason=f"Titan image embedding failed: {e}", vector_type="image"
            )

    async def embed_text(self, text: str) -> TextEmbedding:
        """Generate a 1024-dim embedding from text via Titan."""
        try:
            values = await asyncio.get_event_loop().run_in_executor(
                None, self._do_text_embedding, text
            )
            return TextEmbedding(values=tuple(values))
        except VectorizationError:
            raise
        except Exception as e:
            raise VectorizationError(
                reason=f"Titan text embedding failed: {e}", vector_type="text"
            )

    def _do_image_embedding(self, image_data: bytes) -> list[float]:
        """Synchronous image embedding via Bedrock invoke_model."""
        try:
            body = json.dumps({
                "inputImage": base64.b64encode(image_data).decode("utf-8"),
            })
            response = self._client.invoke_model(
                modelId=self._model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except Exception as e:
            raise VectorizationError(
                reason=f"Bedrock image invoke failed: {e}", vector_type="image"
            )

    def _do_text_embedding(self, text: str) -> list[float]:
        """Synchronous text embedding via Bedrock invoke_model."""
        try:
            body = json.dumps({
                "inputText": text,
            })
            response = self._client.invoke_model(
                modelId=self._model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except Exception as e:
            raise VectorizationError(
                reason=f"Bedrock text invoke failed: {e}", vector_type="text"
            )

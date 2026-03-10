"""
CLIP Vectorizer Adapter (ONNX Runtime)

Infrastructure adapter that implements IVectorizerPort
for generating vector embeddings using CLIP ViT-B/32 via ONNX Runtime.

Uses pre-exported ONNX models instead of PyTorch for ~700MB smaller footprint.
"""

import asyncio
import logging
import os
from io import BytesIO

import numpy as np
import onnxruntime as ort
from PIL import Image
from transformers import CLIPProcessor

from ...application.ingestion.ports.vectorizer_port import IVectorizerPort
from ...domain.ingestion.value_objects import ImageEmbedding, TextEmbedding
from ...domain.ingestion.exceptions import VectorizationError


logger = logging.getLogger(__name__)


class ClipVectorizerAdapter(IVectorizerPort):
    """
    CLIP ViT-B/32 vectorizer adapter using ONNX Runtime.

    Generates 512-dimensional L2-normalized embeddings for both
    images and text in the same vector space.
    """

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        cache_dir: str | None = None,
    ) -> None:
        model_dir = cache_dir or "/app/models"
        vision_path = os.path.join(model_dir, "clip_vision.onnx")
        text_path = os.path.join(model_dir, "clip_text.onnx")
        processor_path = os.path.join(model_dir, "processor")

        # Load processor from local dir if available, otherwise download
        if os.path.isdir(processor_path):
            logger.info(f"Loading CLIP processor from {processor_path}")
            self._processor = CLIPProcessor.from_pretrained(processor_path)
        else:
            logger.info(f"Loading CLIP processor from {model_name}")
            self._processor = CLIPProcessor.from_pretrained(model_name, cache_dir=model_dir)

        # Load ONNX sessions
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.inter_op_num_threads = 2
        sess_options.intra_op_num_threads = 2

        logger.info(f"Loading CLIP ONNX vision model: {vision_path}")
        self._image_session = ort.InferenceSession(vision_path, sess_options)

        logger.info(f"Loading CLIP ONNX text model: {text_path}")
        self._text_session = ort.InferenceSession(text_path, sess_options)

        logger.info("CLIP ONNX models loaded successfully")

    async def embed_image(self, image_data: bytes) -> ImageEmbedding:
        """Generate a 512-dim normalized embedding from image bytes."""
        try:
            values = await asyncio.get_event_loop().run_in_executor(
                None, self._do_image_embedding, image_data
            )
            return ImageEmbedding(values=tuple(values))
        except VectorizationError:
            raise
        except Exception as e:
            raise VectorizationError(reason=f"CLIP image embedding failed: {str(e)}", vector_type="image")

    async def embed_text(self, text: str) -> TextEmbedding:
        """Generate a 512-dim normalized embedding from text."""
        try:
            values = await asyncio.get_event_loop().run_in_executor(
                None, self._do_text_embedding, text
            )
            return TextEmbedding(values=tuple(values))
        except VectorizationError:
            raise
        except Exception as e:
            raise VectorizationError(reason=f"CLIP text embedding failed: {str(e)}", vector_type="text")

    def _do_image_embedding(self, image_data: bytes) -> list[float]:
        """Synchronous image embedding generation via ONNX Runtime."""
        try:
            image = Image.open(BytesIO(image_data))
            if image.mode != "RGB":
                image = image.convert("RGB")

            inputs = self._processor(images=image, return_tensors="np")
            outputs = self._image_session.run(None, {"pixel_values": inputs["pixel_values"]})
            features = outputs[0]

            # L2 normalize
            features = features / np.linalg.norm(features, axis=-1, keepdims=True)
            return features.squeeze().tolist()
        except Exception as e:
            raise VectorizationError(reason=f"Failed to process image: {str(e)}", vector_type="image")

    def _do_text_embedding(self, text: str) -> list[float]:
        """Synchronous text embedding generation via ONNX Runtime."""
        try:
            inputs = self._processor(
                text=[text], return_tensors="np", padding=True, truncation=True, max_length=77
            )
            outputs = self._text_session.run(
                None,
                {
                    "input_ids": inputs["input_ids"].astype(np.int64),
                    "attention_mask": inputs["attention_mask"].astype(np.int64),
                },
            )
            features = outputs[0]

            # L2 normalize
            features = features / np.linalg.norm(features, axis=-1, keepdims=True)
            return features.squeeze().tolist()
        except Exception as e:
            raise VectorizationError(reason=f"Failed to process text: {str(e)}", vector_type="text")

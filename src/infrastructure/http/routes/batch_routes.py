"""
Batch Processing API Routes

Endpoints consumed by AWS Lambda to process pending images.
Lambda calls these instead of connecting directly to the database.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import get_metadata_repository, get_image_storage


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["Batch Processing"])


class PendingImageResponse(BaseModel):
    id: int
    s3_key: str
    processing_status: str


class CompleteRequest(BaseModel):
    texto_ocr: Optional[str] = None
    image_embedding: Optional[list[float]] = None
    text_embedding: Optional[list[float]] = None
    processing_status: str = "completed"


class CompleteResponse(BaseModel):
    id: int
    status: str
    message: str


@router.get("/pending", response_model=list[PendingImageResponse])
async def get_pending_images(
    limit: int = 100,
    repository=Depends(get_metadata_repository),
):
    """Get all images pending processing (for Lambda batch processor)."""
    pending = await repository.get_pending()
    results = [
        PendingImageResponse(
            id=record.id,
            s3_key=record.s3_key,
            processing_status=record.processing_status,
        )
        for record in pending[:limit]
    ]
    logger.info(f"Returning {len(results)} pending images for batch processing")
    return results


@router.patch("/{image_id}/complete", response_model=CompleteResponse)
async def complete_image_processing(
    image_id: int,
    request: CompleteRequest,
    repository=Depends(get_metadata_repository),
):
    """Update a processed image with OCR text and embeddings (called by Lambda)."""
    record = await repository.get_by_id(image_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")

    try:
        if request.texto_ocr is not None:
            await repository.update_ocr_text(image_id, request.texto_ocr)

        if request.image_embedding is not None:
            await repository.update_image_embedding(image_id, request.image_embedding)

        if request.text_embedding is not None:
            await repository.update_text_embedding(image_id, request.text_embedding)

        await repository.update_processing_status(image_id, request.processing_status)

        logger.info(f"Image {image_id} processing completed via API")
        return CompleteResponse(
            id=image_id,
            status=request.processing_status,
            message="Processing results saved successfully",
        )

    except Exception as e:
        logger.error(f"Failed to update image {image_id}: {e}")
        await repository.update_processing_status(image_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))

"""
Search API Routes

Endpoints for searching images by similarity (image, text, hybrid).
Uses Titan Multimodal Embeddings (1024 dims) + pgvector cosine distance.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel

from ..dependencies import get_metadata_repository, get_vectorizer_adapter, get_image_storage


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])


class SearchResult(BaseModel):
    id: int
    id_secuencial: int
    id_mensaje: str
    tipo_origen: str
    numero_celular: str
    nombre_usuario: str
    instancia: str
    s3_key: Optional[str] = None
    texto_ocr: Optional[str] = None
    processing_status: str = "pending"
    similarity_score: float = 0.0
    image_url: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query_type: str


@router.post("/by-image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(...),
    limit: int = Form(10),
    repository=Depends(get_metadata_repository),
    vectorizer=Depends(get_vectorizer_adapter),
    storage=Depends(get_image_storage),
):
    """
    Search for similar images by uploading an image.

    Generates a Titan embedding from the uploaded image and finds
    the most similar images by cosine similarity on image_embedding.
    """
    if vectorizer is None:
        raise HTTPException(status_code=503, detail="Embeddings vectorizer not available")

    image_data = await image.read()
    embedding = await vectorizer.embed_image(image_data)

    results = await repository.search_by_image_embedding(embedding.to_list(), limit=limit)

    return SearchResponse(
        results=[_model_to_result(r, storage) for r in results],
        total=len(results),
        query_type="by-image",
    )


@router.post("/by-text", response_model=SearchResponse)
async def search_by_text(
    query: str = Form(...),
    limit: int = Form(10),
    repository=Depends(get_metadata_repository),
    vectorizer=Depends(get_vectorizer_adapter),
    storage=Depends(get_image_storage),
):
    """
    Search for images by text query.

    Generates a Titan text embedding and finds similar images
    by cosine similarity on text_embedding.
    """
    if vectorizer is None:
        raise HTTPException(status_code=503, detail="Embeddings vectorizer not available")

    text_embedding = await vectorizer.embed_text(query)

    results = await repository.search_by_text_embedding(text_embedding.to_list(), limit=limit)

    return SearchResponse(
        results=[_model_to_result(r, storage) for r in results],
        total=len(results),
        query_type="by-text",
    )


@router.post("/hybrid", response_model=SearchResponse)
async def search_hybrid(
    query: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    limit: int = Form(10),
    repository=Depends(get_metadata_repository),
    vectorizer=Depends(get_vectorizer_adapter),
    storage=Depends(get_image_storage),
):
    """
    Hybrid search combining image and text similarity.

    If both image and text are provided, results from both searches
    are merged and deduplicated, prioritizing items found in both.
    """
    if vectorizer is None:
        raise HTTPException(status_code=503, detail="Embeddings vectorizer not available")

    if not query and not image:
        raise HTTPException(status_code=400, detail="Provide at least a query text or an image")

    seen_ids = set()
    combined_results = []

    if image:
        image_data = await image.read()
        img_embedding = await vectorizer.embed_image(image_data)
        img_results = await repository.search_by_image_embedding(img_embedding.to_list(), limit=limit)
        for r in img_results:
            model = r[0] if isinstance(r, tuple) else r
            if model.id not in seen_ids:
                seen_ids.add(model.id)
                combined_results.append(r)

    if query:
        txt_embedding = await vectorizer.embed_text(query)
        txt_results = await repository.search_by_text_embedding(txt_embedding.to_list(), limit=limit)
        for r in txt_results:
            model = r[0] if isinstance(r, tuple) else r
            if model.id not in seen_ids:
                seen_ids.add(model.id)
                combined_results.append(r)

    return SearchResponse(
        results=[_model_to_result(r, storage) for r in combined_results[:limit]],
        total=len(combined_results[:limit]),
        query_type="hybrid",
    )


def _model_to_result(row, storage=None) -> SearchResult:
    """Convert query result (model + score) to search result."""
    # row can be a tuple (model, distance) or just a model
    if isinstance(row, tuple):
        model, distance = row
        similarity = 1.0 - float(distance)
    else:
        model = row
        similarity = 0.0

    image_url = None
    if storage and model.s3_key:
        try:
            image_url = storage.generate_presigned_url(model.s3_key)
        except Exception:
            pass

    return SearchResult(
        id=model.id,
        id_secuencial=model.id_secuencial,
        id_mensaje=model.id_mensaje,
        tipo_origen=model.tipo_origen,
        numero_celular=model.numero_celular,
        nombre_usuario=model.nombre_usuario,
        instancia=model.instancia,
        s3_key=model.s3_key,
        texto_ocr=model.texto_ocr,
        processing_status=model.processing_status,
        similarity_score=round(similarity, 4),
        image_url=image_url,
    )

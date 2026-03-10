# Image Ingestion Service - Project Specifications

## Project Description

Image Ingestion Service is a Python-based microservice responsible for downloading images from **Evolution API** (chat messages and user status), storing them in **AWS S3**, extracting text via **OCR (Tesseract)**, generating vector embeddings via **CLIP ViT-B/32**, and registering all metadata in **PostgreSQL with pgvector**.

The service guarantees **idempotent ingestion**, meaning it can be executed multiple times without downloading the same image twice.
The generated dataset supports **training, RAG, vectorization pipelines, and similarity search** (by image, by text, and hybrid).

The service operates **per user and per instance**, ensuring controlled and deterministic ingestion.

Processing (OCR + vectorization) runs as a **batch process** (on-demand or nightly via AWS Fargate + EventBridge).

---

## System Architecture

```
Imagen llega → FastAPI → Dedup Check → S3 Upload
                              │
                    INSERT metadata (status='pending')


Batch Processor (on-demand / nightly cron)
  ┌─────────────────────────────────────────┐
  │  for each pending image:                │
  │    1. Download from S3                  │
  │    2. OCR (Tesseract/Textract)          │
  │    3. CLIP image embedding              │
  │    4. CLIP text embedding (if OCR text) │
  │    5. Mark completed                    │
  └─────────────────────────────────────────┘
                              │
                              ▼
            PostgreSQL + pgvector (MISMA BD, MISMA TABLA)
                              │
                              ▼
                   Search API (by-image, by-text, hybrid)
```

### Key Decisions
1. **Single database** for vectors and metadata - one table, transactional consistency
2. **Tesseract first** (free), Textract selective for low confidence (future)
3. **CLIP ViT-B/32** - 512 dims, text+image same vector space, ~800MB RAM
4. **pgvector/pgvector:pg15** in Docker
5. **MinIO** for S3-compatible local storage in development

---

## Execution Parameters

The service requires the following **mandatory parameters** for execution:

| Parameter        | Type   | Description                             |
| ---------------- | ------ | --------------------------------------- |
| `numero_celular` | string | User phone number to ingest images from |
| `instancia`      | string | Evolution API instance identifier       |

❗ Both parameters are **required**.
❌ The ingestion process must not start if any parameter is missing.

---

## User Stories

### Epic 1: Image Ingestion from Evolution API

#### US-ING-001: Download images from chats and user statuses by user and instance

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to download images from chats and user status published via Evolution API,
Filtered by **phone number** and **instance**,
So that I can build a clean, structured dataset for AI processing without duplication.

**Acceptance Criteria:**
- Retrieve images from chat messages and user status (stories)
- Filter by `numero_celular` and `instancia`
- Only image messages processed (videos, audios, stickers ignored)
- Sequential numeric filenames (1.jpg, 2.jpg, 3.jpg)
- Idempotent: duplicate images are not re-downloaded
- Deduplication by `id_mensaje` and `hash_imagen`
- All images normalized to JPEG format

---

### Epic 2: Cloud Storage (S3)

#### US-S3-001: Store images in S3 instead of local filesystem

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to store downloaded images in AWS S3 (or MinIO for local dev),
So that images are durable, scalable, and accessible from any service.

**Acceptance Criteria:**
- Images uploaded to S3 after JPEG conversion
- Sequential naming preserved as S3 keys: `images/1.jpg`, `images/2.jpg`
- S3 bucket, region, and credentials configurable via environment variables
- MinIO used as S3-compatible storage in development
- Existing `IImageStoragePort` interface reused (new S3 adapter)
- SHA-256 hash calculated before upload for deduplication
- JPEG conversion logic extracted to shared utility (`image_converter.py`)

**Implemented in:**
- `src/infrastructure/storage/s3_image_storage.py` — `S3ImageStorageAdapter`
- `src/infrastructure/storage/image_converter.py` — shared JPEG conversion
- `src/config/settings.py` — S3 settings (`s3_bucket_name`, `s3_prefix`, `s3_endpoint_url`, etc.)
- `src/infrastructure/http/dependencies.py` — `get_image_storage()` switches S3/filesystem via `storage_backend`
- `docker-compose.yml` — MinIO service (ports 9000/9001)

---

### Epic 3: PostgreSQL + pgvector Persistence

#### US-PG-001: Store metadata in PostgreSQL with pgvector support

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to persist image metadata in PostgreSQL with pgvector extension,
So that I can store vector embeddings alongside metadata in a single transactional database.

**Acceptance Criteria:**
- PostgreSQL replaces CSV as the metadata store
- Existing `IMetadataRepositoryPort` interface reused (new Postgres adapter)
- SQLAlchemy async + asyncpg for database access
- pgvector extension enabled for vector columns
- Alembic used for database migrations
- Table schema includes all existing fields plus:
  - `s3_key` (VARCHAR 512)
  - `texto_ocr` (TEXT)
  - `image_embedding` (vector 512)
  - `text_embedding` (vector 512)
  - `processing_status` (VARCHAR 20, default 'pending')
  - `created_at`, `updated_at` (TIMESTAMP)
- HNSW indexes on `image_embedding` and `text_embedding` for cosine similarity
- Unique indexes on `id_secuencial`, `id_mensaje`, `hash_imagen`
- Docker image: `pgvector/pgvector:pg15`

**Implemented in:**
- `src/infrastructure/persistence/database.py` — `DatabaseManager` (async engine + session factory)
- `src/infrastructure/persistence/models/image_metadata_model.py` — SQLAlchemy model con pgvector
- `src/infrastructure/persistence/repositories/postgres_metadata_repository.py` — `PostgresMetadataRepository`
- `src/domain/ingestion/value_objects.py` — `OcrText`, `ImageEmbedding`, `TextEmbedding`, `ProcessingStatus`
- `src/domain/ingestion/entities.py` — `ImageMetadata` extendida con campos nuevos
- `alembic/` — Alembic setup + migration 001 (CREATE EXTENSION vector, tabla, HNSW indexes)
- `docker-compose.yml` — `pgvector/pgvector:pg15` + BD `whatsapp_ingestion`

---

### Epic 4: OCR (Optical Character Recognition)

#### US-OCR-001: Extract text from images using Tesseract OCR

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to extract text from downloaded images using Tesseract OCR,
So that text content within images is searchable and can be used for text-based similarity search.

**Acceptance Criteria:**
- Tesseract OCR processes each image asynchronously (via RabbitMQ worker)
- Languages supported: Spanish + English (`spa+eng`)
- OCR runs in a dedicated worker (`worker-ocr`)
- Worker downloads image from S3, extracts text, saves to PostgreSQL `texto_ocr` field
- OCR failure is non-fatal: image metadata is preserved with `texto_ocr = NULL`
- New port: `IOcrPort` with method `extract_text(image_data: bytes) -> OcrText`
- New adapter: `TesseractOcrAdapter` using pytesseract + PIL
- OCR execution in thread pool (`run_in_executor`) to avoid blocking async loop
- After OCR completes, publishes to `text.embedding` queue for text vectorization

**Implemented in:**
- `src/application/ingestion/ports/ocr_port.py` — `IOcrPort`
- `src/infrastructure/ocr/tesseract_adapter.py` — `TesseractOcrAdapter`
- `src/workers/ocr_worker.py` — `OcrWorker` (consume + publish a `text.embedding`)
- `src/domain/ingestion/exceptions.py` — `OcrError`
- `Dockerfile` — `tesseract-ocr`, `tesseract-ocr-spa`, `tesseract-ocr-eng`

---

### Epic 5: CLIP Vectorization

#### US-VEC-001: Generate image embeddings using CLIP ViT-B/32

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to generate vector embeddings for each image using CLIP ViT-B/32,
So that I can perform similarity search across images.

**Acceptance Criteria:**
- CLIP model: `openai/clip-vit-base-patch32` (512 dimensions)
- Model loaded once as singleton (pre-downloaded in Docker build)
- Runs in dedicated worker (`worker-clip`)
- Worker downloads image from S3, generates embedding, saves to PostgreSQL `image_embedding` field
- Vectors L2-normalized before storage
- New port: `IVectorizerPort` with methods:
  - `embed_image(image_data: bytes) -> ImageEmbedding`
  - `embed_text(text: str) -> TextEmbedding`
- New adapter: `ClipVectorizerAdapter` using transformers + torch (CPU)
- Model inference in thread pool (`run_in_executor`)

**Implemented in:**
- `src/application/ingestion/ports/vectorizer_port.py` — `IVectorizerPort`
- `src/infrastructure/vectorization/clip_adapter.py` — `ClipVectorizerAdapter`
- `src/workers/clip_worker.py` — `ClipWorker`
- `src/domain/ingestion/value_objects.py` — `ImageEmbedding`, `TextEmbedding`
- `src/domain/ingestion/exceptions.py` — `VectorizationError`
- `Dockerfile` — stage `model-downloader` pre-descarga CLIP

#### US-VEC-002: Generate text embeddings from OCR output using CLIP

**Status:** ✅ COMPLETED

As a data ingestion system,
I want to generate vector embeddings from the OCR-extracted text using CLIP,
So that I can perform text-based similarity search in the same vector space as images.

**Acceptance Criteria:**
- Runs in dedicated worker (`worker-text-embedding`)
- Triggered after OCR worker completes (consumes from `text.embedding` queue)
- Uses same CLIP model to embed text into 512-dimensional vector
- Saves to PostgreSQL `text_embedding` field
- When both `image_embedding` and `text_embedding` are complete, updates `processing_status = 'completed'`

**Implemented in:**
- `src/workers/text_embedding_worker.py` — `TextEmbeddingWorker`

---

### Epic 6: Async Processing with RabbitMQ Workers

#### US-WRK-001: Asynchronous image processing pipeline via RabbitMQ

**Status:** ✅ COMPLETED

As a data ingestion system,
I want the OCR and vectorization to run asynchronously via RabbitMQ workers,
So that the ingestion endpoint responds immediately and processing scales independently.

**Acceptance Criteria:**
- Ingestion endpoint returns immediately after S3 upload + DB insert (status='pending')
- RabbitMQ queues:
  - `image.processing.clip` - for CLIP image embedding
  - `image.processing.ocr` - for Tesseract OCR
  - `text.embedding` - for CLIP text embedding (triggered after OCR)
- New port: `IIngestionEventPort` with method `publish_image_ready(metadata_id, s3_key)`
- New adapter: `RabbitMqIngestionPublisher` using aio-pika
- Worker base class with: RabbitMQ connection, retry logic, error handling
- Workers run as separate Docker services (same Dockerfile, different CMD)
- Processing failure is non-fatal: metadata persists, status set to 'failed'

**Implemented in:**
- `src/application/ingestion/ports/event_publisher_port.py` — `IIngestionEventPort`
- `src/infrastructure/messaging/rabbitmq/ingestion_publisher.py` — `RabbitMqIngestionPublisher`
- `src/workers/base_worker.py` — `BaseWorker` (conexion, retry, error handling)
- `src/workers/clip_worker.py`, `ocr_worker.py`, `text_embedding_worker.py` — workers
- `src/application/ingestion/use_cases/ingest_images.py` — modificado para publicar eventos
- `docker-compose.yml` — servicios `worker-clip`, `worker-ocr`, `worker-text-embedding`

---

### Epic 7: Similarity Search API

#### US-SRC-001: Search images by similarity

**Status:** ✅ COMPLETED

As an API consumer,
I want to search for similar images using image upload, text query, or hybrid search,
So that I can find relevant images from the ingested dataset.

**Acceptance Criteria:**
- `POST /api/v1/search/by-image` - upload image, find similar images via cosine similarity on `image_embedding`
- `POST /api/v1/search/by-text` - text query, embed with CLIP, search on `text_embedding`
- `POST /api/v1/search/hybrid` - combine image + text similarity scores
- Results include metadata, similarity score, and S3 URL
- Pagination support (limit, offset)
- Only searches images with `processing_status = 'completed'`

**Implemented in:**
- `src/infrastructure/http/routes/search_routes.py` — endpoints `by-image`, `by-text`, `hybrid`
- `src/infrastructure/persistence/repositories/postgres_metadata_repository.py` — `search_by_image_embedding()`, `search_by_text_embedding()`
- `src/main.py` — `search_router` registrado en `/api/v1`

---

### Epic 8: AWS Textract OCR Adapter

#### US-OCR-002: Textract OCR with auto-fallback

**Status:** ✅ COMPLETED

As an operator,
I want to choose between Tesseract (free/local), AWS Textract (cloud/paid), or auto-fallback mode,
So that I can balance cost and OCR accuracy based on my needs.

**Acceptance Criteria:**
- `OCR_BACKEND=tesseract` → uses Tesseract only (default, no change in behavior)
- `OCR_BACKEND=textract` → uses AWS Textract directly (requires AWS credentials)
- `OCR_BACKEND=auto` → tries Tesseract first, falls back to Textract if result is empty or too short (< 10 chars)
- Textract adapter uses `detect_document_text()` API, extracts LINE blocks
- All adapters implement `IOcrPort` interface (hexagonal architecture)
- Without valid AWS credentials, Textract fails gracefully with warning log

**Configuration:**
- `OCR_BACKEND` — `tesseract` | `textract` | `auto` (default: `tesseract`)
- `TEXTRACT_REGION` — AWS region (default: `us-east-1`)
- `TEXTRACT_ACCESS_KEY_ID` — AWS access key (optional)
- `TEXTRACT_SECRET_ACCESS_KEY` — AWS secret key (optional)

**Implemented in:**
- `src/infrastructure/ocr/textract_adapter.py` — `TextractOcrAdapter` implements `IOcrPort`
- `src/infrastructure/ocr/auto_ocr_adapter.py` — `AutoOcrAdapter` with Tesseract→Textract fallback
- `src/config/settings.py` — `ocr_backend`, `textract_*` settings
- `src/infrastructure/http/dependencies.py` — `get_ocr_adapter()` selects adapter by config
- `src/workers/ocr_worker.py` — type hint `IOcrPort`, factory via `_build_ocr_adapter()`
- `docker-compose.yml` — `OCR_BACKEND`, `TEXTRACT_*` env vars in `worker-ocr`

---

### Epic 9: Batch Processing (replaces RabbitMQ workers)

#### US-BAT-001: Nightly batch processor for OCR + CLIP embeddings

**Status:** ✅ COMPLETED

As an operator,
I want a single batch processor that handles OCR and CLIP embedding for all pending images,
So that I eliminate the 3 always-on RabbitMQ workers (~1.8 GB RAM) and replace them with an on-demand task.

**Acceptance Criteria:**
- Single batch script processes all images with `processing_status='pending'` and `s3_key IS NOT NULL`
- For each pending image: download from S3 → OCR → CLIP image embedding → CLIP text embedding → mark completed
- RabbitMQ removed from the ingestion pipeline (use case no longer publishes events)
- `docker-compose up` starts only API + Postgres + MinIO + Redis + Evolution API (no workers, no RabbitMQ)
- Batch processor runs on-demand via `docker-compose run --rm batch-processor`
- AWS Fargate task definition + EventBridge cron rule for nightly execution (2:00 AM Colombia)
- Workers source code preserved in `src/workers/` but not started in docker-compose
- Processing failures are non-fatal per image: failed images marked as `failed`, others continue

**Configuration:**
- No new env vars required — reuses existing `DATABASE_URL`, `S3_*`, `OCR_*`, `CLIP_*`, `TEXTRACT_*`
- Docker Compose profile: `batch` (not started by default)
- AWS: 2 vCPU, 4 GB RAM Fargate task

**Implemented in:**
- `src/batch/__init__.py` — batch module
- `src/batch/process_pending.py` — batch processor script
- `src/infrastructure/persistence/repositories/postgres_metadata_repository.py` — `get_pending()` method
- `src/application/ingestion/use_cases/ingest_images.py` — removed `event_publisher` (RabbitMQ)
- `src/infrastructure/http/dependencies.py` — removed `get_ingestion_event_publisher()`
- `src/config/settings.py` — removed `rabbitmq_url`, `rabbitmq_exchange`
- `docker-compose.yml` — removed workers + rabbitmq, added `batch-processor` with profile
- `aws/task-definition.json` — ECS Fargate task definition
- `aws/eventbridge-rule.json` — EventBridge cron rule
- `aws/README.md` — deployment instructions

---

## Data Structure

### ImageMetadata (Domain Entity)

```
ImageMetadata {
  id_secuencial: int              # Unique incremental numeric ID
  id_mensaje: string              # Message ID or status ID
  tipo_origen: 'chat' | 'estado'  # Source type
  fecha_descarga: datetime        # Download timestamp
  numero_celular: string          # User phone number
  nombre_usuario: string          # User display name
  instancia: string               # Evolution API instance
  ruta_archivo: string            # S3 image path
  hash_imagen: string             # SHA-256 hash for deduplication
  s3_key: string                  # S3 object key
  texto_ocr: string               # OCR-extracted text (nullable)
  image_embedding: vector(512)    # CLIP image embedding (nullable)
  text_embedding: vector(512)     # CLIP text embedding (nullable)
  processing_status: string       # pending | processing | completed | failed
}
```

---

## Architecture Requirements

The service must strictly follow **Hexagonal Architecture**.

### Domain Layer

- Pure domain entities with no external dependencies
- Value Objects for:
  - ImageHash, ImagePath, PhoneNumber, Instance
  - OcrText, ImageEmbedding, TextEmbedding, ProcessingStatus
- Ports (interfaces):
  - ImageSourcePort
  - ImageStoragePort
  - ImageMetadataRepositoryPort
  - IOcrPort
  - IVectorizerPort
❌ The domain must NOT depend on:
- FastAPI, HTTP clients, Filesystem, CSV, S3, PostgreSQL, or external libraries

### Application Layer

- Use cases responsible for:
  - Ingesting images from chats and user status
  - Deduplication logic and sequential ID generation
  - Flow coordination and parameter validation
  - Saving metadata with pending status for batch processing

### Adapters Layer

#### Outbound Adapters
- Evolution API Adapter (HTTP) - image source
- S3 Adapter (boto3) - image storage
- PostgreSQL Adapter (SQLAlchemy async + pgvector) - metadata persistence
- Tesseract Adapter (pytesseract) - OCR processing
- CLIP Adapter (transformers + torch) - vectorization

#### Inbound Adapters
- HTTP API (FastAPI) - ingestion triggers and search endpoints
- Batch Processor (script) - processes pending images on-demand

---

## API Endpoints

### Ingestion
```
POST /api/v1/ingestion/ingest          # Ingest all (chat + status)
POST /api/v1/ingestion/ingest/chat     # Chat images only
POST /api/v1/ingestion/ingest/status   # Status images only
GET  /api/v1/ingestion/status          # System health and stats
GET  /api/v1/ingestion/metadata        # All metadata (paginated)
GET  /api/v1/ingestion/metadata/{id}   # Specific image metadata
```

### Search
```
POST /api/v1/search/by-image           # Find similar images by image upload
POST /api/v1/search/by-text            # Find images by text query
POST /api/v1/search/hybrid             # Combined image + text search
```

---

## Environment Configuration

```
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=SUMlung9541

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/whatsapp_ingestion

S3_BUCKET_NAME=whatsapp-images
S3_PREFIX=images/
S3_REGION=us-east-1
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
STORAGE_BACKEND=s3

OCR_LANGUAGE=spa+eng
OCR_ENABLED=true

CLIP_MODEL_NAME=openai/clip-vit-base-patch32
CLIP_MODEL_CACHE_DIR=/app/models
CLIP_ENABLED=true

```

---

## Infrastructure (Docker Compose)

| Service                  | Image                        | Ports       | Notes                     |
| ------------------------ | ---------------------------- | ----------- | ------------------------- |
| whatsapp-microservice    | Built from Dockerfile        | 3000        |                           |
| evolution-api            | atendai/evolution-api:latest | 8080        |                           |
| postgres                 | pgvector/pgvector:pg15       | 5432        |                           |
| redis                    | redis:7-alpine               | 6379        |                           |
| minio                    | minio/minio:latest           | 9000, 9001  |                           |
| batch-processor          | Built from Dockerfile        | -           | profile=batch, on-demand  |

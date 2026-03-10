# Plan: OCR + CLIP + S3 + PostgreSQL/pgvector + Workers

## Context

Microservicio de ingesta de imágenes WhatsApp. Flujo end-to-end con workers async:

```
Imagen llega → FastAPI → Dedup Check → S3 Upload
                              │
                    INSERT metadata (status='pending')
                              │
                              ▼
                          RabbitMQ
                         /        \
              Worker CLIP      Worker OCR
            (image embed)    (Tesseract)
                  │               │
                  │               ▼
                  │         Worker Text Embedding
                  │               │
                  ▼               ▼
            PostgreSQL + pgvector (MISMA BD, MISMA TABLA)
                              │
                              ▼
                   Search API (by-image, by-text, hybrid)
```

### Decisiones clave
1. **Misma BD** para vectores y metadata - una tabla, consistencia transaccional
2. **Tesseract primero** (gratis), Textract selectivo para baja confianza (futuro)
3. **CLIP ViT-B/32** - 512 dims, texto+imagen mismo espacio vectorial, ~800MB RAM
4. **pgvector/pgvector:pg15** en Docker

---

## Fase 1: Dominio

### 1.1 Value Objects → `src/domain/ingestion/value_objects.py`
- `OcrText(value: str)` - texto extraído, max 50000 chars
- `ImageEmbedding(values: tuple[float, ...])` - vector CLIP 512 dims
- `TextEmbedding(values: tuple[float, ...])` - vector CLIP del texto OCR 512 dims
- `ProcessingStatus` - Enum: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`

### 1.2 Extender `ImageMetadata` → `src/domain/ingestion/entities.py`
Campos nuevos (todos Optional con default None para no romper código existente):
- `texto_ocr: Optional[OcrText] = None`
- `image_embedding: Optional[ImageEmbedding] = None`
- `text_embedding: Optional[TextEmbedding] = None`
- `processing_status: ProcessingStatus = ProcessingStatus.PENDING`
- `s3_key: Optional[str] = None`

### 1.3 Excepciones → `src/domain/ingestion/exceptions.py`
- `OcrError(IngestionError)`
- `VectorizationError(IngestionError)`

---

## Fase 2: Nuevos Ports

### 2.1 `src/application/ingestion/ports/ocr_port.py`
```python
class IOcrPort(ABC):
    async def extract_text(self, image_data: bytes) -> OcrText
```

### 2.2 `src/application/ingestion/ports/vectorizer_port.py`
```python
class IVectorizerPort(ABC):
    async def embed_image(self, image_data: bytes) -> ImageEmbedding
    async def embed_text(self, text: str) -> TextEmbedding
```

### 2.3 `src/application/ingestion/ports/event_publisher_port.py`
```python
class IIngestionEventPort(ABC):
    async def publish_image_ready(self, metadata_id: int, s3_key: str) -> None
```

---

## Fase 3: Adapters de Infraestructura

### 3.1 S3 Storage → `src/infrastructure/storage/s3_image_storage.py`
- Implementa `IImageStoragePort` existente
- boto3, MinIO en dev local
- Extraer `_convert_to_jpeg` a `src/infrastructure/storage/image_converter.py` (compartido)

### 3.2 Tesseract OCR → `src/infrastructure/ocr/tesseract_adapter.py`
- Implementa `IOcrPort`
- pytesseract + PIL, idioma `spa+eng`
- `run_in_executor` para no bloquear async

### 3.3 CLIP Vectorizer → `src/infrastructure/vectorization/clip_adapter.py`
- Implementa `IVectorizerPort`
- `openai/clip-vit-base-patch32` via transformers
- `embed_image()`: imagen → 512 dims L2-normalized
- `embed_text()`: texto OCR → 512 dims L2-normalized (CLIP soporta ambos)
- Singleton, modelo cargado una vez en `__init__`
- `run_in_executor` para inference

### 3.4 PostgreSQL Repository → `src/infrastructure/persistence/repositories/postgres_metadata_repository.py`
- Implementa `IMetadataRepositoryPort`
- SQLAlchemy async + asyncpg + pgvector

### 3.5 SQLAlchemy Model → `src/infrastructure/persistence/models/image_metadata_model.py`
```sql
CREATE TABLE image_metadata (
    id SERIAL PRIMARY KEY,
    id_secuencial INTEGER UNIQUE NOT NULL,
    id_mensaje VARCHAR(500) UNIQUE NOT NULL,
    tipo_origen VARCHAR(20) NOT NULL,
    fecha_descarga TIMESTAMP NOT NULL,
    numero_celular VARCHAR(20) NOT NULL,
    nombre_usuario VARCHAR(256) NOT NULL,
    instancia VARCHAR(100) NOT NULL,
    ruta_archivo VARCHAR(512) NOT NULL,
    hash_imagen VARCHAR(64) UNIQUE NOT NULL,
    s3_key VARCHAR(512),
    texto_ocr TEXT,
    image_embedding vector(512),
    text_embedding vector(512),
    processing_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
-- Indexes en id_secuencial, id_mensaje, hash_imagen, numero_celular, instancia
-- HNSW en image_embedding y text_embedding (vector_cosine_ops)
```

### 3.6 Database Manager → `src/infrastructure/persistence/database.py`
- `create_async_engine` + `async_sessionmaker`, pool_size=5

### 3.7 RabbitMQ Publisher → `src/infrastructure/messaging/rabbitmq/ingestion_publisher.py`
- Implementa `IIngestionEventPort`
- Publica mensaje con `{metadata_id, s3_key}` a queue `image.processing`

---

## Fase 4: Workers (procesamiento async)

### 4.1 Worker CLIP Image → `src/workers/clip_worker.py`
- Consume de RabbitMQ queue `image.processing.clip`
- Descarga imagen de S3
- Genera embedding con CLIP
- UPDATE `image_embedding` en PostgreSQL

### 4.2 Worker OCR → `src/workers/ocr_worker.py`
- Consume de RabbitMQ queue `image.processing.ocr`
- Descarga imagen de S3
- Ejecuta Tesseract OCR
- UPDATE `texto_ocr` en PostgreSQL
- Publica a queue `text.embedding` para el siguiente paso

### 4.3 Worker Text Embedding → `src/workers/text_embedding_worker.py`
- Consume de RabbitMQ queue `text.embedding`
- Lee `texto_ocr` de PostgreSQL
- Genera embedding del texto con CLIP `embed_text()`
- UPDATE `text_embedding` en PostgreSQL
- Cuando ambos embeddings listos → UPDATE `processing_status = 'completed'`

### 4.4 Worker Base → `src/workers/base_worker.py`
- Clase base con conexión RabbitMQ, retry logic, error handling
- aio-pika para async consumption

---

## Fase 5: Modificar Pipeline de Ingesta

### 5.1 Use Case → `src/application/ingestion/use_cases/ingest_images.py`
El flujo cambia a:
1. Descargar imagen de Evolution API (existente)
2. Dedup check por message_id y hash (existente)
3. **Subir a S3** (nuevo, reemplaza filesystem)
4. **INSERT en PostgreSQL** con `processing_status='pending'` (nuevo, reemplaza CSV)
5. **Publicar a RabbitMQ** para workers async (nuevo)
6. Retornar respuesta inmediatamente (no espera OCR/CLIP)

Constructor agrega: `event_publisher: Optional[IIngestionEventPort] = None`

### 5.2 Search API → `src/infrastructure/http/routes/search_routes.py`
Endpoints nuevos:
- `POST /api/v1/search/by-image` - buscar imágenes similares (upload imagen → CLIP → cosine similarity)
- `POST /api/v1/search/by-text` - buscar por texto (texto → CLIP text embed → cosine similarity en text_embedding)
- `POST /api/v1/search/hybrid` - combinación de ambos

---

## Fase 6: Configuración

### 6.1 Settings → `src/config/settings.py`
```python
# Database
database_url: str = "postgresql://postgres:postgres@postgres:5432/whatsapp_ingestion"

# S3
s3_bucket_name: str = "whatsapp-images"
s3_prefix: str = "images/"
s3_region: str = "us-east-1"
s3_endpoint_url: Optional[str] = None
s3_access_key_id: Optional[str] = None
s3_secret_access_key: Optional[str] = None
storage_backend: str = "s3"

# OCR
ocr_language: str = "spa+eng"
ocr_enabled: bool = True

# CLIP
clip_model_name: str = "openai/clip-vit-base-patch32"
clip_model_cache_dir: str = "/app/models"
clip_enabled: bool = True

# RabbitMQ
rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
```

---

## Fase 7: DI + Startup

### 7.1 `src/infrastructure/http/dependencies.py`
- `get_database_manager()` - singleton
- `get_image_storage()` - S3 o filesystem según config
- `get_metadata_repository()` - Postgres o CSV según config
- `get_ocr_adapter()` - singleton si habilitado
- `get_vectorizer_adapter()` - singleton (CLIP carga una vez)
- `get_event_publisher()` - RabbitMQ publisher

### 7.2 Startup en `src/main.py`
- Crear bucket S3 si no existe (MinIO en dev)
- Run Alembic migrations
- Verificar conexión PostgreSQL

---

## Fase 8: Docker

### 8.1 Dockerfile
- 3 stages: builder, model-downloader (pre-descarga CLIP), production
- `apt-get install tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng`
- Copiar modelos CLIP pre-descargados
- Copiar `alembic/` + `alembic.ini`

### 8.2 docker-compose.yml
- `postgres`: cambiar a `pgvector/pgvector:pg15`, agregar BD `whatsapp_ingestion`
- Agregar servicio **MinIO** (ports 9000/9001)
- Workers como servicios separados (mismo Dockerfile, distinto CMD):
  - `worker-clip`: `python -m src.workers.clip_worker`
  - `worker-ocr`: `python -m src.workers.ocr_worker`
  - `worker-text-embedding`: `python -m src.workers.text_embedding_worker`
- Volumes: `minio_data`, `clip_models`

### 8.3 pyproject.toml
Agregar a dependencias principales:
```
pytesseract>=0.3.10
boto3>=1.34.0
torch>=2.1.0
transformers>=4.36.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pgvector>=0.2.4
aio-pika>=9.3.0
```

### 8.4 Alembic
- `alembic/env.py`, `alembic.ini`
- Migration 001: CREATE EXTENSION vector + create table + indexes + HNSW

---

## Orden de Implementación

| # | Tarea | Archivos clave |
|---|-------|---------------|
| 1 | Value objects + entidades + excepciones | `value_objects.py`, `entities.py`, `exceptions.py` |
| 2 | Nuevos ports | `ports/ocr_port.py`, `ports/vectorizer_port.py`, `ports/event_publisher_port.py` |
| 3 | Image converter (shared) | `storage/image_converter.py`, refactor `filesystem_image_storage.py` |
| 4 | S3 adapter | `storage/s3_image_storage.py` |
| 5 | Database manager + SQLAlchemy model | `persistence/database.py`, `persistence/models/` |
| 6 | Alembic setup + migration | `alembic/` |
| 7 | PostgreSQL repository | `persistence/repositories/postgres_metadata_repository.py` |
| 8 | Tesseract adapter | `infrastructure/ocr/tesseract_adapter.py` |
| 9 | CLIP adapter | `infrastructure/vectorization/clip_adapter.py` |
| 10 | RabbitMQ publisher | `messaging/rabbitmq/ingestion_publisher.py` |
| 11 | Worker base + 3 workers | `workers/base_worker.py`, `workers/clip_worker.py`, `workers/ocr_worker.py`, `workers/text_embedding_worker.py` |
| 12 | Modificar use case | `use_cases/ingest_images.py` |
| 13 | DTOs actualizados | `dto.py` |
| 14 | Search API routes | `routes/search_routes.py` |
| 15 | Settings | `config/settings.py` |
| 16 | DI wiring | `dependencies.py` |
| 17 | Docker (Dockerfile + compose + pyproject) | `Dockerfile`, `docker-compose.yml`, `pyproject.toml` |

---

## Verificación

1. `docker-compose up -d` - todos los servicios arrancan
2. MinIO console `localhost:9001` - bucket creado
3. PostgreSQL tiene tabla `image_metadata` con columnas vector
4. `POST /api/v1/ingestion/ingest` → imagen sube a S3, metadata en PG con status `pending`
5. Workers procesan: OCR → texto guardado, CLIP → embeddings guardados, status → `completed`
6. `POST /api/v1/search/by-text` con query → retorna imágenes relevantes
7. `GET /api/v1/ingestion/metadata/{id}` → muestra `texto_ocr`, `has_embedding: true`

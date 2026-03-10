# CLAUDE.md — Image Ingestion Service

## Descripción
Microservicio Python/FastAPI para ingesta de imágenes WhatsApp vía Evolution API.
Almacena en S3, extrae texto (Tesseract OCR), genera embeddings (CLIP ViT-B/32),
registra metadata en PostgreSQL/pgvector. Procesamiento batch (OCR + CLIP) on-demand o vía AWS Fargate + EventBridge.

## Arquitectura Hexagonal

```
src/
├── domain/           → Entidades, Value Objects, Excepciones (sin dependencias externas)
├── application/      → Use Cases, Ports (interfaces ABC), DTOs
├── infrastructure/   → Adapters (implementaciones concretas)
│   ├── http/         → FastAPI routes, middleware, dependencies (DI)
│   ├── integrations/ → Evolution API client/adapters
│   ├── messaging/    → Event publishers (in-memory for messaging use cases)
│   ├── persistence/  → PostgreSQL repos, SQLAlchemy models, CSV repo legacy
│   ├── storage/      → S3 adapter, filesystem adapter
│   ├── ocr/          → Tesseract/Textract adapter
│   └── vectorization/→ CLIP adapter
├── batch/            → Batch processor (replaces RabbitMQ workers)
├── workers/          → Legacy RabbitMQ workers (not used, kept for reference)
└── config/           → Settings (pydantic-settings), logging
```

## Capas y Regla de Dependencia
- **Domain** → sin imports de infrastructure/application
- **Application (Ports/Use Cases)** → importa domain, define interfaces ABC
- **Infrastructure (Adapters)** → implementa ports, importa domain + application

## Patrones Obligatorios
- **Value Objects**: `@dataclass(frozen=True)` con validación en `__post_init__`
- **Ports**: clases ABC en `application/{bounded_context}/ports/`
- **Adapters**: implementan ports, en `infrastructure/`
- **DI**: composición en `infrastructure/http/dependencies.py` con `@lru_cache`
- **Async I/O**: `run_in_executor` para operaciones bloqueantes (OCR, CLIP inference, filesystem)
- **Entidades**: dataclass mutables con métodos de negocio

## Stack Tecnológico
- Python 3.11, FastAPI, uvicorn
- PostgreSQL 15 + pgvector (vectores 512 dims)
- SQLAlchemy async + asyncpg + Alembic
- S3/MinIO (boto3) para imágenes
- Tesseract OCR (pytesseract)
- CLIP ViT-B/32 (transformers + torch)
- Docker multi-stage
- AWS Fargate + EventBridge (batch scheduling)

## Documentos de Referencia
- `PROJECT_SPECS.md` → Requisitos funcionales, parámetros, esquema BD, endpoints
- `PLAN_OCR_CLIP_S3_PGVECTOR.md` → Plan detallado de implementación por fases

## Convenciones de Código
- Frozen dataclass para value objects, validar en `__post_init__`
- `run_in_executor` para código síncrono bloqueante en contextos async
- Excepciones de dominio heredan de base del bounded context (e.g., `IngestionError`)
- Settings via `pydantic_settings.BaseSettings` con prefijo env vars
- Imports absolutos desde `src.` (e.g., `from src.domain.ingestion.entities import ...`)

## Rutas Clave
| Archivo | Propósito |
|---------|-----------|
| `src/main.py` | App factory FastAPI, lifespan, routers |
| `src/config/settings.py` | Configuración centralizada (env vars) |
| `src/infrastructure/http/dependencies.py` | Composition root / DI wiring |
| `src/domain/ingestion/entities.py` | ImageMetadata, RawImageData, IngestionResult |
| `src/domain/ingestion/value_objects.py` | SourceType, ImageHash, MessageId, etc. |
| `src/application/ingestion/use_cases/ingest_images.py` | Orquestador principal de ingesta |
| `src/application/ingestion/ports/` | Interfaces: storage, metadata, image source |
| `src/infrastructure/persistence/models/` | SQLAlchemy models |
| `src/infrastructure/persistence/repositories/` | Repos: Postgres, CSV legacy |
| `src/infrastructure/http/routes/` | FastAPI routers |
| `src/batch/process_pending.py` | Batch processor (OCR + CLIP) |
| `aws/` | Fargate task def + EventBridge rule |

## Comandos Útiles
```bash
docker-compose up -d                           # Levantar API + infra (sin workers)
docker-compose up -d postgres minio            # Solo infra
docker-compose run --rm batch-processor        # Procesar imágenes pendientes
python -m src.batch.process_pending            # Batch processor standalone
```

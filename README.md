# WhatsApp Integration Microservice

A clean architecture microservice for WhatsApp messaging via Evolution API.

## Architecture

This project follows **Hexagonal Architecture** (Ports and Adapters) with strict adherence to:

- **SOLID Principles**
- **Scope Rule**: Code used by one feature stays local; shared code requires actual duplication
- **Screaming Architecture**: Folder structure reveals business capabilities

### Project Structure

```
src/
├── domain/                    # Business entities and rules (NO external dependencies)
│   ├── messaging/             # Message entities, value objects, exceptions
│   ├── instances/             # WhatsApp instance entities
│   └── contacts/              # Contact management
│
├── application/               # Use cases and port definitions
│   ├── messaging/
│   │   ├── use_cases/         # SendTextMessage, SendMediaMessage, etc.
│   │   └── ports/             # IWhatsAppGateway, IMessageRepository
│   └── instances/
│       ├── use_cases/         # CreateInstance, ConnectInstance, etc.
│       └── ports/             # IInstanceGateway, IInstanceRepository
│
├── infrastructure/            # Adapters and external integrations
│   ├── integrations/
│   │   └── evolution_api/     # Evolution API client and adapters
│   ├── persistence/
│   │   └── repositories/      # InMemory, Postgres implementations
│   ├── messaging/
│   │   └── rabbitmq/          # Event publishers
│   └── http/
│       ├── routes/            # FastAPI endpoints
│       ├── webhooks/          # Evolution API webhooks
│       └── middleware/        # Logging, error handling
│
├── shared/                    # Code used by 2+ features (never speculative)
│
└── config/                    # Settings and configuration
```

### Dependency Flow

```
Infrastructure → Application → Domain
     ↓               ↓           ↓
  (Adapters)    (Use Cases)  (Entities)
```

- **Domain Layer**: Pure Python, no external imports
- **Application Layer**: Depends only on Domain
- **Infrastructure Layer**: Implements ports, can import everything

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Evolution API running (or use provided docker-compose)

### Installation

1. Clone and setup:
```bash
cd microservicio
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your Evolution API credentials
```

3. Run locally:
```bash
python -m src.main
```

### Docker

Run with Docker Compose (includes Evolution API, Redis, RabbitMQ):

```bash
docker-compose up -d
```

Development mode with hot reload:
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## API Endpoints

### Health
- `GET /api/v1/health` - Health check
- `GET /api/v1/health/live` - Liveness probe
- `GET /api/v1/health/ready` - Readiness probe

### Instances
- `POST /api/v1/instances` - Create new instance
- `GET /api/v1/instances` - List all instances
- `GET /api/v1/instances/{name}/status` - Get instance status
- `POST /api/v1/instances/{name}/connect` - Get QR code
- `DELETE /api/v1/instances/{name}` - Delete instance

### Messaging
- `POST /api/v1/messages/text` - Send text message
- `POST /api/v1/messages/media` - Send media message
- `GET /api/v1/messages/{id}/status` - Get message status

### Image Ingestion (US-ING-001)
- `POST /api/v1/ingestion/ingest` - Ingest all images (chats + status)
- `POST /api/v1/ingestion/ingest/chat` - Ingest only chat images
- `POST /api/v1/ingestion/ingest/status` - Ingest only status images
- `GET /api/v1/ingestion/status` - Get ingestion system status
- `GET /api/v1/ingestion/metadata` - List all ingested images metadata
- `GET /api/v1/ingestion/metadata/{id}` - Get specific image metadata

### Webhooks
- `POST /api/v1/webhooks/evolution` - Evolution API webhook

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run only unit tests
pytest tests/unit

# Run integration tests
pytest tests/integration

# Run e2e tests (requires Evolution API)
pytest tests/e2e -m e2e
```

## Development

### Code Quality

```bash
# Lint
ruff check src tests

# Format
ruff format src tests

# Type check
mypy src
```

### Adding New Features

1. **Domain First**: Define entities and value objects in `domain/`
2. **Define Ports**: Create interfaces in `application/[capability]/ports/`
3. **Implement Use Cases**: Business logic in `application/[capability]/use_cases/`
4. **Create Adapters**: Infrastructure in `infrastructure/`
5. **Wire Dependencies**: Update `infrastructure/http/dependencies.py`
6. **Add Routes**: HTTP endpoints in `infrastructure/http/routes/`

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `EVOLUTION_API_URL` | Evolution API base URL | `http://localhost:8080` |
| `EVOLUTION_API_KEY` | API authentication key | Required |
| `PORT` | Server port | `3000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Environment mode | `development` |
| `INGESTION_DATA_DIRECTORY` | Base directory for ingested data | `/data` |
| `INGESTION_IMAGES_SUBDIRECTORY` | Images subdirectory | `images` |
| `INGESTION_METADATA_SUBDIRECTORY` | Metadata subdirectory | `metadata` |
| `INGESTION_METADATA_FILENAME` | CSV metadata filename | `images.csv` |

## Testing the Image Ingestion Service

### Quick Start Testing

**⚠️ IMPORTANTE: El servicio ahora requiere `numero_celular` e `instancia` (parámetros obligatorios)**

```bash
# Windows - Run automated test suite
.\test-ingestion.ps1 -NumCelular "51999999999" -Instancia "mi-instancia"

# Linux/Mac - Run automated test suite
chmod +x test-ingestion.sh
./test-ingestion.sh 51999999999 mi-instancia

# Manual testing with cURL - see curl-examples.md for all examples
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"numero_celular\": \"51999999999\", \"instancia\": \"mi-instancia\"}"
```

### Testing Documentation

- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Complete step-by-step testing guide
- **[curl-examples.md](curl-examples.md)** - Ready-to-use cURL command examples
- **test-ingestion.ps1** - Automated test suite for Windows
- **test-ingestion.sh** - Automated test suite for Linux/Mac

## License

MIT

# Image Ingestion Service - Project Specifications

## Project Description

Image Ingestion Service is a Python-based microservice responsible for downloading images from **Evolution API** (chat messages and user status), storing them locally using sequential filenames, and registering metadata in a CSV file.

The service guarantees **idempotent ingestion**, meaning it can be executed multiple times without downloading the same image twice.  
The generated dataset is prepared for future use in **training, RAG, and vectorization pipelines**.

The service operates **per user and per instance**, ensuring controlled and deterministic ingestion.

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

As a data ingestion system,  
I want to download images from chats and user status published via Evolution API,  
Filtered by **phone number** and **instance**,  
So that I can build a clean, structured dataset for AI processing without duplication.

---

## Acceptance Criteria

### Input Validation

- The service must require:
  - `numero_celular`
  - `instancia`
- If any parameter is missing or empty:
  - The service returns an error
  - No ingestion process is executed

---

### Image Sources

- The system must retrieve images from:
  - Chat messages for the given `numero_celular`
  - User status (stories) for the given `numero_celular`
- The Evolution API calls must be scoped to the provided `instancia`
- Only image messages are processed
- Videos, audios, stickers, documents, and other media types are ignored

---

### Storage

- All images are stored in a single local directory:/data/images/

- Images are saved using **sequential numeric filenames**:

  1.jpg
  2.jpg
  3.jpg

- The sequential ID:
  - Is unique
  - Does not reset between executions
  - Is global across all users and instances

---

### Idempotency & Deduplication

- The service must be **idempotent**
- If the service is executed today and images are downloaded,
- And executed again later with the same parameters:
  - Previously downloaded images must **NOT** be downloaded again

Before downloading any image, the system must verify:

- If the `id_mensaje` already exists in the metadata CSV, OR
- If the `hash_imagen` already exists in the metadata CSV

If the image already exists:

- The image is NOT downloaded again
- The sequential ID is NOT incremented
- No duplicate metadata entry is created

---

### Image Normalization

- All images are:
  - Converted
  - Normalized
  - Stored in **JPEG format**

---

### Metadata Registration

- Metadata is persisted in a CSV file located at:/data/metadata/images.csv

- For each downloaded image, a metadata record is created with the following fields:

| Field          | Description                   |
| -------------- | ----------------------------- |
| id_secuencial  | Unique incremental numeric ID |
| id_mensaje     | Message ID or status ID       |
| tipo_origen    | `chat` or `estado`            |
| fecha_descarga | Download timestamp            |
| numero_celular | User phone number             |
| nombre_usuario | User display name             |
| instancia      | Evolution API instance        |
| ruta_archivo   | Local image path              |
| hash_imagen    | Hash used for deduplication   |

- The CSV file acts as the **single source of truth** for ingestion state

---

### Re-execution Safety

- The service can be safely executed multiple times
- On each execution:
  - Only new images are downloaded
  - Existing images are not modified
  - Existing metadata is preserved
  - The sequential numbering continues correctly

---

## Architecture Requirements

The service must strictly follow **Hexagonal Architecture**.

---

### Domain Layer

- Pure domain entities with no external dependencies
- Value Objects for:
  - ImageHash
  - ImagePath
  - PhoneNumber
  - Instance
- Ports (interfaces):
  - ImageSourcePort
  - ImageStoragePort
  - ImageMetadataRepositoryPort

❌ The domain must NOT depend on:

- FastAPI
- HTTP clients
- Filesystem
- CSV or pandas
- External libraries

---

### Application Layer

- Use cases responsible for:
  - Ingesting images from chats
  - Ingesting images from user status
- Deduplication logic
- Sequential ID generation
- Flow coordination
- Validation of required parameters

---

### Adapters Layer

#### Outbound Adapters

- Evolution API Adapter (HTTP)
- FileSystem Adapter (image storage)
- CSV Adapter (metadata persistence)

#### Inbound Adapters

- HTTP API (FastAPI) to trigger ingestion processes

Example endpoint:POST /ingest/images

Request body:

```json
{
  "numero_celular": "51999999999",
  "instancia": "instance_01"
}

Data Structure

ImageMetadata (Domain Entity)

ImageMetadata {
  id_secuencial: int
  id_mensaje: string
  tipo_origen: 'chat' | 'estado'
  fecha_descarga: datetime
  numero_celular: string
  nombre_usuario: string
  instancia: string
  ruta_archivo: string
  hash_imagen: string
}
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=SUMlung9541




```

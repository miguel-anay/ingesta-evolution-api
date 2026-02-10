# Ejemplos cURL - Servicio de Ingestión de Imágenes

Colección de comandos cURL listos para usar con el servicio de ingestión.

## Variables de Entorno (Opcional)

```bash
# Configurar para facilitar los ejemplos
export BASE_URL="http://localhost:3000"
export INSTANCE_NAME="mi-instancia"
```

---

## Health & Status

### Health Check

```bash
curl http://localhost:3000/api/v1/health
```

**Respuesta:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T12:00:00Z"
}
```

---

### Estado de Ingestión

```bash
curl http://localhost:3000/api/v1/ingestion/status
```

**Respuesta:**
```json
{
  "status": "ready",
  "total_images_ingested": 42,
  "last_ingestion": "2026-01-13T12:30:00Z",
  "images_directory": "c:/evolution api/microservicio/data/images",
  "metadata_file": "c:/evolution api/microservicio/data/metadata/images.csv"
}
```

---

## Ingestión de Imágenes

### Ingestión Completa (Chats + Estados)

**⚠️ CAMBIO IMPORTANTE: Ahora requiere `numero_celular` e `instancia` (obligatorios)**

```bash
# Ingerir imágenes de un usuario específico
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Con límite:**
```bash
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\",
    \"limit\": 50
  }"
```

**Respuesta:**
```json
{
  "success": true,
  "images_ingested": 15,
  "images_skipped": 5,
  "total_processed": 20,
  "execution_time_seconds": 3.45,
  "details": {
    "from_chats": 10,
    "from_status": 5
  }
}
```

**Nota:** El servicio filtra y descarga SOLO las imágenes del `numero_celular` especificado.

---

### Ingestión Solo de Chats

**⚠️ CAMBIO: Ahora requiere `numero_celular` e `instancia`**

```bash
# Ingerir imágenes de chat de un usuario específico
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Con límite:**
```bash
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\",
    \"limit\": 50
  }"
```

**Parámetros obligatorios:**
- `numero_celular`: Número de teléfono (sin espacios, guiones ni prefijo +)
- `instancia`: Identificador de instancia de WhatsApp

**Nota:** El servicio descarga SOLO las imágenes del `numero_celular` especificado.

---

### Ingestión Solo de Estados (Stories)

**⚠️ CAMBIO: Ahora requiere `numero_celular` e `instancia`**

```bash
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/status \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Con límite:**
```bash
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/status \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\",
    \"limit\": 10
  }"
```

---

## Consulta de Metadata

### Listar Toda la Metadata

```bash
curl http://localhost:3000/api/v1/ingestion/metadata
```

**Con paginación:**
```bash
curl "http://localhost:3000/api/v1/ingestion/metadata?limit=10&offset=0"
```

**Respuesta:**
```json
{
  "total": 42,
  "metadata": [
    {
      "id_secuencial": 1,
      "id_mensaje": "3EB0ABC123456789",
      "tipo_origen": "chat",
      "fecha_descarga": "2026-01-13T10:30:00Z",
      "numero_telefono": "5511999999999",
      "nombre_usuario": "Juan Pérez",
      "ruta_archivo": "c:/evolution api/microservicio/data/images/1.jpg",
      "hash_imagen": "a1b2c3d4e5f6..."
    },
    {
      "id_secuencial": 2,
      "id_mensaje": "3EB0DEF987654321",
      "tipo_origen": "estado",
      "fecha_descarga": "2026-01-13T10:31:00Z",
      "numero_telefono": "5511888888888",
      "nombre_usuario": "María García",
      "ruta_archivo": "c:/evolution api/microservicio/data/images/2.jpg",
      "hash_imagen": "f6e5d4c3b2a1..."
    }
  ]
}
```

---

### Obtener Metadata por ID

```bash
curl http://localhost:3000/api/v1/ingestion/metadata/1
```

**Respuesta:**
```json
{
  "id_secuencial": 1,
  "id_mensaje": "3EB0ABC123456789",
  "tipo_origen": "chat",
  "fecha_descarga": "2026-01-13T10:30:00Z",
  "numero_telefono": "5511999999999",
  "nombre_usuario": "Juan Pérez",
  "ruta_archivo": "c:/evolution api/microservicio/data/images/1.jpg",
  "hash_imagen": "a1b2c3d4e5f6..."
}
```

---

## Gestión de Instancias (Endpoints Existentes)

### Listar Instancias

```bash
curl http://localhost:3000/api/v1/instances
```

---

### Crear Nueva Instancia

```bash
curl -X POST http://localhost:3000/api/v1/instances \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"test-instance\",
    \"token\": \"test-token-123\"
  }"
```

---

### Conectar Instancia (Obtener QR)

```bash
curl -X POST http://localhost:3000/api/v1/instances/test-instance/connect
```

---

### Estado de Instancia

```bash
curl http://localhost:3000/api/v1/instances/test-instance/status
```

---

### Eliminar Instancia

```bash
curl -X DELETE http://localhost:3000/api/v1/instances/test-instance
```

---

## Mensajería (Endpoints Existentes)

### Enviar Mensaje de Texto

```bash
curl -X POST http://localhost:3000/api/v1/messages/text \
  -H "Content-Type: application/json" \
  -d "{
    \"instance_name\": \"mi-instancia\",
    \"number\": \"5511999999999\",
    \"text\": \"Hola desde el microservicio!\"
  }"
```

---

### Enviar Imagen

```bash
curl -X POST http://localhost:3000/api/v1/messages/media \
  -H "Content-Type: application/json" \
  -d "{
    \"instance_name\": \"mi-instancia\",
    \"number\": \"5511999999999\",
    \"media_url\": \"https://example.com/image.jpg\",
    \"caption\": \"Mira esta imagen!\"
  }"
```

---

## Escenarios de Prueba

### Escenario 1: Primera Ingestión Completa

```bash
# 1. Verificar estado inicial
curl http://localhost:3000/api/v1/ingestion/status

# 2. Ejecutar ingestión
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"

# 3. Verificar metadata
curl http://localhost:3000/api/v1/ingestion/metadata

# 4. Verificar estado final
curl http://localhost:3000/api/v1/ingestion/status
```

---

### Escenario 2: Prueba de Idempotencia

```bash
# Ejecutar dos veces seguidas
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"

# La segunda vez debería retornar images_ingested: 0 y images_skipped > 0
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
```

---

### Escenario 3: Ingestión Incremental

```bash
# 1. Primera ingestión
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"

# 2. Enviar nuevas imágenes por WhatsApp
curl -X POST http://localhost:3000/api/v1/messages/media \
  -H "Content-Type: application/json" \
  -d "{
    \"instance_name\": \"mi-instancia\",
    \"number\": \"TU_NUMERO\",
    \"media_url\": \"https://picsum.photos/800/600\",
    \"caption\": \"Test image\"
  }"

# 3. Segunda ingestión (debería encontrar solo las nuevas)
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
```

---

## Formatos de Respuesta

### Respuesta Exitosa

```json
{
  "success": true,
  "images_ingested": 10,
  "images_skipped": 5,
  "total_processed": 15,
  "execution_time_seconds": 2.34
}
```

---

### Respuesta con Error

```json
{
  "detail": "Instance 'invalid-instance' not found or not connected"
}
```

---

## Tips y Trucos

### Pretty Print con jq

```bash
curl http://localhost:3000/api/v1/ingestion/metadata | jq '.'
```

---

### Guardar Respuesta en Archivo

```bash
curl http://localhost:3000/api/v1/ingestion/metadata > metadata.json
```

---

### Ver Headers de Respuesta

```bash
curl -i http://localhost:3000/api/v1/ingestion/status
```

---

### Silenciar Progress Bar

```bash
curl -s http://localhost:3000/api/v1/health
```

---

### Timeout Personalizado

```bash
curl --max-time 60 -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
```

---

### Verbose Mode (Debug)

```bash
curl -v http://localhost:3000/api/v1/ingestion/status
```

---

## Verificación de Archivos Locales

### Listar Imágenes Descargadas

```bash
# Windows
dir data\images

# Linux/Mac
ls -lh data/images/
```

---

### Ver Contenido del CSV

```bash
# Windows
type data\metadata\images.csv

# Linux/Mac
cat data/metadata/images.csv

# Con formato de tabla (Linux/Mac)
column -t -s, data/metadata/images.csv
```

---

### Contar Imágenes Descargadas

```bash
# Windows PowerShell
(Get-ChildItem data\images -Filter *.jpg).Count

# Linux/Mac
ls -1 data/images/*.jpg | wc -l
```

---

## Variables de Entorno para Scripts

### Bash Script

```bash
#!/bin/bash
BASE_URL="http://localhost:3000"
INSTANCE="mi-instancia"

# Health check
curl "$BASE_URL/api/v1/health"

# Ingerir imágenes
curl -X POST "$BASE_URL/api/v1/ingestion/ingest" \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"$INSTANCE\"}"
```

---

### PowerShell Script

```powershell
$BaseUrl = "http://localhost:3000"
$Instance = "mi-instancia"

# Health check
Invoke-RestMethod -Uri "$BaseUrl/api/v1/health"

# Ingerir imágenes
Invoke-RestMethod -Uri "$BaseUrl/api/v1/ingestion/ingest" `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{instance_name = $Instance} | ConvertTo-Json)
```

---

## Evolution API Direct (Para Debugging)

### Listar Instancias en Evolution API

```bash
curl http://localhost:8080/instance/fetchInstances \
  -H "apikey: SUMlung9541"
```

---

### Verificar Conexión de Instancia

```bash
curl http://localhost:8080/instance/connectionState/mi-instancia \
  -H "apikey: SUMlung9541"
```

---

## Documentación Interactiva

El servicio también expone documentación interactiva Swagger:

- **Swagger UI**: http://localhost:3000/docs
- **ReDoc**: http://localhost:3000/redoc
- **OpenAPI JSON**: http://localhost:3000/openapi.json


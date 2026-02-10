# Guía de Pruebas - Servicio de Ingestión de Imágenes

Esta guía te muestra cómo probar el servicio de ingestión de imágenes (US-ING-001) paso a paso.

## 📋 Prerrequisitos

1. **Evolution API corriendo** (puerto 8080)
2. **Python 3.11+** instalado
3. **Al menos una instancia de WhatsApp conectada** en Evolution API

---

## 🚀 Paso 1: Configurar el Entorno

### 1.1 Activar el entorno virtual

```bash
# En el directorio del microservicio
cd c:\evolution api\microservicio

# Activar virtual environment (Windows)
.venv\Scripts\activate

# Si no existe el venv, créalo primero
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### 1.2 Verificar/Configurar .env

Asegúrate de que tu archivo `.env` tenga estas configuraciones:

```env
# Evolution API
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=SUMlung9541

# Ingestion settings
INGESTION_DATA_DIRECTORY=c:/evolution api/microservicio/data
INGESTION_IMAGES_SUBDIRECTORY=images
INGESTION_METADATA_SUBDIRECTORY=metadata
INGESTION_METADATA_FILENAME=images.csv
```

### 1.3 Crear directorios necesarios

```bash
# Crear directorios para almacenar imágenes y metadata
mkdir data
mkdir data\images
mkdir data\metadata
```

---

## 🏃 Paso 2: Iniciar el Servicio

```bash
# Iniciar el microservicio
python -m src.main
```

Deberías ver:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:3000
```

---

## 🧪 Paso 3: Probar los Endpoints

### 3.1 Verificar que el servicio está funcionando

```bash
# Health check
curl http://localhost:3000/api/v1/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T12:00:00Z"
}
```

### 3.2 Verificar estado de ingestión

```bash
curl http://localhost:3000/api/v1/ingestion/status
```

**Respuesta esperada:**
```json
{
  "status": "ready",
  "total_images_ingested": 0,
  "last_ingestion": null,
  "images_directory": "c:/evolution api/microservicio/data/images",
  "metadata_file": "c:/evolution api/microservicio/data/metadata/images.csv"
}
```

---

## 📥 Paso 4: Probar la Ingestión

### Prerrequisito: Tener una instancia conectada

Primero, verifica que tienes instancias en Evolution API:

```bash
# Listar instancias de WhatsApp
curl http://localhost:8080/instance/fetchInstances \
  -H "apikey: SUMlung9541"
```

**Anota el nombre de tu instancia** (ej: `mi-instancia`)

---

### 4.1 Ingestión Completa (Chat + Estados)

**⚠️ IMPORTANTE: Ahora se requieren 2 parámetros obligatorios:**
- `numero_celular`: Número de teléfono del usuario (ej: `51999999999`)
- `instancia`: Identificador de instancia (ej: `mi-instancia`)

```bash
# Ingerir imágenes de un usuario específico en una instancia
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Respuesta esperada:**
```json
{
  "success": true,
  "images_ingested": 5,
  "images_skipped": 0,
  "total_processed": 5,
  "execution_time_seconds": 2.34,
  "details": {
    "from_chats": 3,
    "from_status": 2
  }
}
```

**Nota:** El servicio ahora filtra y descarga SOLO las imágenes del `numero_celular` especificado.

---

### 4.2 Ingestión Solo de Chats

```bash
# Ingerir imágenes de chat de un usuario específico
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\",
    \"limit\": 50
  }"
```

**Parámetros obligatorios:**
- `numero_celular`: Número de teléfono del usuario (sin espacios ni guiones)
- `instancia`: Identificador de la instancia de WhatsApp

**Parámetros opcionales:**
- `limit`: Número máximo de imágenes a procesar

---

### 4.3 Ingestión Solo de Estados (Stories)

```bash
# Ingerir solo imágenes de estados de un usuario específico
curl -X POST http://localhost:3000/api/v1/ingestion/ingest/status \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Parámetros obligatorios:**
- `numero_celular`: Número de teléfono del usuario
- `instancia`: Identificador de la instancia

---

### 4.4 Prueba de Idempotencia (Re-ejecución)

```bash
# Ejecutar nuevamente la ingestión - NO debería descargar duplicados
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{
    \"numero_celular\": \"51999999999\",
    \"instancia\": \"mi-instancia\"
  }"
```

**Respuesta esperada:**
```json
{
  "success": true,
  "images_ingested": 0,
  "images_skipped": 5,
  "total_processed": 5,
  "execution_time_seconds": 0.12,
  "message": "All images already ingested (idempotent execution)"
}
```

---

## 🔍 Paso 5: Verificar Resultados

### 5.1 Ver metadata de imágenes ingresadas

```bash
# Listar toda la metadata
curl http://localhost:3000/api/v1/ingestion/metadata
```

**Respuesta esperada:**
```json
{
  "total": 5,
  "metadata": [
    {
      "id_secuencial": 1,
      "id_mensaje": "3EB0ABC123456789",
      "tipo_origen": "chat",
      "fecha_descarga": "2026-01-13T12:30:45Z",
      "numero_telefono": "5511999999999",
      "nombre_usuario": "Juan Pérez",
      "ruta_archivo": "c:/evolution api/microservicio/data/images/1.jpg",
      "hash_imagen": "a1b2c3d4e5f6..."
    },
    ...
  ]
}
```

### 5.2 Ver metadata de una imagen específica

```bash
# Obtener metadata por ID secuencial
curl http://localhost:3000/api/v1/ingestion/metadata/1
```

---

### 5.3 Verificar archivos físicos

```bash
# Listar imágenes descargadas
dir data\images

# Deberías ver:
# 1.jpg
# 2.jpg
# 3.jpg
# ...

# Ver el CSV de metadata
type data\metadata\images.csv
```

**Contenido esperado del CSV:**
```csv
id_secuencial,id_mensaje,tipo_origen,fecha_descarga,numero_telefono,nombre_usuario,ruta_archivo,hash_imagen
1,3EB0ABC123456789,chat,2026-01-13T12:30:45Z,5511999999999,Juan Pérez,c:/evolution api/microservicio/data/images/1.jpg,a1b2c3d4e5f6...
2,3EB0DEF987654321,estado,2026-01-13T12:30:46Z,5511888888888,María García,c:/evolution api/microservicio/data/images/2.jpg,f6e5d4c3b2a1...
```

---

## 🐍 Paso 6: Ejecutar Tests Automatizados

### 6.1 Ejecutar todos los tests

```bash
# Ejecutar suite completa de tests
pytest

# Ver con cobertura
pytest --cov=src --cov-report=html
```

### 6.2 Ejecutar tests específicos de ingestión

```bash
# Tests unitarios del dominio
pytest tests/unit/domain/test_ingestion_value_objects.py -v
pytest tests/unit/domain/test_ingestion_entities.py -v

# Tests de casos de uso
pytest tests/unit/application/test_ingest_images_use_case.py -v

# Tests de integración
pytest tests/integration/test_ingestion_adapters.py -v
```

**Resultado esperado:**
```
===================== 91 passed in 5.23s =====================
```

---

## 🎯 Escenarios de Prueba Específicos

### Escenario 1: Primera Ingestión

```bash
# 1. Verificar estado inicial
curl http://localhost:3000/api/v1/ingestion/status

# 2. Ejecutar ingestión
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"

# 3. Verificar que se crearon archivos
dir data\images
type data\metadata\images.csv

# 4. Verificar metadata vía API
curl http://localhost:3000/api/v1/ingestion/metadata
```

---

### Escenario 2: Prueba de Idempotencia

```bash
# 1. Primera ejecución
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
# Resultado: images_ingested: 5, images_skipped: 0

# 2. Segunda ejecución (sin nuevas imágenes en WhatsApp)
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
# Resultado esperado: images_ingested: 0, images_skipped: 5

# 3. Verificar que no hay duplicados en el CSV
type data\metadata\images.csv
# Debería tener solo 5 líneas (+ header), no 10
```

---

### Escenario 3: Nuevas Imágenes

```bash
# 1. Primera ingestión
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
# Resultado: 5 imágenes ingresadas

# 2. Enviar nuevas imágenes por WhatsApp (enviar 2 imágenes nuevas)

# 3. Segunda ingestión
curl -X POST http://localhost:3000/api/v1/ingestion/ingest \
  -H "Content-Type: application/json" \
  -d "{\"instance_name\": \"mi-instancia\"}"
# Resultado esperado: images_ingested: 2, images_skipped: 5

# 4. Verificar que los IDs continúan secuencialmente
dir data\images
# Deberías ver: 1.jpg, 2.jpg, 3.jpg, 4.jpg, 5.jpg, 6.jpg, 7.jpg
```

---

## 🔧 Troubleshooting

### Error: "Evolution API not reachable"

```bash
# Verificar que Evolution API está corriendo
curl http://localhost:8080/instance/fetchInstances -H "apikey: SUMlung9541"

# Si no responde, iniciar Evolution API
cd "c:\evolution api"
docker-compose up -d
```

---

### Error: "Instance not found"

```bash
# Listar instancias disponibles
curl http://localhost:8080/instance/fetchInstances -H "apikey: SUMlung9541"

# Crear una nueva instancia si es necesario
curl -X POST http://localhost:3000/api/v1/instances \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"test-instance\", \"token\": \"test-token\"}"

# Conectar la instancia (escanear QR)
curl http://localhost:3000/api/v1/instances/test-instance/connect
```

---

### Error: "Permission denied" al escribir archivos

```bash
# En Windows, verificar permisos del directorio data
# Asegúrate de que el directorio existe
mkdir data\images
mkdir data\metadata

# Verificar que puedes escribir
echo test > data\test.txt
del data\test.txt
```

---

### No se encuentran imágenes

```bash
# Verificar que la instancia tiene mensajes con imágenes
# Puedes probar enviándote imágenes a ti mismo por WhatsApp

# O usar la instancia para enviar una imagen de prueba:
curl -X POST http://localhost:3000/api/v1/messages/media \
  -H "Content-Type: application/json" \
  -d "{
    \"instance_name\": \"mi-instancia\",
    \"number\": \"TU_NUMERO@s.whatsapp.net\",
    \"media_url\": \"https://example.com/test-image.jpg\",
    \"caption\": \"Test image\"
  }"
```

---

## 📊 Verificación de Calidad

### ✅ Checklist de Pruebas Exitosas

- [ ] El servicio inicia sin errores
- [ ] Health check responde correctamente
- [ ] Status endpoint muestra información correcta
- [ ] Primera ingestión descarga imágenes exitosamente
- [ ] Archivos `.jpg` se crean en `/data/images/` con nombres secuenciales
- [ ] Archivo CSV se crea en `/data/metadata/images.csv`
- [ ] Metadata CSV contiene todos los campos requeridos
- [ ] Segunda ejecución NO descarga duplicados (idempotencia)
- [ ] IDs secuenciales NO se resetean entre ejecuciones
- [ ] Nuevas imágenes se procesan correctamente
- [ ] Todos los tests unitarios pasan (pytest)
- [ ] API responde correctamente a todos los endpoints

---

## 🎓 Próximos Pasos

Una vez que todas las pruebas sean exitosas:

1. **Integrar con orquestador C#** para triggers automáticos
2. **Configurar webhooks** para ingestión en tiempo real
3. **Implementar pipeline RAG** para procesar las imágenes
4. **Agregar vectorización** con embeddings
5. **Conectar con bases de datos vectoriales** (Qdrant, FAISS)

---

## 📚 Recursos Adicionales

- [PROJECT_SPECS.md](PROJECT_SPECS.md) - Especificaciones completas del proyecto
- [README.md](README.md) - Documentación general del microservicio
- [Evolution API Docs](https://doc.evolution-api.com/) - Documentación de Evolution API


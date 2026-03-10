# Decisiones de Arquitectura — Image Ingestion Service

## 1. PyTorch CPU-only vs CUDA

### Decisión: Usar PyTorch CPU-only en Docker

| Aspecto | CUDA (GPU) | CPU-only |
|---|---|---|
| **Tamaño imagen** | ~8 GB | ~1.5 GB |
| **Tiempo de build** | ~40 min | ~10 min |
| **Rendimiento** | Igual (sin GPU disponible) | Igual |
| **Fargate tiene GPU?** | No | No |
| **Docker Desktop tiene GPU?** | No | No |

**Conclusión:** PyTorch CUDA sin GPU = corre en CPU igualmente. Son 8GB de librerías NVIDIA que nunca se usan. Se eliminó `torch` del `pyproject.toml` y se instala CPU-only en el Dockerfile con `--index-url https://download.pytorch.org/whl/cpu`.

### Tiempos de inferencia en CPU

| Operación | Tiempo por imagen | Bloqueante? |
|---|---|---|
| CLIP image embedding | ~0.5-2 seg | No (batch offline) |
| CLIP text embedding | ~0.1-0.3 seg | No (batch offline) |
| OCR Tesseract | ~1-3 seg | No (batch offline) |

Para 1000 imágenes en batch: ~30-50 minutos en CPU. Aceptable para procesamiento nocturno.

---

## 2. Batch Processor vs API (siempre activo)

### Son dos servicios independientes

```
BATCH (cron 2 AM o manual):
  Imagen nueva → OCR → CLIP embedding → guarda vector en BD
  ⏰ Se ejecuta, termina y muere

API (siempre corriendo 24/7):
  Usuario sube imagen → CLIP la vectoriza en el momento → pgvector busca similares → responde
  🟢 Siempre activo
```

### En Fargate

| Componente | Tipo en Fargate | Estado |
|---|---|---|
| **whatsapp-microservice** (API) | **Service** (always-on) | Siempre corriendo |
| **batch-processor** | **Task** (on-demand) | Solo cuando hay imágenes nuevas |

El endpoint `POST /api/v1/search/by-image` vive en la API. No necesita el batch para buscar. El batch solo procesa imágenes nuevas para tenerlas listas en la BD.

---

## 3. CLIP vive dentro de whatsapp-microservice

```
whatsapp-microservice (1 contenedor)
├── FastAPI (API endpoints)
├── CLIP model (cargado en memoria RAM ~400MB)
├── Tesseract OCR
└── Conexiones a: PostgreSQL, S3, Evolution API
```

Para el volumen actual esto es suficiente. Fargate con 2 vCPU + 4GB RAM lo maneja bien.

---

## 4. AWS Rekognition vs CLIP — ¿Por qué NO Rekognition?

### Rekognition NO sirve para búsqueda de imágenes generales

```
Rekognition similarity search → SOLO funciona con CARAS humanas
                                 (IndexFaces / SearchFacesByImage)

Nuestro caso → productos, documentos, fotos generales de WhatsApp
             → Rekognition no tiene "SearchImagesByImage" general
```

### Comparación

| Criterio | Rekognition | CLIP + pgvector |
|---|---|---|
| **Busca imágenes similares generales?** | **NO** (solo caras) | **SÍ** |
| **Costo mensual** | ~$120+/mes | ~$0.50/mes |
| **Necesita entrenamiento?** | Sí (Custom Labels) | No (zero-shot) |
| **Latencia por búsqueda** | 100-300ms (API call) | 20-50ms (query PG local) |
| **Vendor lock-in** | Alto (embeddings no exportables) | Ninguno |
| **Búsqueda texto + imagen** | No | Sí (mismo embedding space) |

---

## 5. Modelos de Embeddings disponibles en AWS Bedrock

| Modelo | En Bedrock? | Dims | Imágenes? | Costo por imagen |
|---|---|---|---|---|
| **CLIP ViT-B/32** (actual) | No (self-hosted) | 512 | Sí | ~$0.00 |
| **Amazon Titan Multimodal Embeddings** | **Sí** | 1024 | Sí | ~$0.0006 |
| **Cohere Embed v3** | Sí | 1024 | No (solo texto) | - |
| **DINOv2** (Meta) | No (self-hosted) | 384-1024 | Sí | ~$0.00 |

### Titan Multimodal vs CLIP

| Aspecto | CLIP (self-hosted) | Titan Multimodal (Bedrock) |
|---|---|---|
| Calidad | Buena | Similar/Ligeramente mejor |
| Infra | Modelo en contenedor (~400MB RAM) | API call, sin infra |
| Costo 10K imágenes | ~$0.05 (Fargate) | ~$6.00 |
| Costo por búsqueda | $0 (local) | ~$0.0006 |
| Ventaja | Sin costo, sin dependencia | Sin modelo local, más simple |

---

## 6. DINOv2 vs CLIP — Búsqueda de imagen por imagen

### DINOv2 es significativamente mejor para image→image

| Benchmark | DINOv2 | CLIP | Diferencia |
|---|---|---|---|
| Image similarity (DISC21, 150K imgs) | **64%** | 28% | **+125%** |
| Fine-grained classification (10K clases) | **70%** | 15% | **+4.5x** |
| Scene classification (365 categorías) | **53%** | 51% | ~igual |

### Pero DINOv2 NO soporta búsqueda por texto

```
CLIP:    imagen → búsqueda ✅    texto → búsqueda ✅
DINOv2:  imagen → búsqueda ✅    texto → búsqueda ❌  (vision-only)
```

### Variantes de DINOv2

| Variante | Params | RAM | Velocidad (CPU) | Dims |
|---|---|---|---|---|
| **ViT-S/14** (recomendado) | 21M | ~200 MB | ~50ms/img | 384 |
| ViT-B/14 | 86M | ~400 MB | ~150ms/img | 768 |
| ViT-L/14 | 300M | ~1.4 GB | ~500ms/img | 1024 |
| ViT-g/14 | 1.1B | ~4.4 GB | ~2000ms/img | 1536 |

### Estrategia recomendada: Dual-Embedding

```
Imagen nueva entra al batch:
├── CLIP   → vector 512 dims → clip_embedding  (para búsqueda por texto)
└── DINOv2 → vector 384 dims → dino_embedding  (para búsqueda por imagen, 2x más preciso)

Búsqueda por TEXTO:   usa CLIP
Búsqueda por IMAGEN:  usa DINOv2
Búsqueda HÍBRIDA:     combina ambos scores (0.6 dino + 0.4 clip)
```

Costo adicional en batch: ~50ms extra por imagen. Prácticamente nada.

### Deploy en AWS

Igual que CLIP — baked en el contenedor Fargate. DINOv2 ViT-S/14 agrega solo ~200MB al contenedor.

---

## 7. CI/CD — GitHub Actions vs AWS CodeBuild

### GitHub Actions Free Tier

| Recurso | Repos públicos | Repos privados |
|---|---|---|
| Minutos/mes | Ilimitados | 2,000 min/mes |
| RAM runner | 7 GB | 7 GB |
| Disco runner | 14 GB | 14 GB |

Con PyTorch CPU-only, el build toma ~10 min. Con 2,000 min/mes gratis se pueden hacer ~200 builds/mes. Suficiente.

### Comparación

| Servicio | Build time | Costo |
|---|---|---|
| **GitHub Actions** (privado) | ~10 min (CPU-only) | **Gratis** (2000 min/mes) |
| **AWS CodeBuild** (build.general1.small) | ~10 min | ~$0.005/build |

---

## 8. Arquitectura en AWS (Producción)

| Componente | Servicio AWS | Tipo |
|---|---|---|
| **API (microservicio)** | ECS Fargate | Service (always-on) |
| **Batch Processor (OCR + CLIP)** | ECS Fargate | Task (on-demand) |
| **Scheduler** | EventBridge | Cron 2:00 AM Colombia |
| **Base de datos** | RDS PostgreSQL + pgvector | Instancia |
| **Almacenamiento imágenes** | S3 | Bucket |
| **OCR** | AWS Textract | API (reemplaza Tesseract) |
| **Secrets** | SSM Parameter Store | Parámetros |
| **Logs** | CloudWatch | Log groups |
| **CI/CD** | GitHub Actions | Free tier |

### Costo estimado mensual (producción ligera)

| Servicio | Estimado |
|---|---|
| Fargate API (0.5 vCPU, 1GB, 24/7) | ~$15/mes |
| Fargate Batch (2 vCPU, 4GB, 30 min/día) | ~$1/mes |
| RDS PostgreSQL (db.t3.micro) | ~$15/mes |
| S3 (10GB imágenes) | ~$0.25/mes |
| Textract (1000 páginas/mes) | ~$1.50/mes |
| **Total estimado** | **~$33/mes** |

---

## 9. Flujo completo de búsqueda por imagen

```
1. Usuario sube imagen de búsqueda
         ↓
2. CLIP (o DINOv2) genera embedding (vector 512/384 dims) — en el momento
         ↓
3. pgvector busca los vectores más similares (cosine similarity)
         ↓
4. Retorna las imágenes más parecidas con score de similitud
```

### ¿Por qué CLIP/DINOv2 y no comparar píxeles?

```
Comparar píxeles:     "¿Son los mismos bytes?"        → Inútil
Comparar con CLIP:    "¿Se parecen semánticamente?"   → Inteligente

Ejemplo: foto de un gato negro de frente vs de lado
  - Píxeles: 0% similitud
  - CLIP:    95% similitud (entiende que es un gato)
```

---

## 10. Roadmap de implementación

### Fase 1 (Actual)
- [x] CLIP ViT-B/32 para embeddings
- [x] pgvector para búsqueda vectorial
- [x] Tesseract OCR
- [x] Batch processor
- [ ] Levantar con PyTorch CPU-only

### Fase 2 (Próximo sprint)
- [ ] Agregar DINOv2 ViT-S/14 como segunda columna
- [ ] Endpoint `/search/by-image` usa DINOv2
- [ ] Endpoint `/search/by-text` usa CLIP
- [ ] Endpoint `/search/hybrid` combina ambos

### Fase 3 (Producción AWS)
- [ ] Deploy en ECS Fargate
- [ ] RDS PostgreSQL con pgvector
- [ ] EventBridge para batch nocturno
- [ ] GitHub Actions CI/CD
- [ ] Textract en lugar de Tesseract

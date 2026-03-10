# AWS Deployment Guide — Batch Lambda + Search API

## Arquitectura

```
                        ┌─────────────────────────────┐
                        │        EC2 Instance          │
                        │   (whatsapp-ingestion API)   │
                        │                              │
                        │  FastAPI + Search Endpoints  │
                        │  POST /api/v1/search/by-image│
                        │  POST /api/v1/search/by-text │
                        │  POST /api/v1/search/hybrid  │
                        │  POST /api/v1/batch/process  │
                        │                              │
                        │  IAM Role: ec2-ingesta-role  │
                        └──────────┬───────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌─────────────┐
              │    S3     │  │ Bedrock  │  │ PostgreSQL  │
              │ whatsapp- │  │  Titan   │  │  + pgvector │
              │ images    │  │ Multimod │  │  (RDS)      │
              └──────────┘  └──────────┘  └─────────────┘
                    ▲              ▲
                    │              │
                    └──────┬───────┘
                           │
                        ┌──┴───────────────────────────┐
                        │     Lambda Function           │
                        │  (whatsapp-batch-processor)   │
                        │                               │
                        │  1. Lista pendientes (API)    │
                        │  2. Descarga imagen de S3     │
                        │  3. Textract OCR              │
                        │  4. Titan image embedding     │
                        │  5. Titan text embedding      │
                        │  6. Envía resultados (API)    │
                        │                               │
                        │  Conecta a EC2 via HTTP ──────┼──► EC2 FastAPI :3000
                        │                               │
                        │  IAM Role: lambda-batch-role  │
                        └───────────────────────────────┘
                                   ▲
                                   │
                        ┌──────────┴───────────┐
                        │    EventBridge        │
                        │  cron(0 7 * * ? *)    │
                        │  2:00 AM Colombia     │
                        └──────────────────────┘
```

## Servicios AWS utilizados

| Servicio | Propósito | Costo estimado (1000 imgs/día) |
|---|---|---|
| EC2 (t3.small) | API FastAPI + Search | ~$15/mes |
| Lambda | Batch processor | ~$0.10/mes |
| S3 | Almacenamiento de imágenes | ~$0.50/mes |
| Textract | OCR | ~$1.50/mes |
| Bedrock Titan | Embeddings 1024 dims | ~$0.06/mes |
| RDS PostgreSQL | Metadata + pgvector | ~$15/mes |
| EventBridge | Cron trigger | Gratis |

## Modelo de embeddings

**Titan Multimodal Embeddings G1** (`amazon.titan-embed-image-v1`)
- Imagen → vector 1024 dims
- Texto → vector 1024 dims (mismo espacio vectorial)
- Permite búsqueda cross-modal (buscar por imagen O por texto)

## Autenticación AWS

**No se usan Access Keys.** Todo por IAM Roles:

| Componente | Cómo se autentica |
|---|---|
| EC2 (API) | IAM Instance Role → boto3 lee del instance metadata |
| Lambda (batch) | IAM Execution Role → se asigna al crear la Lambda |

boto3 detecta automáticamente las credenciales del role sin necesidad de `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en `.env`.

---

## Paso 1: Crear IAM Role para EC2

### 1a. Crear policy de permisos para EC2

```bash
aws iam create-policy \
  --policy-name ec2-whatsapp-ingestion-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "S3Access",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"],
        "Resource": ["arn:aws:s3:::whatsapp-images-prod", "arn:aws:s3:::whatsapp-images-prod/*"]
      },
      {
        "Sid": "TextractOCR",
        "Effect": "Allow",
        "Action": ["textract:DetectDocumentText"],
        "Resource": "*"
      },
      {
        "Sid": "BedrockTitan",
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel"],
        "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-image-v1"
      }
    ]
  }'
```

### 1b. Crear role para EC2

```bash
aws iam create-role \
  --role-name ec2-whatsapp-ingestion-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

### 1c. Asignar policy al role

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws iam attach-role-policy \
  --role-name ec2-whatsapp-ingestion-role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/ec2-whatsapp-ingestion-policy
```

### 1d. Crear instance profile y asignar a EC2

```bash
aws iam create-instance-profile \
  --instance-profile-name ec2-whatsapp-ingestion-profile

aws iam add-role-to-instance-profile \
  --instance-profile-name ec2-whatsapp-ingestion-profile \
  --role-name ec2-whatsapp-ingestion-role

# Asignar a la instancia EC2
aws ec2 associate-iam-instance-profile \
  --instance-id i-XXXXXXXXX \
  --iam-instance-profile Name=ec2-whatsapp-ingestion-profile
```

> **Nota:** Si creas el role desde la consola visual (IAM → Roles → Create → EC2), el instance profile se crea automáticamente. Solo necesitas el comando si lo haces por CLI.

---

## Paso 2: Crear IAM Role para Lambda

### 2a. Crear policy de permisos para Lambda

```bash
aws iam create-policy \
  --policy-name lambda-batch-processor-policy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "S3Access",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:ListBucket"],
        "Resource": ["arn:aws:s3:::whatsapp-images-prod", "arn:aws:s3:::whatsapp-images-prod/*"]
      },
      {
        "Sid": "TextractOCR",
        "Effect": "Allow",
        "Action": ["textract:DetectDocumentText"],
        "Resource": "*"
      },
      {
        "Sid": "BedrockTitan",
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel"],
        "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-image-v1"
      },
      {
        "Sid": "CloudWatchLogs",
        "Effect": "Allow",
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "arn:aws:logs:*:*:*"
      }
    ]
  }'
```

### 2b. Crear role para Lambda

```bash
aws iam create-role \
  --role-name lambda-batch-processor-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

### 2c. Asignar policy al role

```bash
aws iam attach-role-policy \
  --role-name lambda-batch-processor-role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/lambda-batch-processor-policy
```

---

## Paso 3: Empaquetar código para Lambda

```bash
mkdir -p build/lambda

docker run --rm -v $(pwd):/app -w /app python:3.11-slim bash -c "
  apt-get update && apt-get install -y zip &&
  pip install boto3 httpx pydantic -t build/lambda &&
  cp -r src/ build/lambda/src/ &&
  cd build/lambda &&
  zip -r ../lambda-package.zip . -x '*.pyc' '__pycache__/*'
"
```

> **Nota:** Lambda ya no conecta directamente a PostgreSQL. Se comunica con la FastAPI via HTTP
> usando `httpx`, por lo que no necesita `sqlalchemy`, `asyncpg`, `pgvector` ni `pydantic-settings`.

---

## Paso 4: Crear función Lambda

```bash
aws lambda create-function \
  --function-name whatsapp-batch-processor \
  --runtime python3.11 \
  --handler src.batch.lambda_handler.handler \
  --role arn:aws:iam::${ACCOUNT_ID}:role/lambda-batch-processor-role \
  --zip-file fileb://build/lambda-package.zip \
  --timeout 900 \
  --memory-size 512 \
  --environment "Variables={
    API_BASE_URL=http://<EC2_IP>:3000,
    S3_BUCKET_NAME=whatsapp-images-prod,
    S3_PREFIX=images/,
    S3_REGION=us-east-1,
    OCR_ENABLED=true,
    EMBEDDINGS_ENABLED=true,
    TEXTRACT_REGION=us-east-1,
    BEDROCK_REGION=us-east-1,
    TITAN_MODEL_ID=amazon.titan-embed-image-v1
  }"
```

> El role se asigna directamente con `--role`. No se necesita instance profile ni paso adicional.
>
> **Importante:** Reemplaza `<EC2_IP>` con la IP pública de tu instancia EC2. Lambda NO necesita `--vpc-config` porque se comunica con la API via HTTP público, no accede directamente a la base de datos.

---

## Paso 5: Crear EventBridge (cron)

```bash
# Crear regla: 2:00 AM Colombia = 07:00 UTC
aws events put-rule \
  --name batch-processor-schedule \
  --schedule-expression "cron(0 7 * * ? *)" \
  --state ENABLED \
  --description "Batch processor diario 2:00 AM Colombia"

# Dar permiso a EventBridge para invocar Lambda
aws lambda add-permission \
  --function-name whatsapp-batch-processor \
  --statement-id eventbridge-invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:${ACCOUNT_ID}:rule/batch-processor-schedule

# Conectar EventBridge → Lambda
aws events put-targets \
  --rule batch-processor-schedule \
  --targets "Id=batch-lambda,Arn=arn:aws:lambda:us-east-1:${ACCOUNT_ID}:function:whatsapp-batch-processor"
```

---

## Paso 6: Probar

```bash
# Invocar Lambda manualmente
aws lambda invoke \
  --function-name whatsapp-batch-processor \
  --payload '{"source": "manual", "trigger": "test"}' \
  --cli-read-timeout 900 \
  /tmp/lambda-output.json

cat /tmp/lambda-output.json

# Ver logs en tiempo real
aws logs tail /aws/lambda/whatsapp-batch-processor --follow
```

---

## Paso 7: Actualizar código (después de cambios)

```bash
# Re-empaquetar
cd build/lambda && zip -r ../lambda-package.zip . -x '*.pyc' && cd ../..

# Subir nueva versión
aws lambda update-function-code \
  --function-name whatsapp-batch-processor \
  --zip-file fileb://build/lambda-package.zip
```

---

## Habilitar Titan en Bedrock

Antes de usar Titan, verifica que tengas acceso:

```bash
aws bedrock list-foundation-models \
  --query "modelSummaries[?modelId=='amazon.titan-embed-image-v1']"
```

Si no aparece:
1. AWS Console → Bedrock → Model access
2. Request access → Amazon Titan Multimodal Embeddings G1
3. Submit (aprobación inmediata)

---

## Variables de entorno (.env) para EC2

```env
# Database
DATABASE_URL=postgresql://user:pass@tu-rds-host:5432/whatsapp_ingestion
EVOLUTION_DATABASE_URL=postgresql://user:pass@tu-rds-host:5432/evolution

# S3 (sin keys — usa IAM Role)
S3_BUCKET_NAME=whatsapp-images-prod
S3_PREFIX=images/
S3_REGION=us-east-1
STORAGE_BACKEND=s3

# Textract OCR
OCR_ENABLED=true
TEXTRACT_REGION=us-east-1

# Bedrock Titan
EMBEDDINGS_ENABLED=true
BEDROCK_REGION=us-east-1
TITAN_MODEL_ID=amazon.titan-embed-image-v1
```

---

## Search API — Endpoints

### Buscar por imagen
```bash
curl -X POST http://tu-ec2:3000/api/v1/search/by-image \
  -F "image=@foto.jpg" \
  -F "limit=5"
```

### Buscar por texto
```bash
curl -X POST http://tu-ec2:3000/api/v1/search/by-text \
  -F "query=factura con logo rojo" \
  -F "limit=5"
```

### Búsqueda híbrida
```bash
curl -X POST http://tu-ec2:3000/api/v1/search/hybrid \
  -F "image=@foto.jpg" \
  -F "query=factura" \
  -F "limit=5"
```

### Respuesta ejemplo
```json
{
  "results": [
    {
      "id": 42,
      "id_secuencial": 42,
      "id_mensaje": "msg_abc123",
      "tipo_origen": "chat",
      "numero_celular": "573001234567",
      "nombre_usuario": "Juan",
      "instancia": "mi-instancia",
      "s3_key": "images/42.jpg",
      "texto_ocr": "Factura #123...",
      "processing_status": "completed",
      "similarity_score": 0.9234,
      "image_url": "https://whatsapp-images-prod.s3.amazonaws.com/images/42.jpg?X-Amz-..."
    }
  ],
  "total": 1,
  "query_type": "by-image"
}
```

---

## Diferencia de permisos EC2 vs Lambda

| Permiso | EC2 | Lambda |
|---|---|---|
| S3 GetObject | Si | Si |
| S3 PutObject | Si | No (solo lee) |
| S3 DeleteObject | Si | No |
| Textract | Si | Si |
| Bedrock InvokeModel | Si | Si |
| CloudWatch Logs | No | Si |

---

## Paso 8: Crear el bucket S3

```bash
aws s3 mb s3://whatsapp-images-prod --region us-east-1

# Bloquear acceso público
aws s3api put-public-access-block \
  --bucket whatsapp-images-prod \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## Paso 9: Crear RDS PostgreSQL + pgvector

### 9a. Crear Security Group para RDS

```bash
# Obtener VPC default
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)

aws ec2 create-security-group \
  --group-name rds-whatsapp-sg \
  --description "PostgreSQL for whatsapp ingestion" \
  --vpc-id $VPC_ID

# Obtener el ID del SG creado
RDS_SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=rds-whatsapp-sg --query "SecurityGroups[0].GroupId" --output text)

# Abrir puerto 5432 solo desde la VPC (rango CIDR de tu VPC)
VPC_CIDR=$(aws ec2 describe-vpcs --vpc-ids $VPC_ID --query "Vpcs[0].CidrBlock" --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG \
  --protocol tcp \
  --port 5432 \
  --cidr $VPC_CIDR
```

### 9b. Crear instancia RDS

```bash
aws rds create-db-instance \
  --db-instance-identifier whatsapp-postgres \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username postgres \
  --master-user-password TU_PASSWORD_SEGURO \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids $RDS_SG \
  --db-name whatsapp_ingestion \
  --backup-retention-period 7 \
  --no-multi-az \
  --publicly-accessible \
  --storage-encrypted

# Esperar a que esté disponible (~5-10 min)
aws rds wait db-instance-available --db-instance-identifier whatsapp-postgres

# Obtener el endpoint
RDS_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier whatsapp-postgres \
  --query "DBInstances[0].Endpoint.Address" --output text)

echo "RDS Endpoint: $RDS_HOST"
```

### 9c. Instalar pgvector en RDS

```bash
# Conectar y habilitar pgvector
psql -h $RDS_HOST -U postgres -d whatsapp_ingestion -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Crear también la BD de Evolution API
psql -h $RDS_HOST -U postgres -c "CREATE DATABASE evolution;"
```

> **Nota:** RDS PostgreSQL 15+ ya incluye pgvector. Solo necesitas hacer `CREATE EXTENSION vector`.

---

## Paso 10: Crear instancia EC2

### 10a. Crear Security Group para EC2

```bash
aws ec2 create-security-group \
  --group-name ec2-whatsapp-sg \
  --description "WhatsApp ingestion API" \
  --vpc-id $VPC_ID

EC2_SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=ec2-whatsapp-sg --query "SecurityGroups[0].GroupId" --output text)

# Abrir SSH (puerto 22)
aws ec2 authorize-security-group-ingress \
  --group-id $EC2_SG \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Abrir API (puerto 3000)
aws ec2 authorize-security-group-ingress \
  --group-id $EC2_SG \
  --protocol tcp \
  --port 3000 \
  --cidr 0.0.0.0/0

# Abrir Evolution API (puerto 8080)
aws ec2 authorize-security-group-ingress \
  --group-id $EC2_SG \
  --protocol tcp \
  --port 8080 \
  --cidr 0.0.0.0/0
```

### 10b. Crear Key Pair para SSH

```bash
aws ec2 create-key-pair \
  --key-name whatsapp-ingestion-key \
  --query "KeyMaterial" \
  --output text > whatsapp-ingestion-key.pem

chmod 400 whatsapp-ingestion-key.pem
```

### 10c. Lanzar instancia EC2

```bash
# Amazon Linux 2023 AMI (us-east-1)
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" --output text)

aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.small \
  --key-name whatsapp-ingestion-key \
  --security-group-ids $EC2_SG \
  --iam-instance-profile Name=ec2-whatsapp-ingestion-profile \
  --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=whatsapp-ingestion}]" \
  --count 1

# Obtener IP pública
EC2_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=whatsapp-ingestion" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PublicIpAddress" --output text)

echo "EC2 IP: $EC2_IP"
```

### 10d. Conectar por SSH e instalar Docker

```bash
ssh -i whatsapp-ingestion-key.pem ec2-user@$EC2_IP
```

Dentro del EC2:

```bash
# Instalar Docker
sudo dnf update -y
sudo dnf install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Re-login para aplicar grupo docker
exit
```

### 10e. Desplegar la aplicación

```bash
ssh -i whatsapp-ingestion-key.pem ec2-user@$EC2_IP

# Clonar repo
git clone https://github.com/tu-usuario/ingesta-evolution-api.git
cd ingesta-evolution-api

# Crear .env de producción
cat > .env << 'EOF'
# Application
APP_NAME="WhatsApp Integration Microservice"
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=3000

# Evolution API
EVOLUTION_API_URL=http://evolution-api:8080
EVOLUTION_API_KEY=TU_API_KEY_SEGURA
EVOLUTION_API_TIMEOUT=30.0

# Database (apuntar a RDS)
DATABASE_URL=postgresql://postgres:TU_PASSWORD_SEGURO@TU_RDS_HOST:5432/whatsapp_ingestion
EVOLUTION_DATABASE_URL=postgresql://postgres:TU_PASSWORD_SEGURO@TU_RDS_HOST:5432/evolution

# Redis
REDIS_URL=redis://redis:6379
REDIS_PREFIX=whatsapp_ms

# S3 (sin keys — usa IAM Role del EC2)
S3_BUCKET_NAME=whatsapp-images-prod
S3_PREFIX=images/
S3_REGION=us-east-1
STORAGE_BACKEND=s3

# Textract OCR
OCR_ENABLED=true
TEXTRACT_REGION=us-east-1

# Bedrock Titan
EMBEDDINGS_ENABLED=true
BEDROCK_REGION=us-east-1
TITAN_MODEL_ID=amazon.titan-embed-image-v1

# Logging
LOG_LEVEL=INFO
CORS_ORIGINS=*
EOF
```

### 10f. docker-compose para producción

En producción usas RDS y S3 reales, no MinIO ni PostgreSQL local. Crea un override:

```bash
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  whatsapp-microservice:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whatsapp-microservice
    restart: unless-stopped
    ports:
      - "3000:3000"
    env_file:
      - .env
    depends_on:
      redis:
        condition: service_healthy
      evolution-api:
        condition: service_started
    networks:
      - whatsapp_network

  evolution-api:
    build:
      context: ./.evolution-api-build
    image: evolution-api:2.3.7
    container_name: evolution-api
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - SERVER_URL=http://localhost:8080
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY:-your-api-key}
      - AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
      - CACHE_REDIS_ENABLED=true
      - CACHE_REDIS_URI=redis://redis:6379
      - CACHE_REDIS_PREFIX_KEY=evolution
      - CACHE_REDIS_TTL=604800
      - CACHE_LOCAL_ENABLED=false
      - RABBITMQ_ENABLED=false
      - WEBSOCKET_ENABLED=true
      - WEBSOCKET_GLOBAL_EVENTS=true
      - DATABASE_ENABLED=true
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=${EVOLUTION_DATABASE_URL}
      - STORE_MESSAGES=true
      - STORE_MESSAGE_UP=true
      - STORE_CONTACTS=true
      - STORE_CHATS=true
      - CONFIG_SESSION_PHONE_VERSION=${CONFIG_SESSION_PHONE_VERSION:-2.3000.1034566421}
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - whatsapp_network
    volumes:
      - evolution_instances:/evolution/instances

  redis:
    image: redis:7-alpine
    container_name: whatsapp-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - whatsapp_network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

networks:
  whatsapp_network:
    driver: bridge

volumes:
  evolution_instances:
  redis_data:
EOF
```

### 10g. Levantar en producción

```bash
# Build y arrancar
docker-compose -f docker-compose.prod.yml up -d --build

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f whatsapp-microservice

# Verificar salud
curl http://localhost:3000/api/v1/health/live
```

---

## Paso 11: Verificar todo funciona

```bash
# 1. Health check API
curl http://$EC2_IP:3000/api/v1/health/live

# 2. Probar search (necesitas imágenes procesadas primero)
curl -X POST http://$EC2_IP:3000/api/v1/search/by-image \
  -F "image=@foto.jpg" \
  -F "limit=5"

# 3. Ejecutar batch manualmente
aws lambda invoke \
  --function-name whatsapp-batch-processor \
  --payload '{"source": "manual", "trigger": "test"}' \
  --cli-read-timeout 900 \
  /tmp/lambda-output.json && cat /tmp/lambda-output.json

# 4. Ver logs del Lambda
aws logs tail /aws/lambda/whatsapp-batch-processor --follow
```

---

## Resumen de infraestructura completa

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Account                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    VPC (default)                     │    │
│  │                                                     │    │
│  │  ┌──────────────────┐     ┌──────────────────────┐  │    │
│  │  │     EC2          │     │      RDS              │  │    │
│  │  │  t3.small        │────▶│  db.t3.micro          │  │    │
│  │  │                  │     │  PostgreSQL 15         │  │    │
│  │  │  Docker:         │     │  + pgvector            │  │    │
│  │  │  - FastAPI :3000 │◀──┐ │                        │  │    │
│  │  │  - Evolution API │   │ │  DBs:                  │  │    │
│  │  │  - Redis         │   │ │  - whatsapp_ingestion  │  │    │
│  │  │                  │   │ │  - evolution            │  │    │
│  │  │  IAM Role:       │   │ └──────────────────────┘  │    │
│  │  │  ec2-ingesta     │   │                           │    │
│  │  └──────────────────┘   │ (HTTP)                    │    │
│  │           │             │                           │    │
│  │           ▼             │                           │    │
│  │  ┌──────────────────┐   │ ┌──────────────────────┐  │    │
│  │  │       S3         │   │ │      Lambda           │  │    │
│  │  │  whatsapp-       │◀──┼─│  batch-processor      │  │    │
│  │  │  images-prod     │   └─│  512MB / 15min        │  │    │
│  │  └──────────────────┘     │                        │  │    │
│  │                           │  IAM Role:             │  │    │
│  │  ┌──────────────────┐     │  lambda-batch          │  │    │
│  │  │    Bedrock        │◀───│                        │  │    │
│  │  │  Titan Multimodal │     └───────────────────────┘  │    │
│  │  └──────────────────┘                ▲              │    │
│  │                                      │              │    │
│  │  ┌──────────────────┐     ┌──────────┴───────────┐  │    │
│  │  │    Textract       │     │    EventBridge        │  │    │
│  │  │  OCR              │     │  cron: 2AM Colombia   │  │    │
│  │  └──────────────────┘     └──────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

> **Nota:** Lambda NO conecta directamente a RDS. Se comunica con la FastAPI en EC2 via HTTP
> para obtener imágenes pendientes y enviar resultados de procesamiento (OCR + embeddings).

## Costos mensuales estimados

| Servicio | Especificación | Costo/mes |
|---|---|---|
| EC2 | t3.small (24/7) | ~$15 |
| RDS | db.t3.micro (24/7) | ~$15 |
| S3 | 10 GB imágenes | ~$0.50 |
| Lambda | 1 invocación/día, 15 min | ~$0.10 |
| Textract | 1000 páginas/día | ~$45 |
| Bedrock Titan | 1000 embeddings/día | ~$1.80 |
| EventBridge | Cron rule | Gratis |
| **Total** | | **~$77/mes** |

> Para reducir costos: usar EC2 Reserved Instance (-40%) y RDS Reserved (-40%) = ~$50/mes

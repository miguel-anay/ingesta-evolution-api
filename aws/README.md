# AWS Deployment - Manual Setup

## Overview

- **API** → EC2 con Docker Compose (ver sección al final)
- **Batch Processor** (OCR + CLIP) → ECS Fargate, triggered nightly por EventBridge
- **Imagen Docker** → Una sola, en ECR repo `whatsapp-microservice`

**Schedule:** Every day at 2:00 AM Colombia time (07:00 UTC)
**Resources:** 2 vCPU, 4 GB RAM (Fargate)

---

## Paso 1: Crear ECR Repository

```bash
aws ecr create-repository \
  --repository-name whatsapp-microservice \
  --region us-east-1
```

## Paso 2: Build y Push de la imagen Docker

```bash
# Login a ECR (reemplazar ACCOUNT_ID con tu ID de 12 dígitos)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build y push
docker build -t whatsapp-microservice .
docker tag whatsapp-microservice:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/whatsapp-microservice:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/whatsapp-microservice:latest
```

> **Nota:** Si buildeas desde Windows/Mac con chip ARM, agrega `--platform linux/amd64` al build para que sea compatible con Fargate.

## Paso 3: Crear IAM Roles

### 3a. Task Execution Role (`ecsTaskExecutionRole`)

```bash
# Crear rol con trust policy para ECS
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Adjuntar política managed
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Agregar acceso a SSM Parameter Store (para secrets)
aws iam put-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-name SSMParameterAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["ssm:GetParameters", "ssm:GetParameter"],
      "Resource": "arn:aws:ssm:us-east-1:ACCOUNT_ID:parameter/batch-processor/*"
    }]
  }'
```

### 3b. Task Role (`batch-processor-task-role`)

```bash
aws iam create-role \
  --role-name batch-processor-task-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# S3 access
aws iam put-role-policy \
  --role-name batch-processor-task-role \
  --policy-name S3Access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::whatsapp-images",
        "arn:aws:s3:::whatsapp-images/*"
      ]
    }]
  }'

# Textract access
aws iam put-role-policy \
  --role-name batch-processor-task-role \
  --policy-name TextractAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["textract:DetectDocumentText"],
      "Resource": "*"
    }]
  }'
```

### 3c. EventBridge Role (`ecsEventsRole`)

```bash
aws iam create-role \
  --role-name ecsEventsRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam put-role-policy \
  --role-name ecsEventsRole \
  --policy-name ECSRunTask \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "ecs:RunTask",
        "Resource": "arn:aws:ecs:us-east-1:ACCOUNT_ID:task-definition/batch-processor:*"
      },
      {
        "Effect": "Allow",
        "Action": "iam:PassRole",
        "Resource": [
          "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
          "arn:aws:iam::ACCOUNT_ID:role/batch-processor-task-role"
        ]
      }
    ]
  }'
```

## Paso 4: Crear SSM Parameters (secrets del batch)

```bash
aws ssm put-parameter --name /batch-processor/DATABASE_URL \
  --type SecureString \
  --value "postgresql://user:pass@tu-rds-host:5432/whatsapp_ingestion"

aws ssm put-parameter --name /batch-processor/S3_BUCKET_NAME \
  --type String --value "whatsapp-images"

aws ssm put-parameter --name /batch-processor/S3_PREFIX \
  --type String --value "images/"

aws ssm put-parameter --name /batch-processor/S3_REGION \
  --type String --value "us-east-1"

aws ssm put-parameter --name /batch-processor/TEXTRACT_REGION \
  --type String --value "us-east-1"
```

## Paso 5: Crear CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name /ecs/batch-processor --region us-east-1
```

## Paso 6: Crear ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name ingesta-cluster \
  --capacity-providers FARGATE \
  --region us-east-1
```

## Paso 7: Registrar Task Definition

```bash
# Reemplazar ACCOUNT_ID en el template
sed "s/ACCOUNT_ID/123456789012/g" aws/task-definition.json > /tmp/task-def.json

# Registrar
aws ecs register-task-definition \
  --cli-input-json file:///tmp/task-def.json \
  --region us-east-1
```

## Paso 8: Crear EventBridge Rule (schedule nightly)

```bash
# Editar aws/eventbridge-rule.json con tu ACCOUNT_ID, subnets y security groups

# Crear la regla
aws events put-rule \
  --name batch-processor-nightly \
  --schedule-expression "cron(0 7 * * ? *)" \
  --state ENABLED \
  --description "Batch processor at 2:00 AM Colombia (07:00 UTC)" \
  --region us-east-1

# Agregar target (Fargate task)
aws events put-targets \
  --rule batch-processor-nightly \
  --targets file://aws/eventbridge-rule.json \
  --region us-east-1
```

## Paso 9: Networking

El Fargate task necesita acceso a:
- **PostgreSQL** (RDS o EC2): SG debe permitir inbound puerto 5432 desde el SG del Fargate task
- **S3**: Vía VPC endpoint o internet público (`AssignPublicIp=ENABLED`)
- **Textract API**: Vía internet público o VPC endpoint

> Editar `subnet-XXXXXXXX` y `sg-XXXXXXXX` en `aws/eventbridge-rule.json` con tus valores reales.

---

## Test Manual

```bash
# Ejecutar el batch processor una vez (sin esperar EventBridge)
aws ecs run-task \
  --cluster ingesta-cluster \
  --task-definition batch-processor \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-XXX],securityGroups=[sg-XXX],assignPublicIp=ENABLED}" \
  --region us-east-1

# Ver logs
aws logs tail /ecs/batch-processor --follow --region us-east-1
```

---

## Deploy del Microservicio en EC2

```bash
# SSH al EC2
ssh -i tu-key.pem ubuntu@<EC2_IP>

# Clonar repo (primera vez)
cd /home/ubuntu
git clone https://github.com/TU_USER/ingesta-evolution-api.git
cd ingesta-evolution-api

# Crear .env con valores de producción
cp .env.example .env
nano .env

# Levantar todo
docker compose up -d

# Verificar
docker compose ps
curl http://localhost:3000/api/v1/health/live
```

Para actualizar:
```bash
cd /home/ubuntu/ingesta-evolution-api
git pull
docker compose up -d --build
```

---

## Monitoring

| Qué | Dónde |
|-----|-------|
| Logs batch | CloudWatch → `/ecs/batch-processor` |
| Task status | ECS Console → ingesta-cluster → Tasks |
| Schedule | EventBridge → Rules → `batch-processor-nightly` |
| API logs | EC2 → `docker compose logs -f whatsapp-microservice` |

## Cost Estimate

| Servicio | Costo |
|----------|-------|
| Fargate | ~$0.05/run (2 vCPU, 4GB, ~5 min) |
| Textract | $1.50 per 1000 pages |
| S3 | Minimal (GET requests) |
| EventBridge | Free (< 1M invocations/month) |
| ECR | $0.10/GB/month storage |

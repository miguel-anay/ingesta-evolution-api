#!/bin/bash
# Script de Pruebas - Servicio de Ingestión de Imágenes
# Uso: ./test-ingestion.sh [numero-celular] [instancia]

set -e

# Configuración
NUM_CELULAR="${1:-51999999999}"
INSTANCIA="${2:-mi-instancia}"
BASE_URL="http://localhost:3000"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Funciones de output
success() { echo -e "${GREEN}$1${NC}"; }
info() { echo -e "${CYAN}$1${NC}"; }
warning() { echo -e "${YELLOW}$1${NC}"; }
error() { echo -e "${RED}$1${NC}"; }
step() { echo -e "\n${MAGENTA}===== $1 =====${NC}"; }

# Función para hacer requests
api_request() {
    local method=$1
    local endpoint=$2
    local body=$3

    if [ "$method" = "GET" ]; then
        curl -s "$BASE_URL$endpoint"
    else
        curl -s -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$body"
    fi
}

# Banner
cat << "EOF"

╔═══════════════════════════════════════════════════╗
║  Servicio de Ingestión de Imágenes - Test Suite  ║
║              US-ING-001 - Evolution API           ║
╚═══════════════════════════════════════════════════╝

EOF

info "Configuración:"
info "  • Base URL: $BASE_URL"
info "  • Número Celular: $NUM_CELULAR"
info "  • Instancia: $INSTANCIA"
echo

# Test 1: Health Check
step "Test 1: Health Check"
health=$(api_request GET "/api/v1/health")
status=$(echo "$health" | jq -r '.status')

if [ "$status" = "healthy" ]; then
    success "  ✓ Servicio saludable"
else
    error "  ✗ Servicio no responde correctamente"
    exit 1
fi

# Test 2: Ingestion Status
step "Test 2: Estado de Ingestión Inicial"
initial_status=$(api_request GET "/api/v1/ingestion/status")
initial_count=$(echo "$initial_status" | jq -r '.total_images_ingested')
images_dir=$(echo "$initial_status" | jq -r '.images_directory')
metadata_file=$(echo "$initial_status" | jq -r '.metadata_file')

success "  ✓ Status endpoint responde"
info "    • Total imágenes: $initial_count"
info "    • Directorio: $images_dir"
info "    • Archivo metadata: $metadata_file"

# Test 3: Primera Ingestión
step "Test 3: Primera Ingestión de Imágenes"
info "  Ingiriendo imágenes del número '$NUM_CELULAR' en instancia '$INSTANCIA'..."

ingest_result=$(api_request POST "/api/v1/ingestion/ingest" \
    "{\"numero_celular\": \"$NUM_CELULAR\", \"instancia\": \"$INSTANCIA\"}")

ingested=$(echo "$ingest_result" | jq -r '.images_ingested')
skipped=$(echo "$ingest_result" | jq -r '.images_skipped')
total=$(echo "$ingest_result" | jq -r '.total_processed')
exec_time=$(echo "$ingest_result" | jq -r '.execution_time_seconds')

success "  ✓ Ingestión completada"
info "    • Imágenes ingresadas: $ingested"
info "    • Imágenes omitidas: $skipped"
info "    • Total procesadas: $total"
info "    • Tiempo: ${exec_time}s"

if [ "$ingested" -eq 0 ]; then
    warning "  ⚠ No se encontraron imágenes nuevas"
fi

# Test 4: Verificar Metadata
step "Test 4: Verificación de Metadata"
metadata=$(api_request GET "/api/v1/ingestion/metadata")
metadata_total=$(echo "$metadata" | jq -r '.total')

success "  ✓ Metadata disponible"
info "    • Total registros: $metadata_total"

if [ "$metadata_total" -gt 0 ]; then
    first_id=$(echo "$metadata" | jq -r '.metadata[0].id_secuencial')
    first_origin=$(echo "$metadata" | jq -r '.metadata[0].tipo_origen')
    first_user=$(echo "$metadata" | jq -r '.metadata[0].nombre_usuario')
    first_phone=$(echo "$metadata" | jq -r '.metadata[0].numero_telefono')

    info "    • Primera imagen:"
    info "      - ID: $first_id"
    info "      - Origen: $first_origin"
    info "      - Usuario: $first_user"
    info "      - Teléfono: $first_phone"
fi

# Test 5: Prueba de Idempotencia
step "Test 5: Prueba de Idempotencia (Re-ejecución)"
info "  Ejecutando ingestión nuevamente..."

ingest_result2=$(api_request POST "/api/v1/ingestion/ingest" \
    "{\"numero_celular\": \"$NUM_CELULAR\", \"instancia\": \"$INSTANCIA\"}")

ingested2=$(echo "$ingest_result2" | jq -r '.images_ingested')
skipped2=$(echo "$ingest_result2" | jq -r '.images_skipped')
exec_time2=$(echo "$ingest_result2" | jq -r '.execution_time_seconds')

if [ "$ingested2" -eq 0 ] && [ "$skipped2" -gt 0 ]; then
    success "  ✓ Idempotencia verificada"
    info "    • Imágenes omitidas: $skipped2"
    info "    • Tiempo: ${exec_time2}s"
else
    warning "  ⚠ Se ingresaron nuevas imágenes: $ingested2"
fi

# Test 6: Ingestión solo de Chats
step "Test 6: Ingestión Solo de Chats"
chat_result=$(api_request POST "/api/v1/ingestion/ingest/chat" \
    "{\"numero_celular\": \"$NUM_CELULAR\", \"instancia\": \"$INSTANCIA\", \"limit\": 10}")

chat_ingested=$(echo "$chat_result" | jq -r '.images_ingested')
success "  ✓ Ingestión de chats completada"
info "    • Imágenes de chats: $chat_ingested"

# Test 7: Ingestión solo de Estados
step "Test 7: Ingestión Solo de Estados"
status_result=$(api_request POST "/api/v1/ingestion/ingest/status" \
    "{\"numero_celular\": \"$NUM_CELULAR\", \"instancia\": \"$INSTANCIA\"}")

status_ingested=$(echo "$status_result" | jq -r '.images_ingested')
success "  ✓ Ingestión de estados completada"
info "    • Imágenes de estados: $status_ingested"

# Test 8: Verificar archivos físicos
step "Test 8: Verificación de Archivos Físicos"

images_dir_local="./data/images"
metadata_file_local="./data/metadata/images.csv"

if [ -d "$images_dir_local" ]; then
    image_count=$(find "$images_dir_local" -name "*.jpg" | wc -l)
    success "  ✓ Directorio de imágenes existe"
    info "    • Total archivos .jpg: $image_count"

    if [ "$image_count" -gt 0 ]; then
        info "    • Primeros archivos:"
        find "$images_dir_local" -name "*.jpg" | head -5 | while read file; do
            size=$(du -h "$file" | cut -f1)
            basename=$(basename "$file")
            info "      - $basename ($size)"
        done
    fi
else
    warning "  ⚠ Directorio de imágenes no existe"
fi

if [ -f "$metadata_file_local" ]; then
    line_count=$(wc -l < "$metadata_file_local")
    success "  ✓ Archivo CSV de metadata existe"
    info "    • Líneas en CSV: $line_count"
    info "    • Registros: $((line_count - 1))"

    info "    • Primeras líneas del CSV:"
    head -3 "$metadata_file_local" | while read line; do
        info "      $line"
    done
else
    warning "  ⚠ Archivo CSV de metadata no existe"
fi

# Test 9: Estado Final
step "Test 9: Estado Final del Sistema"
final_status=$(api_request GET "/api/v1/ingestion/status")
final_count=$(echo "$final_status" | jq -r '.total_images_ingested')
increment=$((final_count - initial_count))

success "  ✓ Estado final obtenido"
info "    • Total imágenes: $final_count"
info "    • Incremento: $increment"

# Resumen
step "Resumen de Pruebas"

all_passed=true

tests=(
    "Health Check:$status"
    "Status Endpoint:$initial_count"
    "Primera Ingestión:$ingested"
    "Metadata Endpoint:$metadata_total"
    "Idempotencia:$skipped2"
    "Ingestión Chats:$chat_ingested"
    "Ingestión Estados:$status_ingested"
)

for test in "${tests[@]}"; do
    name="${test%%:*}"
    value="${test##*:}"

    if [ -n "$value" ] && [ "$value" != "null" ]; then
        success "  ✓ $name"
    else
        error "  ✗ $name"
        all_passed=false
    fi
done

echo
if [ "$all_passed" = true ]; then
    success "╔════════════════════════════════════════════╗"
    success "║  ✓ TODAS LAS PRUEBAS PASARON EXITOSAMENTE ║"
    success "╚════════════════════════════════════════════╝"
    exit 0
else
    error "╔════════════════════════════════════╗"
    error "║  ✗ ALGUNAS PRUEBAS FALLARON        ║"
    error "╚════════════════════════════════════╝"
    exit 1
fi

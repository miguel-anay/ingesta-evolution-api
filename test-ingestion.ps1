# Script de Pruebas - Servicio de Ingestión de Imágenes
# Uso: .\test-ingestion.ps1 -NumCelular "51999999999" -Instancia "mi-instancia"

param(
    [Parameter(Mandatory=$false)]
    [string]$NumCelular = "51999999999",

    [Parameter(Mandatory=$false)]
    [string]$Instancia = "mi-instancia",

    [Parameter(Mandatory=$false)]
    [string]$BaseUrl = "http://localhost:3000",

    [Parameter(Mandatory=$false)]
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

# Colores para output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Step { Write-Host "`n===== $args =====" -ForegroundColor Magenta }

# Función para hacer requests HTTP
function Invoke-ApiRequest {
    param(
        [string]$Method = "GET",
        [string]$Endpoint,
        [object]$Body = $null
    )

    $url = "$BaseUrl$Endpoint"

    if ($Verbose) {
        Write-Info "  → $Method $url"
    }

    try {
        $params = @{
            Uri = $url
            Method = $Method
            ContentType = "application/json"
            ErrorAction = "Stop"
        }

        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
        }

        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        Write-Error "  ✗ Error: $($_.Exception.Message)"
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            Write-Error "  Response: $responseBody"
        }
        return $null
    }
}

# Banner
Write-Host @"

╔═══════════════════════════════════════════════════╗
║  Servicio de Ingestión de Imágenes - Test Suite  ║
║              US-ING-001 - Evolution API           ║
╚═══════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Info "Configuración:"
Write-Info "  • Base URL: $BaseUrl"
Write-Info "  • Número Celular: $NumCelular"
Write-Info "  • Instancia: $Instancia"
Write-Info ""

# Test 1: Health Check
Write-Step "Test 1: Health Check"
$health = Invoke-ApiRequest -Endpoint "/api/v1/health"
if ($health -and $health.status -eq "healthy") {
    Write-Success "  ✓ Servicio saludable"
} else {
    Write-Error "  ✗ Servicio no responde correctamente"
    exit 1
}

# Test 2: Ingestion Status (Estado Inicial)
Write-Step "Test 2: Estado de Ingestión Inicial"
$status = Invoke-ApiRequest -Endpoint "/api/v1/ingestion/status"
if ($status) {
    Write-Success "  ✓ Status endpoint responde"
    Write-Info "    • Total imágenes: $($status.total_images_ingested)"
    Write-Info "    • Directorio: $($status.images_directory)"
    Write-Info "    • Archivo metadata: $($status.metadata_file)"
    $initialCount = $status.total_images_ingested
} else {
    Write-Error "  ✗ No se pudo obtener el status"
    exit 1
}

# Test 3: Primera Ingestión
Write-Step "Test 3: Primera Ingestión de Imágenes"
Write-Info "  Ingiriendo imágenes del número '$NumCelular' en instancia '$Instancia'..."

$ingestResult = Invoke-ApiRequest -Method POST -Endpoint "/api/v1/ingestion/ingest" -Body @{
    numero_celular = $NumCelular
    instancia = $Instancia
}

if ($ingestResult) {
    Write-Success "  ✓ Ingestión completada"
    Write-Info "    • Imágenes ingresadas: $($ingestResult.images_ingested)"
    Write-Info "    • Imágenes omitidas: $($ingestResult.images_skipped)"
    Write-Info "    • Total procesadas: $($ingestResult.total_processed)"
    Write-Info "    • Tiempo: $($ingestResult.execution_time_seconds)s"

    $firstIngestionCount = $ingestResult.images_ingested

    if ($ingestResult.images_ingested -eq 0) {
        Write-Warning "  ⚠ No se encontraron imágenes nuevas. Asegúrate de que la instancia tenga mensajes con imágenes."
    }
} else {
    Write-Error "  ✗ Error en la ingestión"
    exit 1
}

# Test 4: Verificar Metadata
Write-Step "Test 4: Verificación de Metadata"
$metadata = Invoke-ApiRequest -Endpoint "/api/v1/ingestion/metadata"
if ($metadata) {
    Write-Success "  ✓ Metadata disponible"
    Write-Info "    • Total registros: $($metadata.total)"

    if ($metadata.metadata -and $metadata.metadata.Count -gt 0) {
        $firstImage = $metadata.metadata[0]
        Write-Info "    • Primera imagen:"
        Write-Info "      - ID: $($firstImage.id_secuencial)"
        Write-Info "      - Origen: $($firstImage.tipo_origen)"
        Write-Info "      - Usuario: $($firstImage.nombre_usuario)"
        Write-Info "      - Teléfono: $($firstImage.numero_telefono)"
    }
} else {
    Write-Error "  ✗ No se pudo obtener metadata"
}

# Test 5: Prueba de Idempotencia
Write-Step "Test 5: Prueba de Idempotencia (Re-ejecución)"
Write-Info "  Ejecutando ingestión nuevamente (no debería descargar duplicados)..."

$ingestResult2 = Invoke-ApiRequest -Method POST -Endpoint "/api/v1/ingestion/ingest" -Body @{
    numero_celular = $NumCelular
    instancia = $Instancia
}

if ($ingestResult2) {
    if ($ingestResult2.images_ingested -eq 0 -and $ingestResult2.images_skipped -gt 0) {
        Write-Success "  ✓ Idempotencia verificada - No se descargaron duplicados"
        Write-Info "    • Imágenes omitidas: $($ingestResult2.images_skipped)"
        Write-Info "    • Tiempo: $($ingestResult2.execution_time_seconds)s (más rápido que la primera vez)"
    } elseif ($ingestResult2.images_ingested -gt 0) {
        Write-Warning "  ⚠ Se ingresaron nuevas imágenes (esto es normal si enviaste más imágenes entre pruebas)"
        Write-Info "    • Nuevas imágenes: $($ingestResult2.images_ingested)"
    } else {
        Write-Warning "  ⚠ Resultado inesperado en prueba de idempotencia"
    }
} else {
    Write-Error "  ✗ Error en segunda ejecución"
}

# Test 6: Ingestión solo de Chats
Write-Step "Test 6: Ingestión Solo de Chats"
$chatResult = Invoke-ApiRequest -Method POST -Endpoint "/api/v1/ingestion/ingest/chat" -Body @{
    numero_celular = $NumCelular
    instancia = $Instancia
    limit = 10
}

if ($chatResult) {
    Write-Success "  ✓ Ingestión de chats completada"
    Write-Info "    • Imágenes de chats: $($chatResult.images_ingested)"
} else {
    Write-Error "  ✗ Error en ingestión de chats"
}

# Test 7: Ingestión solo de Estados
Write-Step "Test 7: Ingestión Solo de Estados (Stories)"
$statusResult = Invoke-ApiRequest -Method POST -Endpoint "/api/v1/ingestion/ingest/status" -Body @{
    numero_celular = $NumCelular
    instancia = $Instancia
}

if ($statusResult) {
    Write-Success "  ✓ Ingestión de estados completada"
    Write-Info "    • Imágenes de estados: $($statusResult.images_ingested)"
} else {
    Write-Error "  ✗ Error en ingestión de estados"
}

# Test 8: Verificar archivos físicos
Write-Step "Test 8: Verificación de Archivos Físicos"

$imagesDir = ".\data\images"
$metadataFile = ".\data\metadata\images.csv"

if (Test-Path $imagesDir) {
    $images = Get-ChildItem $imagesDir -Filter "*.jpg"
    Write-Success "  ✓ Directorio de imágenes existe"
    Write-Info "    • Total archivos .jpg: $($images.Count)"

    if ($images.Count -gt 0) {
        Write-Info "    • Primeros archivos:"
        $images | Select-Object -First 5 | ForEach-Object {
            $sizeKB = [math]::Round($_.Length / 1KB, 2)
            Write-Info "      - $($_.Name) ($sizeKB KB)"
        }
    }
} else {
    Write-Warning "  ⚠ Directorio de imágenes no existe: $imagesDir"
}

if (Test-Path $metadataFile) {
    Write-Success "  ✓ Archivo CSV de metadata existe"
    $csvLines = (Get-Content $metadataFile).Count
    Write-Info "    • Líneas en CSV: $csvLines (incluyendo header)"
    Write-Info "    • Registros: $($csvLines - 1)"

    # Mostrar primeras líneas del CSV
    Write-Info "    • Primeras líneas del CSV:"
    Get-Content $metadataFile -Head 3 | ForEach-Object {
        Write-Info "      $_"
    }
} else {
    Write-Warning "  ⚠ Archivo CSV de metadata no existe: $metadataFile"
}

# Test 9: Estado Final
Write-Step "Test 9: Estado Final del Sistema"
$finalStatus = Invoke-ApiRequest -Endpoint "/api/v1/ingestion/status"
if ($finalStatus) {
    Write-Success "  ✓ Estado final obtenido"
    Write-Info "    • Total imágenes: $($finalStatus.total_images_ingested)"
    Write-Info "    • Incremento: $($finalStatus.total_images_ingested - $initialCount)"
}

# Resumen
Write-Step "Resumen de Pruebas"

$allPassed = $true
$testsResults = @(
    @{ Name = "Health Check"; Passed = $health -ne $null }
    @{ Name = "Status Endpoint"; Passed = $status -ne $null }
    @{ Name = "Primera Ingestión"; Passed = $ingestResult -ne $null }
    @{ Name = "Metadata Endpoint"; Passed = $metadata -ne $null }
    @{ Name = "Idempotencia"; Passed = $ingestResult2 -ne $null }
    @{ Name = "Ingestión Chats"; Passed = $chatResult -ne $null }
    @{ Name = "Ingestión Estados"; Passed = $statusResult -ne $null }
    @{ Name = "Archivos Físicos"; Passed = (Test-Path $imagesDir) -and (Test-Path $metadataFile) }
)

foreach ($test in $testsResults) {
    if ($test.Passed) {
        Write-Success "  ✓ $($test.Name)"
    } else {
        Write-Error "  ✗ $($test.Name)"
        $allPassed = $false
    }
}

Write-Host ""
if ($allPassed) {
    Write-Success "╔════════════════════════════════════════════╗"
    Write-Success "║  ✓ TODAS LAS PRUEBAS PASARON EXITOSAMENTE ║"
    Write-Success "╚════════════════════════════════════════════╝"
    exit 0
} else {
    Write-Error "╔════════════════════════════════════╗"
    Write-Error "║  ✗ ALGUNAS PRUEBAS FALLARON        ║"
    Write-Error "╚════════════════════════════════════╝"
    exit 1
}

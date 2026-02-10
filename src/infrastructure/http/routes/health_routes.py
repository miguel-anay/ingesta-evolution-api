"""
Health Check Routes

Endpoints for service health monitoring.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime


router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    status: str
    checks: dict


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Basic health check endpoint",
)
async def health_check() -> HealthResponse:
    """
    Basic health check.

    Returns 200 if the service is running.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Check if service is ready to handle requests",
)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check for Kubernetes/Docker.

    Verifies that all dependencies are available.
    """
    # TODO: Add actual dependency checks (database, Redis, etc.)
    checks = {
        "database": "ok",
        "evolution_api": "ok",
        "rabbitmq": "ok",
    }

    return ReadinessResponse(
        status="ready",
        checks=checks,
    )


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Simple liveness probe",
)
async def liveness_check() -> dict:
    """
    Liveness probe for Kubernetes.

    Returns 200 if the process is alive.
    """
    return {"status": "alive"}

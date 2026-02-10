"""
Error Handler

Global exception handling for the API.
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ....domain.messaging.exceptions import MessagingDomainError
from ....domain.instances.exceptions import InstanceDomainError
from ...integrations.evolution_api.exceptions import EvolutionApiError


logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers.

    Converts domain and infrastructure exceptions to proper HTTP responses.
    """

    @app.exception_handler(MessagingDomainError)
    async def messaging_domain_error_handler(
        request: Request,
        exc: MessagingDomainError,
    ) -> JSONResponse:
        """Handle messaging domain errors."""
        logger.warning(f"Messaging domain error: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": exc.message,
                "code": exc.code,
                "type": "MessagingDomainError",
            },
        )

    @app.exception_handler(InstanceDomainError)
    async def instance_domain_error_handler(
        request: Request,
        exc: InstanceDomainError,
    ) -> JSONResponse:
        """Handle instance domain errors."""
        logger.warning(f"Instance domain error: {exc.message}")

        # Map specific errors to HTTP status codes
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in exc.message.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "already exists" in exc.message.lower():
            status_code = status.HTTP_409_CONFLICT

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.message,
                "code": exc.code,
                "type": "InstanceDomainError",
            },
        )

    @app.exception_handler(EvolutionApiError)
    async def evolution_api_error_handler(
        request: Request,
        exc: EvolutionApiError,
    ) -> JSONResponse:
        """Handle Evolution API errors."""
        logger.error(f"Evolution API error: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            content={
                "error": exc.message,
                "code": "EVOLUTION_API_ERROR",
                "type": "EvolutionApiError",
                "details": exc.response_body,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        """Handle validation errors."""
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(exc),
                "code": "VALIDATION_ERROR",
                "type": "ValueError",
            },
        )

    @app.exception_handler(Exception)
    async def general_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(f"Unexpected error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "type": type(exc).__name__,
            },
        )

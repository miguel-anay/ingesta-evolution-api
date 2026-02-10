"""
Evolution API HTTP Client

Low-level HTTP client for Evolution API communication.
This is an infrastructure detail - domain and application layers never use this directly.
"""

from typing import Dict, Any, Optional
import logging
import httpx

from .exceptions import (
    EvolutionApiError,
    EvolutionApiConnectionError,
    EvolutionApiAuthenticationError,
    EvolutionApiNotFoundError,
    EvolutionApiRateLimitError,
)


logger = logging.getLogger(__name__)


class EvolutionApiClient:
    """
    HTTP client for Evolution API.

    Handles authentication, request/response formatting, and error handling.
    This is a low-level client used by adapters.

    IMPORTANT: This class is infrastructure code.
    - NEVER import this in domain or application layers
    - Use via adapters that implement ports
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
    ):
        """
        Initialize Evolution API client.

        Args:
            base_url: Base URL of Evolution API (e.g., http://localhost:8080)
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "apikey": self._api_key,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 401:
            raise EvolutionApiAuthenticationError()

        if response.status_code == 404:
            raise EvolutionApiNotFoundError(response.url.path)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise EvolutionApiRateLimitError(
                retry_after=int(retry_after) if retry_after else None
            )

        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text}

            raise EvolutionApiError(
                message=body.get("message", f"API error: {response.status_code}"),
                status_code=response.status_code,
                response_body=body,
            )

        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make GET request to Evolution API.

        Args:
            endpoint: API endpoint (e.g., /instance/list)
            params: Optional query parameters

        Returns:
            API response as dictionary
        """
        client = await self._get_client()
        logger.debug(f"GET {endpoint} params={params}")

        try:
            response = await client.get(endpoint, params=params)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}")
            raise EvolutionApiConnectionError(str(e))

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make POST request to Evolution API.

        Args:
            endpoint: API endpoint
            data: Request body

        Returns:
            API response as dictionary
        """
        client = await self._get_client()
        logger.debug(f"POST {endpoint} data={data}")

        try:
            response = await client.post(endpoint, json=data or {})
            return await self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}")
            raise EvolutionApiConnectionError(str(e))

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make PUT request to Evolution API."""
        client = await self._get_client()
        logger.debug(f"PUT {endpoint} data={data}")

        try:
            response = await client.put(endpoint, json=data or {})
            return await self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}")
            raise EvolutionApiConnectionError(str(e))

    async def delete(
        self,
        endpoint: str,
    ) -> Dict[str, Any]:
        """Make DELETE request to Evolution API."""
        client = await self._get_client()
        logger.debug(f"DELETE {endpoint}")

        try:
            response = await client.delete(endpoint)
            return await self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}")
            raise EvolutionApiConnectionError(str(e))

    # Convenience methods for common endpoints

    async def send_text(
        self,
        instance_name: str,
        number: str,
        text: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send text message via Evolution API."""
        endpoint = f"/message/sendText/{instance_name}"
        payload = {
            "number": number,
            "text": text,
            "options": options or {},
        }
        return await self.post(endpoint, payload)

    async def send_media(
        self,
        instance_name: str,
        number: str,
        media_type: str,
        media_url: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send media message via Evolution API."""
        endpoint = f"/message/sendMedia/{instance_name}"
        payload = {
            "number": number,
            "mediatype": media_type,
            "media": media_url,
            "caption": caption or "",
            "fileName": filename,
        }
        return await self.post(endpoint, payload)

    async def get_instance_status(self, instance_name: str) -> Dict[str, Any]:
        """Get instance connection status."""
        endpoint = f"/instance/connectionState/{instance_name}"
        return await self.get(endpoint)

    async def create_instance(
        self,
        instance_name: str,
        webhook_url: Optional[str] = None,
        events: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Create a new instance."""
        endpoint = "/instance/create"
        payload = {
            "instanceName": instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "events": events or [
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "CONNECTION_UPDATE",
                    "QRCODE_UPDATED",
                ],
            }
        return await self.post(endpoint, payload)

    async def connect_instance(self, instance_name: str) -> Dict[str, Any]:
        """Get QR code for instance connection."""
        endpoint = f"/instance/connect/{instance_name}"
        return await self.get(endpoint)

    async def list_instances(self) -> Dict[str, Any]:
        """List all instances."""
        endpoint = "/instance/fetchInstances"
        return await self.get(endpoint)

    async def delete_instance(self, instance_name: str) -> Dict[str, Any]:
        """Delete an instance."""
        endpoint = f"/instance/delete/{instance_name}"
        return await self.delete(endpoint)

    async def logout_instance(self, instance_name: str) -> Dict[str, Any]:
        """Logout/disconnect an instance."""
        endpoint = f"/instance/logout/{instance_name}"
        return await self.delete(endpoint)

    async def check_is_whatsapp(
        self,
        instance_name: str,
        numbers: list,
    ) -> Dict[str, Any]:
        """Check if numbers have WhatsApp."""
        endpoint = f"/chat/whatsappNumbers/{instance_name}"
        return await self.post(endpoint, {"numbers": numbers})

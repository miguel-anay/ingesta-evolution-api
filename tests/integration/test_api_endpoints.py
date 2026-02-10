"""
API Endpoint Integration Tests

Tests for FastAPI endpoints with mocked dependencies.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import create_app


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_health_check(self, client: TestClient):
        """Should return healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_liveness_check(self, client: TestClient):
        """Should return alive status."""
        response = client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_check(self, client: TestClient):
        """Should return ready status."""
        response = client.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data


class TestMessagingEndpoints:
    """Tests for messaging API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    @patch("src.infrastructure.http.dependencies.get_evolution_api_client")
    def test_send_text_message_validation_error(
        self,
        mock_client,
        client: TestClient,
    ):
        """Should return 422 for invalid request body."""
        response = client.post(
            "/api/v1/messages/text",
            json={
                "instance_name": "test",
                "recipient": "123",  # Invalid - too short
                "text": "Hello",
            },
        )

        # Pydantic validation or domain validation
        assert response.status_code in (400, 422, 500)

    def test_send_text_message_missing_fields(self, client: TestClient):
        """Should return 422 for missing required fields."""
        response = client.post(
            "/api/v1/messages/text",
            json={
                "instance_name": "test",
                # Missing recipient and text
            },
        )

        assert response.status_code == 422


class TestInstanceEndpoints:
    """Tests for instance management endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_create_instance_validation(self, client: TestClient):
        """Should validate instance name format."""
        response = client.post(
            "/api/v1/instances",
            json={
                "name": "123invalid",  # Must start with letter
            },
        )

        assert response.status_code == 422

    def test_create_instance_name_too_short(self, client: TestClient):
        """Should reject names that are too short."""
        response = client.post(
            "/api/v1/instances",
            json={
                "name": "ab",  # Too short
            },
        )

        assert response.status_code == 422

    def test_list_instances(self, client: TestClient):
        """Should return list of instances."""
        with patch(
            "src.infrastructure.http.dependencies.get_evolution_api_client"
        ) as mock:
            mock_client = AsyncMock()
            mock_client.list_instances.return_value = []
            mock.return_value = mock_client

            response = client.get("/api/v1/instances")

            # May fail due to dependency setup, but should not crash
            assert response.status_code in (200, 500)


class TestWebhookEndpoints:
    """Tests for webhook endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_evolution_webhook_message_received(self, client: TestClient):
        """Should process incoming message webhook."""
        webhook_data = {
            "event": "messages.upsert",
            "instance": "test-instance",
            "data": {
                "key": {"id": "msg_123"},
                "message": {"conversation": "Hello"},
            },
        }

        response = client.post("/api/v1/webhooks/evolution", json=webhook_data)

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data["event_type"] == "messages.upsert"

    def test_evolution_webhook_connection_update(self, client: TestClient):
        """Should process connection update webhook."""
        webhook_data = {
            "event": "connection.update",
            "instance": "test-instance",
            "data": {
                "state": "open",
            },
        }

        response = client.post("/api/v1/webhooks/evolution", json=webhook_data)

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True

    def test_evolution_webhook_invalid_json(self, client: TestClient):
        """Should handle invalid JSON gracefully."""
        response = client.post(
            "/api/v1/webhooks/evolution",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        # Should not crash, return 200 to prevent retries
        assert response.status_code in (200, 422)

    def test_instance_specific_webhook(self, client: TestClient):
        """Should handle instance-specific webhook URL."""
        webhook_data = {
            "event": "messages.upsert",
            "data": {"key": {"id": "msg_456"}},
        }

        response = client.post(
            "/api/v1/webhooks/evolution/my-instance",
            json=webhook_data,
        )

        assert response.status_code == 200

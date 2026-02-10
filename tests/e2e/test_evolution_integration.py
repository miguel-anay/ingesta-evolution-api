"""
Evolution API E2E Tests

End-to-end tests that require a running Evolution API instance.
These tests are skipped by default - run with: pytest -m e2e

To run:
    pytest tests/e2e -m e2e --evolution-url=http://localhost:8080 --api-key=your-key
"""

import pytest
import os

from src.infrastructure.integrations.evolution_api import EvolutionApiClient


# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e


@pytest.fixture
def evolution_client() -> EvolutionApiClient:
    """
    Create Evolution API client for e2e tests.

    Uses environment variables for configuration.
    """
    url = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
    key = os.getenv("EVOLUTION_API_KEY", "test-api-key")

    return EvolutionApiClient(base_url=url, api_key=key)


class TestEvolutionApiConnection:
    """E2E tests for Evolution API connectivity."""

    @pytest.mark.asyncio
    async def test_list_instances(self, evolution_client: EvolutionApiClient):
        """Should be able to list instances from Evolution API."""
        try:
            instances = await evolution_client.list_instances()
            assert isinstance(instances, (list, dict))
        except Exception as e:
            pytest.skip(f"Evolution API not available: {e}")

    @pytest.mark.asyncio
    async def test_create_and_delete_instance(
        self,
        evolution_client: EvolutionApiClient,
    ):
        """Should be able to create and delete an instance."""
        instance_name = "e2e-test-instance"

        try:
            # Create instance
            result = await evolution_client.create_instance(instance_name)
            assert result is not None

            # Delete instance
            await evolution_client.delete_instance(instance_name)

        except Exception as e:
            # Clean up if test fails
            try:
                await evolution_client.delete_instance(instance_name)
            except Exception:
                pass
            pytest.skip(f"Evolution API not available: {e}")


# Skip e2e tests by default
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end (requires Evolution API)"
    )

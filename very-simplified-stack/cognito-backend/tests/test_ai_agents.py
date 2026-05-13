import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

# Since the app is in a different directory, we need to adjust the path
# to import it correctly for testing.
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

@pytest.mark.asyncio
@patch('app.services.backend_router.BackendRouter.generate', new_callable=AsyncMock)
async def test_run_ai_agent_success(mock_generate):
    """
    Tests the successful execution of the /api/agent endpoint.
    """
    # Configure the mock to return a successful response
    mock_generate.return_value = {
        "response": "This is a test response from the mock.",
        "model": "mock-model",
        "backend": "mock-backend",
        "attempt": 1
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Define the request payload
        payload = {
            "prompt": "Hello, AI!",
            "session_id": "test-session-123"
        }

        # Make the request to the endpoint
        response = await client.post("/api/agent", json=payload)

    # Assertions
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["response"] == "This is a test response from the mock."
    assert "metadata" in response_data
    assert "duration_ms" in response_data["metadata"]
    assert response_data["metadata"]["duration_ms"] > 0
    assert response_data["metadata"]["model_used"] == "mock-model"

    # Verify that the mock was called correctly
    mock_generate.assert_called_once_with(
        prompt="Hello, AI!",
        model_params=None
    )

@pytest.mark.asyncio
@patch('app.services.backend_router.BackendRouter.generate', new_callable=AsyncMock)
async def test_run_ai_agent_ollama_error(mock_generate):
    """
    Tests how the endpoint handles an error from the Ollama client.
    """
    # Configure the mock to raise an exception
    mock_generate.side_effect = Exception("Ollama service is down")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "prompt": "This will fail.",
        }
        response = await client.post("/api/agent", json=payload)

    # Assertions for error handling
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"] == "An unexpected error occurred while processing the AI request."

@pytest.mark.asyncio
async def test_health_check():
    """
    Tests the /health endpoint.
    """
    # Mock the BackendRouter health check
    with patch('app.services.backend_router.BackendRouter.health_all', new_callable=AsyncMock) as mock_health_all:
        mock_health_all.return_value = {"mock-backend": "ok"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "ok"
    assert "backends" in response_data
    assert response_data["backends"]["mock-backend"] == "ok"

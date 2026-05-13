import httpx
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class OllamaClient:
    """
    A production-ready client for interacting with the Ollama API.
    """

    def __init__(self, timeout: int = 30):
        """
        Initializes the OllamaClient.

        Args:
            timeout (int): The timeout for HTTP requests in seconds.
        """
        self.api_url = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434/api/generate")
        self.model_name = os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def generate(self, prompt: str, model_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends a prompt to the Ollama API and returns the generated response.

        Args:
            prompt (str): The prompt to send to the model.
            model_params (Optional[Dict[str, Any]]): Optional parameters to override default model settings.

        Returns:
            Dict[str, Any]: The JSON response from the Ollama API.

        Raises:
            httpx.HTTPStatusError: If the API returns an unsuccessful status code.
            httpx.RequestError: If a network-related error occurs.
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        if model_params:
            payload.update(model_params)

        logger.info(f"Sending request to Ollama API at {self.api_url} with model {self.model_name}")
        try:
            response = await self._client.post(self.api_url, json=payload)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            logger.info("Successfully received response from Ollama API.")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error occurred while requesting Ollama API: {e}")
            raise

    async def check_health(self) -> str:
        """
        Checks the health of the Ollama service.

        Returns:
            str: "ok" if the service is healthy, "error" otherwise.
        """
        health_check_url = self.api_url.replace("/api/generate", "")
        try:
            response = await self._client.get(health_check_url, timeout=5)
            return "ok" if response.status_code == 200 else "error"
        except httpx.RequestError:
            return "error"

# Singleton instance of the client
ollama_client = OllamaClient()

import time
import logging
from app.services.ollama_client import ollama_client, OllamaClient
from app.models.ai import AIRequest, AIResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReasoningEngine:
    """
    Orchestrates the AI reasoning process, including timing and interaction with the Ollama client.
    """

    def __init__(self, client: OllamaClient):
        """
        Initializes the ReasoningEngine.

        Args:
            client (OllamaClient): An instance of the Ollama client.
        """
        self.client = client

    async def process_request(self, request: AIRequest) -> AIResponse:
        """
        Processes an AI request, times the operation, and returns a structured response.

        Args:
            request (AIRequest): The request object containing the prompt and other parameters.

        Returns:
            AIResponse: The response object containing the AI-generated text and performance metrics.
        """
        start_time = time.perf_counter()
        logger.info(f"Processing request for session: {request.session_id or 'N/A'}")

        try:
            # Call the Ollama client to get the AI response
            ollama_response = await self.client.generate(
                prompt=request.prompt,
                model_params=request.model_params
            )

            # Extract the response text
            response_text = ollama_response.get("response", "Error: No response field found.")
            model_used = ollama_response.get("model", self.client.model_name)

        except Exception as e:
            logger.error(f"An error occurred during AI processing: {e}")
            response_text = "An internal error occurred."
            model_used = self.client.model_name

        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        logger.info(f"Request processed in {duration_ms:.2f} ms")

        return AIResponse(
            response=response_text,
            duration_ms=duration_ms,
            model_used=model_used
        )

# Singleton instance of the ReasoningEngine
reasoning_engine = ReasoningEngine(client=ollama_client)

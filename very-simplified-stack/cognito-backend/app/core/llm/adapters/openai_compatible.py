import json
import logging
from typing import AsyncIterator, Dict, Any, List, Optional
import httpx

from app.core.llm.adapters.base import (
    LLMAdapter,
    LLMRetryableError,
    LLMNonRetryableError,
    is_retryable_http_status,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(LLMAdapter):
    """
    Adapter for OpenAI-compatible APIs (OpenAI, DeepSeek, OpenRouter, vLLM, etc.).
    Supports standard /v1/chat/completions style endpoints.
    """

    def _get_endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    async def _do_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = self._get_endpoint()
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Merge extra kwargs
        for k, v in kwargs.items():
            if k not in payload and v is not None:
                payload[k] = v

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code >= 400:
                    error_msg = f"OpenAI-Compatible HTTP {response.status_code}: {response.text}"
                    if is_retryable_http_status(response.status_code):
                        raise LLMRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)
                    else:
                        raise LLMNonRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)

                return response.json()
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"OpenAI-Compatible request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"OpenAI-Compatible connection error: {str(e)}") from e

    async def _do_stream_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = self._get_endpoint()
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        for k, v in kwargs.items():
            if k not in payload and v is not None:
                payload[k] = v

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        text = body.decode("utf-8", errors="replace")
                        error_msg = f"OpenAI-Compatible HTTP {response.status_code}: {text}"
                        if is_retryable_http_status(response.status_code):
                            raise LLMRetryableError(error_msg, status_code=response.status_code, raw_response=text)
                        else:
                            raise LLMNonRetryableError(error_msg, status_code=response.status_code, raw_response=text)

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[len("data: "):].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"OpenAI-Compatible stream request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"OpenAI-Compatible stream connection error: {str(e)}") from e

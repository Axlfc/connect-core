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


class OllamaAdapter(LLMAdapter):
    """
    Adapter for Ollama local/remote LLM instances using Ollama native REST API (/api/chat).
    """

    def _get_endpoint(self) -> str:
        if self.base_url.endswith("/api/chat"):
            return self.base_url
        return f"{self.base_url}/api/chat"

    async def _do_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = self._get_endpoint()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code >= 400:
                    error_msg = f"Ollama HTTP {response.status_code}: {response.text}"
                    if is_retryable_http_status(response.status_code):
                        raise LLMRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)
                    else:
                        raise LLMNonRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)

                data = response.json()
                msg = data.get("message", {})
                content = msg.get("content", "")

                return {
                    "id": f"ollama-{data.get('created_at', '')}",
                    "model": self.model_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": msg.get("role", "assistant"),
                                "content": content,
                            },
                            "finish_reason": "stop" if data.get("done") else None,
                        }
                    ],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                    },
                    "raw": data,
                }
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"Ollama request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"Ollama network connection error: {str(e)}") from e

    async def _do_stream_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = self._get_endpoint()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        text = body.decode("utf-8", errors="replace")
                        error_msg = f"Ollama HTTP {response.status_code}: {text}"
                        if is_retryable_http_status(response.status_code):
                            raise LLMRetryableError(error_msg, status_code=response.status_code, raw_response=text)
                        else:
                            raise LLMNonRetryableError(error_msg, status_code=response.status_code, raw_response=text)

                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            yield {
                                "model": self.model_name,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": msg.get("role", "assistant"),
                                            "content": msg.get("content", ""),
                                        },
                                        "finish_reason": "stop" if chunk.get("done") else None,
                                    }
                                ],
                                "done": chunk.get("done", False),
                            }
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"Ollama stream request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"Ollama stream connection error: {str(e)}") from e

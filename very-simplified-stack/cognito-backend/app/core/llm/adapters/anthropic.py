import json
import logging
from typing import AsyncIterator, Dict, Any, List, Optional
import httpx

from app.core.llm.adapters.base import (
    LLMAdapter,
    LLMRetryableError,
    LLMNonRetryableError,
    is_retryable_http_status,
    register_provider,
)

logger = logging.getLogger(__name__)


@register_provider("anthropic", "claude")
class AnthropicAdapter(LLMAdapter):
    """
    Adapter for Anthropic LLM API (Claude models using /v1/messages).
    """

    def _get_endpoint(self) -> str:
        if self.base_url.endswith("/v1/messages"):
            return self.base_url
        return f"{self.base_url}/v1/messages"

    def _format_messages_for_anthropic(self, messages: List[Dict[str, Any]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Extracts system prompt if present and converts messages to Anthropic format.
        """
        system_prompt: Optional[str] = None
        formatted_messages: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            else:
                formatted_messages.append({"role": role, "content": content})

        return system_prompt, formatted_messages

    async def _do_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        url = self._get_endpoint()
        system_prompt, formatted_messages = self._format_messages_for_anthropic(messages)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "max_tokens": max_tokens if max_tokens is not None else 1024,
            "temperature": temperature,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code >= 400:
                    error_msg = f"Anthropic HTTP {response.status_code}: {response.text}"
                    if is_retryable_http_status(response.status_code):
                        raise LLMRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)
                    else:
                        raise LLMNonRetryableError(error_msg, status_code=response.status_code, raw_response=response.text)

                data = response.json()
                content_blocks = data.get("content", [])
                text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

                return {
                    "id": data.get("id", f"anthropic-{data.get('type', '')}"),
                    "model": data.get("model", self.model_name),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": data.get("role", "assistant"),
                                "content": text,
                            },
                            "finish_reason": data.get("stop_reason", "end_turn"),
                        }
                    ],
                    "usage": {
                        "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                        "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                        "total_tokens": (
                            data.get("usage", {}).get("input_tokens", 0) +
                            data.get("usage", {}).get("output_tokens", 0)
                        ),
                    },
                    "raw": data,
                }
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"Anthropic request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"Anthropic connection error: {str(e)}") from e

    async def _do_stream_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = self._get_endpoint()
        system_prompt, formatted_messages = self._format_messages_for_anthropic(messages)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_messages,
            "max_tokens": max_tokens if max_tokens is not None else 1024,
            "temperature": temperature,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        text = body.decode("utf-8", errors="replace")
                        error_msg = f"Anthropic HTTP {response.status_code}: {text}"
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
                            try:
                                chunk = json.loads(data_str)
                                event_type = chunk.get("type")
                                if event_type == "content_block_delta":
                                    delta = chunk.get("delta", {})
                                    yield {
                                        "model": self.model_name,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {
                                                    "role": "assistant",
                                                    "content": delta.get("text", ""),
                                                },
                                                "finish_reason": None,
                                            }
                                        ],
                                        "done": False,
                                    }
                                elif event_type == "message_stop":
                                    yield {
                                        "model": self.model_name,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {"role": "assistant", "content": ""},
                                                "finish_reason": "stop",
                                            }
                                        ],
                                        "done": True,
                                    }
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            raise LLMRetryableError(f"Anthropic stream request timeout: {str(e)}") from e
        except httpx.RequestError as e:
            raise LLMRetryableError(f"Anthropic stream connection error: {str(e)}") from e

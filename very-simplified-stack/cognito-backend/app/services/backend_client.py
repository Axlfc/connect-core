"""
backend_client.py

A unified async client that can talk to:
  - Ollama native API  (POST /api/generate)
  - OpenAI-compatible  (POST /v1/chat/completions)

Supports both blocking and streaming responses.
The caller never needs to know which protocol is being used.
"""

import httpx
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from app.services.backend_registry import BackendConfig, BackendType

logger = logging.getLogger(__name__)


class BackendClient:
    """
    Thin async wrapper around a single BackendConfig.
    Instantiate one per backend, or use BackendRouter which manages the pool.
    """

    def __init__(self, config: BackendConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout,
            headers=config.extra_headers,
        )

    # ── Public interface ───────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send *prompt* to this backend and return a normalised dict:
            {
                "response": str,
                "model":    str,
                "backend":  str,
            }
        Raises httpx.HTTPStatusError / httpx.RequestError on failure.
        """
        if self.config.backend_type == BackendType.OLLAMA:
            return await self._call_ollama(prompt, model_params)
        else:
            return await self._call_openai(prompt, model_params)

    async def generate_stream(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream tokens from this backend.
        Yields dicts with "token" and optionally "logprobs".
        The caller (openai_compat) wraps each chunk in SSE format.
        """
        if self.config.backend_type == BackendType.OLLAMA:
            async for chunk in self._stream_ollama(prompt, model_params):
                yield chunk
        else:
            async for chunk in self._stream_openai(prompt, model_params):
                yield chunk

    async def check_health(self) -> bool:
        """
        Returns True if the backend is reachable.
        """
        try:
            if self.config.backend_type == BackendType.OLLAMA:
                url = self.config.base_url
            else:
                url = f"{self.config.base_url}/v1/models"

            resp = await self._client.get(url, timeout=self.config.health_timeout)
            return resp.status_code < 500
        except httpx.RequestError:
            return False

    # ── Blocking helpers ───────────────────────────────────────────────────────

    async def _call_ollama(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        url = f"{self.config.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }
        if model_params:
            payload.update(model_params)

        logger.info("[%s] POST %s (ollama)", self.config.name, url)
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        return {
            "response": data.get("response", ""),
            "model": data.get("model", self.config.model),
            "backend": self.config.name,
        }

    async def _call_openai(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        url = f"{self.config.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if model_params:
            _ollama_only = {"prompt", "stream"}
            safe_params = {k: v for k, v in model_params.items() if k not in _ollama_only}
            payload.update(safe_params)

        logger.info("[%s] POST %s (openai-compat)", self.config.name, url)
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            text = ""

        return {
            "response": text,
            "model": data.get("model", self.config.model),
            "backend": self.config.name,
        }

    # ── Streaming helpers ──────────────────────────────────────────────────────

    async def _stream_ollama(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Ollama streaming: POST /api/generate with stream=true.
        Each line is a JSON object: {"response": "token", "done": false}
        Last line: {"done": true, ...}
        """
        url = f"{self.config.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,
            "logprobs": True,
            "top_logprobs": 5,
        }
        if model_params:
            # Don't override stream, but we allow overriding logprobs if explicitly passed
            payload.update({k: v for k, v in model_params.items() if k != "stream"})

        logger.info("[%s] STREAM %s (ollama)", self.config.name, url)

        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                token = data.get("response", "")
                logprobs = data.get("logprobs")

                if token or logprobs:
                    yield {"token": token, "logprobs": logprobs}

                if data.get("done", False):
                    break

    async def _stream_openai(
        self,
        prompt: str,
        model_params: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        OpenAI-compat streaming: POST /v1/chat/completions with stream=true.
        Each line: data: {"choices":[{"delta":{"content":"token"}}]}
        Last line: data: [DONE]
        """
        url = f"{self.config.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if model_params:
            _skip = {"prompt", "stream"}
            payload.update({k: v for k, v in model_params.items() if k not in _skip})

        logger.info("[%s] STREAM %s (openai-compat)", self.config.name, url)

        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                # Strip the "data: " SSE prefix
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                try:
                    choice = data["choices"][0]
                    token = choice["delta"].get("content", "")
                    logprobs = choice.get("logprobs")
                except (KeyError, IndexError):
                    token = ""
                    logprobs = None

                if token or logprobs:
                    yield {"token": token, "logprobs": logprobs}

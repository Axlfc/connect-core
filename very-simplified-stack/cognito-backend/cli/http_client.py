import json
import httpx
import logging
from typing import AsyncIterator, Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class CognitoClient:
    def __init__(self, endpoint: str, timeout: float = 120.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=timeout, read=timeout)
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def agent_loop(
        self,
        messages: List[Dict[str, Any]],
        cwd: str,
        session_id: Optional[str] = None,
        model_params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = f"{self.endpoint}/api/agent/loop"
        payload = {
            "messages": messages,
            "cwd": cwd,
            "session_id": session_id,
            "model_params": model_params
        }

        async with self._client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                # Handle non-200 responses as errors
                try:
                    error_data = await response.aread()
                    detail = json.loads(error_data).get("detail", str(error_data))
                except:
                    detail = response.reason_phrase
                raise RuntimeError(f"Server returned {response.status_code}: {detail}")

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SSE data: {data_str}")

    async def list_sessions(self, cwd: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"cwd": cwd} if cwd else {}
        resp = await self._client.get(f"{self.endpoint}/api/agent/sessions", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_session(self, session_id: str) -> Dict[str, Any]:
        resp = await self._client.get(f"{self.endpoint}/api/agent/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def fork_session(self, session_id: str, turn: Optional[int] = None) -> str:
        payload = {"turn": turn} if turn is not None else {}
        resp = await self._client.post(f"{self.endpoint}/api/agent/sessions/{session_id}/fork", json=payload)
        resp.raise_for_status()
        return resp.json()["session_id"]

    async def health(self) -> Dict[str, Any]:
        resp = await self._client.get(f"{self.endpoint}/health")
        resp.raise_for_status()
        return resp.json()

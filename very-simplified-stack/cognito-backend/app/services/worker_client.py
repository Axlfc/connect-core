import httpx
import hashlib
import hmac
import time
import os
import json
import logging
from typing import Dict, Any, Optional, List

from app.core.retry import retry_transient_async

logger = logging.getLogger("cognito.backend.worker_client")


class WorkerUnreachableError(Exception):
    """Raised when the worker service cannot be reached after transient retries."""
    pass


def calculate_signature(secret: str, method: str, path: str, timestamp: str, nonce: str, body_sha256: str, worker_id: str) -> str:
    canonical = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_sha256}\n{worker_id}"
    h = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256)
    return h.hexdigest()


class WorkerClient:
    def __init__(self):
        self.worker_url = os.getenv("COGNITO_WORKER_URL", "http://host.docker.internal:8765")
        self.worker_id = os.getenv("COGNITO_WORKER_ID", "local-worker-01")
        self.secret = os.getenv("COGNITO_WORKER_SECRET", "")

    def _get_headers(self, method: str, path: str, body: bytes = b"") -> Dict[str, str]:
        timestamp = str(time.time())
        nonce = f"nonce-cp-{time.time()}"
        body_sha256 = hashlib.sha256(body).hexdigest()

        sig = calculate_signature(
            self.secret, method, path, timestamp, nonce, body_sha256, self.worker_id
        )

        return {
            "X-Cognito-Worker-Id": self.worker_id,
            "X-Cognito-Timestamp": timestamp,
            "X-Cognito-Nonce": nonce,
            "X-Cognito-Body-SHA256": body_sha256,
            "X-Cognito-Signature": sig,
            "Content-Type": "application/json"
        }

    async def get_health(self) -> Dict[str, Any]:
        url = f"{self.worker_url}/v1/health"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch worker health: {e}")
        return {"status": "unreachable"}

    async def get_models(self) -> List[Dict[str, Any]]:
        path = "/v1/models"
        url = f"{self.worker_url}{path}"
        try:
            headers = self._get_headers("GET", path)
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json().get("models", [])
        except Exception as e:
            logger.warning(f"Failed to fetch worker models: {e}")
        return []

    async def start_task(self, payload: Dict[str, Any]) -> Any:
        path = "/v1/task"
        url = f"{self.worker_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")
        headers = self._get_headers("POST", path, body_bytes)

        # We can return the client or an async generator to stream SSE events
        # Standard httpx.AsyncClient supports streaming
        client = httpx.AsyncClient(timeout=120.0)
        req = client.build_request("POST", url, headers=headers, content=body_bytes)
        resp = await client.send(req, stream=True)
        return resp

    async def verify_task(
        self,
        payload: Dict[str, Any],
        max_attempts: int = 3,
        min_wait: float = 0.5,
        max_wait: float = 4.0,
    ) -> Dict[str, Any]:
        path = "/v1/verify"
        url = f"{self.worker_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")

        async def _do_verify():
            headers = self._get_headers("POST", path, body_bytes)
            async with httpx.AsyncClient(timeout=65.0) as client:
                resp = await client.post(url, headers=headers, content=body_bytes)
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_transient_async(
                _do_verify,
                max_attempts=max_attempts,
                min_wait=min_wait,
                max_wait=max_wait,
            )
        except Exception as e:
            logger.error(f"Worker verification call failed: {e}")
            raise WorkerUnreachableError(f"Worker verification failed: {e}") from e

    async def cleanup_task(
        self,
        payload: Dict[str, Any],
        max_attempts: int = 3,
        min_wait: float = 0.5,
        max_wait: float = 4.0,
    ) -> Dict[str, Any]:
        path = "/v1/cleanup"
        url = f"{self.worker_url}{path}"
        body_bytes = json.dumps(payload).encode("utf-8")

        async def _do_cleanup():
            headers = self._get_headers("POST", path, body_bytes)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, content=body_bytes)
                resp.raise_for_status()
                return resp.json()

        try:
            return await retry_transient_async(
                _do_cleanup,
                max_attempts=max_attempts,
                min_wait=min_wait,
                max_wait=max_wait,
            )
        except Exception as e:
            logger.error(f"Worker cleanup call failed: {e}")
            raise WorkerUnreachableError(f"Worker cleanup failed: {e}") from e


worker_client = WorkerClient()

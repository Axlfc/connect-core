import pytest
import httpx
from unittest.mock import patch, AsyncMock
from app.services.worker_client import WorkerClient, WorkerUnreachableError


@pytest.mark.asyncio
async def test_worker_client_verify_transient_retry_success():
    client = WorkerClient()
    payload = {"task_id": "t1"}

    attempts = 0

    async def mock_post(url, headers=None, content=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectTimeout("Timeout connecting to worker")
        if attempts == 2:
            res_500 = httpx.Response(500, request=httpx.Request("POST", url))
            raise httpx.HTTPStatusError("500 Server Error", request=res_500.request, response=res_500)

        # 3rd attempt succeeds
        res_200 = httpx.Response(200, json={"exit_status": 0, "stdout": "ok"}, request=httpx.Request("POST", url))
        return res_200

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await client.verify_task(payload, max_attempts=3, min_wait=0.01, max_wait=0.05)

    assert attempts == 3
    assert res == {"exit_status": 0, "stdout": "ok"}


@pytest.mark.asyncio
async def test_worker_client_verify_persistent_failure_raises_unreachable_error():
    client = WorkerClient()
    payload = {"task_id": "t1"}

    attempts = 0

    async def mock_post(url, headers=None, content=None):
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectTimeout("Worker unreachable")

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(WorkerUnreachableError) as exc_info:
            await client.verify_task(payload, max_attempts=3, min_wait=0.01, max_wait=0.05)

    assert attempts == 3
    assert "Worker verification failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_worker_client_cleanup_transient_retry_success():
    client = WorkerClient()
    payload = {"task_id": "t1"}

    attempts = 0

    async def mock_post(url, headers=None, content=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            res_503 = httpx.Response(503, request=httpx.Request("POST", url))
            raise httpx.HTTPStatusError("503 Service Unavailable", request=res_503.request, response=res_503)

        res_200 = httpx.Response(200, json={"status": "cleaned"}, request=httpx.Request("POST", url))
        return res_200

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await client.cleanup_task(payload, max_attempts=3, min_wait=0.01, max_wait=0.05)

    assert attempts == 2
    assert res == {"status": "cleaned"}


@pytest.mark.asyncio
async def test_worker_client_cleanup_persistent_failure_raises_unreachable_error():
    client = WorkerClient()
    payload = {"task_id": "t1"}

    attempts = 0

    async def mock_post(url, headers=None, content=None):
        nonlocal attempts
        attempts += 1
        res_502 = httpx.Response(502, request=httpx.Request("POST", url))
        raise httpx.HTTPStatusError("502 Bad Gateway", request=res_502.request, response=res_502)

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(WorkerUnreachableError) as exc_info:
            await client.cleanup_task(payload, max_attempts=3, min_wait=0.01, max_wait=0.05)

    assert attempts == 3
    assert "Worker cleanup failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_worker_task_execution_failure_returns_payload_not_unreachable_error():
    """
    When the worker is reachable (HTTP 200) but reports that the verification task failed (non-zero exit status),
    it must return the response payload rather than raising WorkerUnreachableError.
    """
    client = WorkerClient()
    payload = {"task_id": "t1"}

    async def mock_post(url, headers=None, content=None):
        return httpx.Response(200, json={"exit_status": 1, "stdout": "", "stderr": "AssertionError: 1 != 2"}, request=httpx.Request("POST", url))

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        res = await client.verify_task(payload, max_attempts=3, min_wait=0.01, max_wait=0.05)

    assert res["exit_status"] == 1
    assert "AssertionError" in res["stderr"]

import os
import pytest
import httpx
from pathlib import Path

from app.core.retry import (
    retry_transient_async,
    generate_idempotency_key,
    clear_idempotency_store,
    get_idempotency_store,
    record_idempotency_result,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_idempotency_store()
    yield
    clear_idempotency_store()


def test_generate_idempotency_key():
    key1 = generate_idempotency_key("test")
    key2 = generate_idempotency_key("test")
    assert key1.startswith("test-")
    assert key2.startswith("test-")
    assert key1 != key2


@pytest.mark.asyncio
async def test_retry_transient_async_file_write_idempotency_network_failure(tmp_path: Path):
    """
    Acceptance Criteria Test:
    Simulates a network failure occurring AFTER a file write operation has already taken effect.
    Triggers retry and confirms that the file is not written twice or corrupted with duplicate content.
    """
    target_file = tmp_path / "output.txt"
    attempts = 0
    write_count = 0
    idem_key = generate_idempotency_key("write-file")

    async def _write_file_with_network_drop():
        nonlocal attempts, write_count
        attempts += 1

        # Simulate non-idempotent side effect: write/append content to file
        with open(target_file, "a") as f:
            f.write("IMPORTANT DATA\n")
        write_count += 1

        result = {"status": "success", "bytes_written": 15}
        # Record effect under idempotency key before network response drop occurs
        record_idempotency_result(idem_key, result)

        # Simulate network drop / timeout AFTER the side effect has taken place on attempt 1
        if attempts == 1:
            res_502 = httpx.Response(502, request=httpx.Request("POST", "http://worker/write"))
            raise httpx.HTTPStatusError("502 Bad Gateway", request=res_502.request, response=res_502)

        return result

    res = await retry_transient_async(
        _write_file_with_network_drop,
        max_attempts=3,
        min_wait=0.01,
        max_wait=0.05,
        idempotency_key=idem_key,
        is_destructive=True,
        is_read_only=False,
    )

    # Retry should have recovered from recorded result
    assert res == {"status": "success", "bytes_written": 15}

    # Verify that file write side-effect occurred exactly ONCE, avoiding duplicate/corrupted data
    assert target_file.exists()
    content = target_file.read_text()
    assert content == "IMPORTANT DATA\n"
    assert write_count == 1
    assert attempts == 1  # 2nd attempt was skipped via idempotency store check


@pytest.mark.asyncio
async def test_retry_transient_async_custom_persisted_idempotency_check(tmp_path: Path):
    """
    Tests custom idempotency_check verifying persisted record (e.g., file already exists on disk).
    """
    target_file = tmp_path / "persisted.txt"
    attempts = 0

    def file_exists_check(key: str):
        if target_file.exists():
            return {"status": "already_exists", "content": target_file.read_text()}
        return None

    async def _do_side_effect():
        nonlocal attempts
        attempts += 1
        target_file.write_text("PERSISTED CONTENT")
        if attempts == 1:
            raise httpx.ConnectTimeout("Connection timed out after write")
        return {"status": "written", "content": "PERSISTED CONTENT"}

    res = await retry_transient_async(
        _do_side_effect,
        max_attempts=3,
        min_wait=0.01,
        max_wait=0.05,
        idempotency_key="key-persisted-123",
        is_destructive=False,
        is_read_only=False,
        idempotency_check=file_exists_check,
    )

    assert res["content"] == "PERSISTED CONTENT"
    assert attempts == 1  # Re-execution skipped due to custom idempotency check
    assert target_file.read_text() == "PERSISTED CONTENT"

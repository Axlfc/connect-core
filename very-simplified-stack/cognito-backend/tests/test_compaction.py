import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.compaction import should_compact, compact

@pytest.mark.asyncio
async def test_should_compact():
    msgs = [{"role": "user", "content": "a" * 100}]
    assert await should_compact(msgs, threshold_tokens=1000) is False

    msgs = [{"role": "user", "content": "a" * 4000}]
    # 4000 // 4 = 1000. Not greater than 1000.
    # Actually, keep_last_n check might block it.
    # Threshold is exceeded if estimated_tokens > threshold_tokens.
    assert await should_compact(msgs, threshold_tokens=900) is False # because of KEEP_LAST_N_MESSAGES check

    msgs = [{"role": "user", "content": "a" * 100}] * 10
    assert await should_compact(msgs, threshold_tokens=10) is True

@pytest.mark.asyncio
async def test_compact():
    backend_router = MagicMock()
    backend_router.generate = AsyncMock(return_value={"response": "This is a summary"})

    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "how are you?"},
        {"role": "assistant", "content": "fine"},
    ]

    # keep_last_n = 2
    summary = await compact(msgs, keep_last_n=2, backend_router=backend_router)

    assert summary == "This is a summary"
    backend_router.generate.assert_called_once()
    call_args = backend_router.generate.call_args[1]
    assert "[user]: hello" in call_args["prompt"]
    assert "[assistant]: hi" in call_args["prompt"]
    assert "[user]: how are you?" not in call_args["prompt"] # kept

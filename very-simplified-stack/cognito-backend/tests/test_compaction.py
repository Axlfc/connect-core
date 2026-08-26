import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.compaction import should_compact, compact, extract_context_ledger
from app.core.session_manager import SessionManager
from pathlib import Path
import tempfile

@pytest.mark.asyncio
async def test_should_compact():
    msgs = [{"role": "user", "content": "a" * 100}]
    assert await should_compact(msgs, threshold_tokens=1000) is False

    msgs = [{"role": "user", "content": "a" * 4000}]
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
    summary, ledger = await compact(msgs, keep_last_n=2, backend_router=backend_router)

    assert summary == "This is a summary"
    assert isinstance(ledger, dict)
    assert "files_touched" in ledger
    backend_router.generate.assert_called_once()
    call_args = backend_router.generate.call_args[1]
    assert "[user]: hello" in call_args["prompt"]
    assert "[assistant]: hi" in call_args["prompt"]
    assert "[user]: how are you?" not in call_args["prompt"] # kept

@pytest.mark.asyncio
async def test_context_ledger_extraction_and_multi_compaction():
    backend_router = MagicMock()
    backend_router.generate = AsyncMock(return_value={"response": "Summary text"})

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(sessions_dir=Path(tmpdir))
        sid = sm.create(tmpdir)

        # 1. Turn 1 with file reads and tool calls
        sm.append_message(sid, "user", "Please inspect app/core/main.py and def process_data(x: int) -> str:")
        sm.append_message(
            sid,
            "assistant",
            "I will read app/core/main.py",
            tool_calls=[{
                "id": "tc1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "app/core/main.py"}'
                }
            }]
        )
        sm.append_message(sid, "tool", "file content of main.py", tool_name="read_file", tool_call_id="tc1")

        # First compaction
        eff1 = sm.get_effective_messages(sid)
        last_line1 = sm.get_last_line_index(sid)
        summary1, ledger1 = await compact(eff1, keep_last_n=0, backend_router=backend_router)

        assert "app/core/main.py" in ledger1["files_touched"]
        assert any("read_file" == tc["name"] for tc in ledger1["tool_calls"])
        assert any("def process_data" in sig for sig in ledger1["function_signatures"])

        sm.append_compaction(sid, summary1, last_line1, ledger1)

        # Verify effective message after 1st compaction
        eff_after_1 = sm.get_effective_messages(sid)
        assert len(eff_after_1) == 1
        assert "[Resumen de la conversación anterior]: Summary text" in eff_after_1[0]["content"]
        assert "app/core/main.py" in eff_after_1[0]["content"]
        assert "read_file" in eff_after_1[0]["content"]

        # 2. Turn 2 with new file write
        sm.append_message(sid, "user", "Now edit config/settings.py and class AppConfig:")
        sm.append_message(
            sid,
            "assistant",
            "Writing config/settings.py",
            tool_calls=[{
                "id": "tc2",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": '{"filepath": "config/settings.py", "content": "..."}'
                }
            }]
        )
        sm.append_message(sid, "tool", "wrote config/settings.py", tool_name="write_file", tool_call_id="tc2")

        # Second compaction (ledger survival check)
        eff2 = sm.get_effective_messages(sid)
        last_line2 = sm.get_last_line_index(sid)
        summary2, ledger2 = await compact(eff2, keep_last_n=0, backend_router=backend_router)

        sm.append_compaction(sid, summary2, last_line2, ledger2)

        # Both old and new files/tools/signatures must survive in ledger2
        assert "app/core/main.py" in ledger2["files_touched"]
        assert "config/settings.py" in ledger2["files_touched"]
        assert any("read_file" == tc["name"] for tc in ledger2["tool_calls"])
        assert any("write_file" == tc["name"] for tc in ledger2["tool_calls"])
        assert any("def process_data" in sig for sig in ledger2["function_signatures"])
        assert any("class AppConfig" in sig for sig in ledger2["function_signatures"])

        eff_after_2 = sm.get_effective_messages(sid)
        assert "app/core/main.py" in eff_after_2[0]["content"]
        assert "config/settings.py" in eff_after_2[0]["content"]

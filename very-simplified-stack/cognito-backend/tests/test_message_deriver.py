import json
import pytest
from pathlib import Path
from app.core.session.message_deriver import derive_messages_for_llm, DerivationConfig
from app.core.context_spill import SpillManager

@pytest.mark.asyncio
async def test_derive_messages_basic(tmp_path):
    session_id = "test_session_basic"
    session_file = tmp_path / f"{session_id}.jsonl"

    events = [
        {"type": "message", "role": "user", "content": "Hello", "ts": "2025-01-01T00:00:00Z"},
        {"type": "message", "role": "assistant", "content": "Hi there!", "ts": "2025-01-01T00:00:01Z"}
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    config = DerivationConfig(sessions_dir=tmp_path)
    messages = await derive_messages_for_llm(session_id, config)

    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Hello"}
    assert messages[1] == {"role": "assistant", "content": "Hi there!"}

@pytest.mark.asyncio
async def test_derive_messages_filtering_internal_events(tmp_path):
    session_id = "test_session_filter"
    session_file = tmp_path / f"{session_id}.jsonl"

    events = [
        {"type": "message", "role": "user", "content": "Do task", "ts": "2025-01-01T00:00:00Z"},
        {"type": "internal_system", "data": {"internal": "secret"}, "ts": "2025-01-01T00:00:01Z"},
        {"type": "telemetry", "data": {"metric": 123}, "ts": "2025-01-01T00:00:02Z"},
        {"type": "message", "role": "assistant", "content": "Done", "ts": "2025-01-01T00:00:03Z"}
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    config = DerivationConfig(sessions_dir=tmp_path, exclude_internal=True)
    messages = await derive_messages_for_llm(session_id, config)

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

@pytest.mark.asyncio
async def test_derive_messages_compaction_covers_through_line(tmp_path):
    session_id = "test_session_compaction"
    session_file = tmp_path / f"{session_id}.jsonl"

    # Line 0: user msg
    # Line 1: assistant msg
    # Line 2: compaction event covering through line 1
    # Line 3: user msg after compaction
    events = [
        {"type": "message", "role": "user", "content": "Old msg 1"},
        {"type": "message", "role": "assistant", "content": "Old reply 1"},
        {"type": "compaction", "summary": "User asked to do something. Done.", "covers_through_line": 1},
        {"type": "message", "role": "user", "content": "New question"}
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    config = DerivationConfig(sessions_dir=tmp_path)
    messages = await derive_messages_for_llm(session_id, config)

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "[Resumen de la conversación anterior]: User asked to do something. Done." in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "New question"}

@pytest.mark.asyncio
async def test_derive_messages_context_spill_injection(tmp_path):
    session_id = "test_session_spill"
    session_file = tmp_path / f"{session_id}.jsonl"
    spill_dir = tmp_path / "spill"

    spill_mgr = SpillManager(spill_dir=spill_dir, token_threshold=10)

    large_content = "Word " * 50

    events = [
        {"type": "message", "role": "user", "content": large_content}
    ]
    with open(session_file, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    config = DerivationConfig(
        sessions_dir=tmp_path,
        spill_manager=spill_mgr,
        enable_spill_injection=True,
        spill_threshold_tokens=10
    )
    messages = await derive_messages_for_llm(session_id, config)

    assert len(messages) == 1
    assert "Context Spill References Active" in messages[0]["content"]
    assert "spill_" in messages[0]["content"]

import pytest
import tempfile
from pathlib import Path
from app.core.session_manager import SessionManager
from app.core.session.message_deriver import derive_messages_for_llm, DerivationConfig

@pytest.fixture
def session_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SessionManager(sessions_dir=Path(tmpdir))

@pytest.mark.asyncio
async def test_session_compaction_message_loss_and_system_prompt_regression(session_manager, tmp_path):
    cwd = str(tmp_path)
    agents_md_file = tmp_path / "AGENTS.md"
    agents_md_file.write_text("Instruction: Always follow AGENTS.md guidelines.")

    session_id = session_manager.create(cwd)

    # Turn 0 (lines 0, 1)
    session_manager.append_message(session_id, "user", "msg 0 - turn 1 user")
    session_manager.append_message(session_id, "assistant", "msg 1 - turn 1 assistant")

    # Turn 1 (lines 2, 3)
    session_manager.append_message(session_id, "user", "msg 2 - turn 2 user")
    session_manager.append_message(session_id, "assistant", "msg 3 - turn 2 assistant")

    # Intermediate message added after turn 2 cut-off point (line 4)
    # The compaction covers through line 3 (covers_through_line = 3)
    session_manager.append_message(session_id, "user", "msg 4 - intermediate message before compaction record")

    # Compaction record (line 5)
    session_manager.append_compaction(session_id, "Summary of turns 0 to 3", covers_through_line=3)

    # Post compaction message (line 6)
    session_manager.append_message(session_id, "assistant", "msg 6 - message after compaction record")

    # 1. Derive messages for LLM (production LLM path)
    config = DerivationConfig(
        cwd=cwd,
        sessions_dir=session_manager.sessions_dir
    )
    llm_messages = await derive_messages_for_llm(session_id, config)

    # 2. Get effective messages (direct path)
    effective_messages_with_sys = session_manager.get_effective_messages(session_id, include_system_prompt=True)
    effective_messages_raw = session_manager.get_effective_messages(session_id, include_system_prompt=False)

    # Assert System Prompt and AGENTS.md injection
    assert llm_messages[0]["role"] == "system"
    assert "AGENTS.md" in llm_messages[0]["content"] or "Always follow AGENTS.md guidelines." in llm_messages[0]["content"]

    assert effective_messages_with_sys[0]["role"] == "system"
    assert "AGENTS.md" in effective_messages_with_sys[0]["content"] or "Always follow AGENTS.md guidelines." in effective_messages_with_sys[0]["content"]

    # Assert Compaction Summary
    assert llm_messages[1]["role"] == "system"
    assert "[Resumen de la conversación anterior]: Summary of turns 0 to 3" in llm_messages[1]["content"]

    assert effective_messages_with_sys[1]["role"] == "system"
    assert "[Resumen de la conversación anterior]: Summary of turns 0 to 3" in effective_messages_with_sys[1]["content"]

    assert effective_messages_raw[0]["role"] == "system"
    assert "[Resumen de la conversación anterior]: Summary of turns 0 to 3" in effective_messages_raw[0]["content"]

    # Assert Intermediate Message Preservation (msg 4)
    user_msgs_llm = [m for m in llm_messages if m.get("content") == "msg 4 - intermediate message before compaction record"]
    assert len(user_msgs_llm) == 1

    user_msgs_eff = [m for m in effective_messages_with_sys if m.get("content") == "msg 4 - intermediate message before compaction record"]
    assert len(user_msgs_eff) == 1

    user_msgs_eff_raw = [m for m in effective_messages_raw if m.get("content") == "msg 4 - intermediate message before compaction record"]
    assert len(user_msgs_eff_raw) == 1

    # Assert Post-Compaction Message (msg 6)
    asst_msgs_llm = [m for m in llm_messages if m.get("content") == "msg 6 - message after compaction record"]
    assert len(asst_msgs_llm) == 1

    asst_msgs_eff = [m for m in effective_messages_with_sys if m.get("content") == "msg 6 - message after compaction record"]
    assert len(asst_msgs_eff) == 1

    # Compare non-system-prompt message structure between derive_messages_for_llm and get_effective_messages
    assert llm_messages[1:] == effective_messages_with_sys[1:]

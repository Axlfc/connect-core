import pytest
from typing import List, Dict, Any, Optional
from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext
from app.core.tools.read_tool import ReadTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.bash_tool import BashTool
from app.core.events import ToolCallEvent, ToolResultEvent, DoneEvent
from app.core.exec_policy import evaluate_tool_execution, ExecVerdict


class TurnSequenceMockRouter:
    """Mock router yielding specified tool calls per turn."""
    def __init__(self, turns_tool_calls: List[List[Dict[str, Any]]]):
        self.turns_tool_calls = turns_tool_calls
        self.turn = 0

    async def generate_with_tools(
        self, messages: List[Dict[str, Any]], tools_schema: List[Dict[str, Any]], model_params: Optional[Dict[str, Any]] = None
    ):
        if self.turn < len(self.turns_tool_calls):
            tcs = self.turns_tool_calls[self.turn]
            self.turn += 1
            if tcs:
                yield {
                    "token": f"Turn {self.turn} thinking...",
                    "tool_calls": tcs
                }
            else:
                yield {"token": f"Turn {self.turn} done without tool calls."}
        else:
            self.turn += 1
            yield {"token": "Finished."}


def test_evaluate_tool_execution_read_only_planning_phase():
    """Unit test evaluate_tool_execution in planning phase."""
    write_tool = WriteTool()
    read_tool = ReadTool()

    # Turn 1, untrusted, planning_phase=True -> write_tool DENIED
    verdict, reason = evaluate_tool_execution(
        tool=write_tool,
        trusted=False,
        turn=1,
        planning_phase=True,
        read_only_turns=1
    )
    assert verdict == ExecVerdict.DENEGAR
    assert "Fase de planificación de solo lectura activa" in reason

    # Turn 1, untrusted, planning_phase=True -> read_tool PERMITTED
    verdict, reason = evaluate_tool_execution(
        tool=read_tool,
        trusted=False,
        turn=1,
        planning_phase=True,
        read_only_turns=1
    )
    assert verdict == ExecVerdict.PERMITIR

    # Turn 2, untrusted, planning_phase=True, read_only_turns=1 -> write_tool REQUIERE_APROBACION in untrusted workspace
    verdict, reason = evaluate_tool_execution(
        tool=write_tool,
        trusted=False,
        turn=2,
        planning_phase=True,
        read_only_turns=1
    )
    assert verdict == ExecVerdict.REQUIERE_APROBACION

    # Turn 1, trusted workspace -> write_tool PERMITTED
    verdict, reason = evaluate_tool_execution(
        tool=write_tool,
        trusted=True,
        turn=1,
        planning_phase=True,
        read_only_turns=1
    )
    assert verdict == ExecVerdict.PERMITIR

    # Turn 1, untrusted workspace, planning_phase=False -> write_tool REQUIERE_APROBACION (due to untrusted workspace)
    verdict, reason = evaluate_tool_execution(
        tool=write_tool,
        trusted=False,
        turn=1,
        planning_phase=False,
        read_only_turns=1
    )
    assert verdict == ExecVerdict.REQUIERE_APROBACION


@pytest.mark.asyncio
async def test_agent_loop_first_turn_write_rejected_in_untrusted_planning_phase(tmp_path):
    """Integration test: First turn attempt to write in untrusted workspace is rejected."""
    tools = [ReadTool(), WriteTool(), EditTool()]
    context = ToolContext(
        cwd=str(tmp_path),
        trusted=False,
        protected_files=set()
    )

    router = TurnSequenceMockRouter([
        [
            {
                "id": "tc_write_1",
                "function": {"name": "write", "arguments": {"path": "test.txt", "content": "hello"}}
            }
        ],
        []
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Write test.txt"}],
        tools=tools,
        context=context,
        backend_router=router,
        planning_phase=True,
        read_only_turns=1,
        max_turns=2
    ):
        events.append(event)

    result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(result_events) == 1
    assert result_events[0].is_error is True
    assert "Fase de planificación de solo lectura activa" in result_events[0].output
    assert not (tmp_path / "test.txt").exists()


@pytest.mark.asyncio
async def test_agent_loop_first_turn_read_allowed_in_untrusted_planning_phase(tmp_path):
    """Integration test: First turn attempt to read in untrusted workspace succeeds during planning phase."""
    sample_file = tmp_path / "read_sample.txt"
    sample_file.write_text("sample content", encoding="utf-8")

    tools = [ReadTool(), WriteTool()]
    context = ToolContext(
        cwd=str(tmp_path),
        trusted=False,
        protected_files=set()
    )

    router = TurnSequenceMockRouter([
        [
            {
                "id": "tc_read_1",
                "function": {"name": "read", "arguments": {"path": "read_sample.txt"}}
            }
        ]
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Read sample file"}],
        tools=tools,
        context=context,
        backend_router=router,
        planning_phase=True,
        read_only_turns=1,
        max_turns=1
    ):
        events.append(event)

    result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(result_events) == 1
    assert result_events[0].is_error is False
    assert "sample content" in result_events[0].output


@pytest.mark.asyncio
async def test_agent_loop_multiturn_read_only_planning_phase(tmp_path):
    """Integration test: Configurable read_only_turns=2 rejects writes in turns 1 and 2 in untrusted workspace."""
    tools = [ReadTool(), WriteTool()]
    untrusted_context = ToolContext(cwd=str(tmp_path), trusted=False, protected_files=set())

    router = TurnSequenceMockRouter([
        [
            {
                "id": "tc_write_turn1",
                "function": {"name": "write", "arguments": {"path": "file1.txt", "content": "turn1"}}
            }
        ],
        [
            {
                "id": "tc_write_turn2",
                "function": {"name": "write", "arguments": {"path": "file2.txt", "content": "turn2"}}
            }
        ]
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Perform multi-turn writes"}],
        tools=tools,
        context=untrusted_context,
        backend_router=router,
        planning_phase=True,
        read_only_turns=2,
        max_turns=2
    ):
        events.append(event)

    results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(results) == 2

    # Turn 1 write rejected
    assert results[0].is_error is True
    assert "Fase de planificación de solo lectura activa (turno 1/2)" in results[0].output

    # Turn 2 write rejected
    assert results[1].is_error is True
    assert "Fase de planificación de solo lectura activa (turno 2/2)" in results[1].output


@pytest.mark.asyncio
async def test_agent_loop_disabled_planning_phase_allows_first_turn_write(tmp_path):
    """Integration test: When planning_phase=False on trusted workspace, first turn write is allowed."""
    tools = [WriteTool()]
    context = ToolContext(
        cwd=str(tmp_path),
        trusted=True,
        protected_files=set()
    )

    router = TurnSequenceMockRouter([
        [
            {
                "id": "tc_write_direct",
                "function": {"name": "write", "arguments": {"path": "direct.txt", "content": "direct_content"}}
            }
        ]
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Write direct"}],
        tools=tools,
        context=context,
        backend_router=router,
        planning_phase=False,
        read_only_turns=1,
        max_turns=1
    ):
        events.append(event)

    results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(results) == 1
    assert results[0].is_error is False
    assert (tmp_path / "direct.txt").exists()
    assert (tmp_path / "direct.txt").read_text(encoding="utf-8") == "direct_content"

import pytest
from app.core.guardrails.tool_loop_detector import (
    ToolLoopDetector,
    normalize_args,
    compute_tool_call_hash,
)
from app.core.events import ToolCallEvent, ToolResultEvent, DoneEvent
from app.core.agent_loop import agent_loop
from app.core.tools.base import AgentTool, ToolContext, ToolResult


def test_normalize_args_dict():
    args1 = {"b": 2, "a": 1}
    args2 = {"a": 1, "b": 2}
    assert normalize_args(args1) == normalize_args(args2)
    assert normalize_args(args1) == '{"a":1,"b":2}'


def test_normalize_args_json_string():
    str_json = '{"b": 2, "a": 1}'
    dict_args = {"a": 1, "b": 2}
    assert normalize_args(str_json) == normalize_args(dict_args)


def test_compute_tool_call_hash():
    h1 = compute_tool_call_hash("read_file", {"path": "test.txt", "offset": 0})
    h2 = compute_tool_call_hash("read_file", {"offset": 0, "path": "test.txt"})
    assert h1 == h2


def test_tool_loop_detector_trigger():
    detector = ToolLoopDetector(window_size=4, threshold=3)

    tool_name = "read_file"
    args = {"filepath": "main.py"}
    output = "file content"

    # Call 1: No warning
    res1 = detector.record_and_check(tool_name, args, output=output)
    assert res1 is None

    # Call 2: No warning
    res2 = detector.record_and_check(tool_name, args, output=output)
    assert res2 is None

    # Call 3: Exceeds threshold (3 consecutive calls) -> Trigger warning
    res3 = detector.record_and_check(tool_name, args, output=output)
    assert res3 is not None
    assert "ADVERTENCIA DEL SISTEMA: Has intentado ejecutar la herramienta 'read_file'" in res3
    assert "con los mismos parámetros múltiples veces sin éxito." in res3


def test_tool_loop_detector_legitimate_reads_growing_file_no_warning():
    """
    Simulates 5 consecutive legitimate reads of a file that grows (result changes).
    Confirms that NO warning is triggered.
    """
    detector = ToolLoopDetector(window_size=10, threshold=3)
    tool_name = "read"
    args = {"path": "log.txt"}

    for i in range(1, 6):
        file_content = f"Log content line 1 to {i}"
        res = detector.record_and_check(tool_name, args, output=file_content)
        assert res is None, f"Warning should not trigger on call {i} because output changed"


def test_tool_loop_detector_identical_side_effect_calls_triggers_warning():
    """
    Simulates 5 identical calls with no change in result on a tool with side effects (or any tool).
    Confirms that warning IS triggered starting at threshold (call 3).
    """
    detector = ToolLoopDetector(window_size=10, threshold=3)
    tool_name = "bash"
    args = {"command": "echo hello"}
    output = "hello\n"

    for i in range(1, 6):
        res = detector.record_and_check(tool_name, args, output=output)
        if i < 3:
            assert res is None, f"Call {i} should not trigger warning"
        else:
            assert res is not None, f"Call {i} should trigger warning"
            assert "ADVERTENCIA DEL SISTEMA" in res


def test_tool_loop_detector_different_args_resets_consecutive_count():
    detector = ToolLoopDetector(window_size=4, threshold=3)

    tool_name = "read_file"
    args1 = {"filepath": "file1.py"}
    args2 = {"filepath": "file2.py"}

    detector.record_and_check(tool_name, args1)
    detector.record_and_check(tool_name, args1)
    # Different args breaks sequence
    detector.record_and_check(tool_name, args2)

    # 3rd attempt for args1 (consecutive sequence reset)
    res = detector.record_and_check(tool_name, args1)
    assert res is None


class DummyTool(AgentTool):
    name: str = "dummy_tool"
    description: str = "A dummy tool for testing"
    parameters_schema: dict = {
        "type": "object",
        "properties": {"arg": {"type": "string"}},
        "required": ["arg"]
    }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        return ToolResult(is_error=False, output="Dummy output")


class MockBackendRouterLoop:
    def __init__(self, repeats: int):
        self.repeats = repeats
        self.turn = 0
        self.received_messages = []

    async def generate_with_tools(self, messages, tools_schema, model_params=None):
        self.received_messages.append(list(messages))
        self.turn += 1
        if self.turn <= self.repeats:
            yield {
                "token": "",
                "tool_calls": [
                    {
                        "id": f"call_{self.turn}",
                        "function": {
                            "name": "dummy_tool",
                            "arguments": {"arg": "test"}
                        }
                    }
                ]
            }
        else:
            yield {"token": "Done"}


@pytest.mark.asyncio
async def test_agent_loop_guardrail_injection():
    tool = DummyTool()
    context = ToolContext(cwd="/tmp", trusted=True, protected_files=set())
    # Backend requested tool call 3 times
    router = MockBackendRouterLoop(repeats=3)

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Run tool"}],
        tools=[tool],
        context=context,
        backend_router=router,
        max_turns=5
    ):
        events.append(event)

    # Turn 1: 1st tool call
    # Turn 2: 2nd tool call
    # Turn 3: 3rd tool call -> triggers guardrail -> system warning injected into messages for Turn 4 prompt!
    assert len(router.received_messages) == 4
    turn_4_messages = router.received_messages[3]

    system_warning_messages = [
        m for m in turn_4_messages
        if m.get("role") == "system" and "ADVERTENCIA DEL SISTEMA: Has intentado ejecutar la herramienta 'dummy_tool'" in m.get("content", "")
    ]
    assert len(system_warning_messages) == 1

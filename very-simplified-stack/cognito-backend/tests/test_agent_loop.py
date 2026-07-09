import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.core.agent_loop import agent_loop
from app.core.tools.base import ToolContext, ToolResult, AgentTool
from app.core.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent

class MockTool(AgentTool):
    name = "mock_tool"
    description = "A mock tool"
    parameters_schema = {"type": "object", "properties": {"arg1": {"type": "string"}}}

    def __init__(self):
        self.mock_execute = AsyncMock()

    async def execute(self, arguments, context):
        return await self.mock_execute(arguments, context)

@pytest.fixture
def tool_context():
    return ToolContext(cwd="/tmp", trusted=True, protected_files=set())

@pytest.mark.asyncio
async def test_agent_loop_simple_text(tool_context):
    backend_router = MagicMock()

    async def mock_generate(*args, **kwargs):
        yield {"token": "Hello"}
        yield {"token": " world"}

    backend_router.generate_with_tools = mock_generate

    messages = [{"role": "user", "content": "Hi"}]
    tools = []

    events = []
    async for event in agent_loop(messages, tools, tool_context, backend_router):
        events.append(event)

    assert len(events) == 3 # "Hello", " world", DoneEvent
    assert isinstance(events[0], TextDeltaEvent)
    assert events[0].content == "Hello"
    assert isinstance(events[1], TextDeltaEvent)
    assert events[1].content == " world"
    assert isinstance(events[2], DoneEvent)
    assert events[2].stop_reason == "end_turn"

@pytest.mark.asyncio
async def test_agent_loop_tool_call(tool_context):
    backend_router = MagicMock()
    mock_tool = MockTool()
    mock_tool.mock_execute.return_value = ToolResult(output="tool result")

    # Turn 1: model calls tool
    # Turn 2: model responds with final text
    turn = 0
    async def mock_generate(*args, **kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            yield {
                "token": "I will use a tool",
                "tool_calls": [{
                    "function": {"name": "mock_tool", "arguments": {"arg1": "val1"}}
                }]
            }
        else:
            yield {"token": "Final answer"}

    backend_router.generate_with_tools = mock_generate

    messages = [{"role": "user", "content": "use tool"}]
    tools = [mock_tool]

    events = []
    async for event in agent_loop(messages, tools, tool_context, backend_router):
        events.append(event)

    # Events expected:
    # 1. TextDeltaEvent "I will use a tool"
    # 2. ToolCallEvent "mock_tool"
    # 3. ToolResultEvent "tool result"
    # 4. TextDeltaEvent "Final answer"
    # 5. DoneEvent "end_turn"

    assert any(isinstance(e, ToolCallEvent) for e in events)
    assert any(isinstance(e, ToolResultEvent) for e in events)
    assert any(isinstance(e, TextDeltaEvent) and e.content == "Final answer" for e in events)
    assert events[-1].stop_reason == "end_turn"
    mock_tool.mock_execute.assert_called_once()

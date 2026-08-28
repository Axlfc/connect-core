import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.agent_loop import agent_loop
from app.core.compaction import compact
from app.core.extensions.registry import ExtensionRegistry
from app.core.extensions.api import (
    ExtensionAPI, AgentStartPayload, ToolPreExecPayload, ToolPostExecPayload, PreCompactPayload
)
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.events import ToolResultEvent, DoneEvent


class DummyTool(AgentTool):
    def __init__(self, name="dummy_tool"):
        self.name = name
        self.description = "A dummy tool for testing hooks"
        self.parameters_schema = {
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
        }
        self.executed = False

    async def execute(self, arguments, context):
        self.executed = True
        return ToolResult(is_error=False, output=f"Executed {self.name} with {arguments}")


class MockBackendRouter:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls or []
        self.generated_prompts = []

    async def generate_with_tools(self, messages, tools_schema, model_params=None):
        if self.tool_calls:
            tc = self.tool_calls.pop(0)
            yield {"tool_calls": [tc]}
        else:
            yield {"token": "Done"}

    async def generate(self, prompt):
        self.generated_prompts.append(prompt)
        return {"response": "Resumen de prueba para compactación."}


@pytest.fixture
def clean_registry(monkeypatch):
    registry = ExtensionRegistry()
    monkeypatch.setattr("app.core.extensions.registry.extension_registry", registry)
    monkeypatch.setattr("app.core.agent_loop.extension_registry", registry)
    return registry


@pytest.mark.asyncio
async def test_on_tool_pre_exec_blocks_tool_execution(clean_registry):
    """
    Acceptance Criterion: A test hook registered in on_tool_pre_exec can block a tool call.
    """
    pre_exec_calls = []

    async def security_validator_hook(payload: ToolPreExecPayload):
        pre_exec_calls.append(payload)
        if payload.tool_name == "dummy_tool" and payload.arguments.get("arg1") == "forbidden":
            return "Acceso denegado por regla de seguridad corporativa SEC-001"
        return None

    clean_registry.register_hook("on_tool_pre_exec", security_validator_hook, origin=None)

    tool = DummyTool("dummy_tool")
    context = ToolContext(cwd="/tmp/test_workspace", trusted=True, protected_files=[])
    router = MockBackendRouter(tool_calls=[
        {"id": "call_1", "function": {"name": "dummy_tool", "arguments": {"arg1": "forbidden"}}}
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Run tool"}],
        tools=[tool],
        context=context,
        backend_router=router,
        planning_phase=False,
    ):
        events.append(event)

    # Verify tool was NOT executed by the tool object
    assert tool.executed is False

    # Verify on_tool_pre_exec hook was triggered
    assert len(pre_exec_calls) == 1
    assert pre_exec_calls[0].tool_name == "dummy_tool"
    assert pre_exec_calls[0].arguments == {"arg1": "forbidden"}

    # Verify ToolResultEvent returned rejection output
    tool_results = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_results) == 1
    assert tool_results[0].is_error is True
    assert "Acción bloqueada por hook de seguridad (on_tool_pre_exec)" in tool_results[0].output
    assert "SEC-001" in tool_results[0].output


@pytest.mark.asyncio
async def test_on_agent_start_event_fires_at_loop_start(clean_registry):
    """
    Criterion: on_agent_start fires at the correct moment with complete payload.
    """
    agent_start_payloads = []

    async def on_agent_start_hook(payload: AgentStartPayload):
        agent_start_payloads.append(payload)
        return None

    clean_registry.register_hook("on_agent_start", on_agent_start_hook, origin=None)

    tool = DummyTool("dummy_tool")
    context = ToolContext(cwd="/tmp/workspace_agent_start", trusted=True, protected_files=[])
    router = MockBackendRouter()

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[tool],
        context=context,
        backend_router=router,
        session_id="session_start_123",
        max_turns=5,
    ):
        events.append(event)

    assert len(agent_start_payloads) == 1
    p = agent_start_payloads[0]
    assert p.session_id == "session_start_123"
    assert p.cwd == "/tmp/workspace_agent_start"
    assert p.max_turns == 5
    assert len(p.messages) == 1
    assert p.messages[0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_on_tool_post_exec_event_fires_after_execution(clean_registry):
    """
    Criterion: on_tool_post_exec fires at the correct moment with output and status.
    """
    post_exec_payloads = []

    async def on_tool_post_hook(payload: ToolPostExecPayload):
        post_exec_payloads.append(payload)
        return None

    clean_registry.register_hook("on_tool_post_exec", on_tool_post_hook, origin=None)

    tool = DummyTool("dummy_tool")
    context = ToolContext(cwd="/tmp/workspace_post_exec", trusted=True, protected_files=[])
    router = MockBackendRouter(tool_calls=[
        {"id": "call_post_1", "function": {"name": "dummy_tool", "arguments": {"arg1": "allowed_value"}}}
    ])

    events = []
    async for event in agent_loop(
        messages=[{"role": "user", "content": "Execute allowed tool"}],
        tools=[tool],
        context=context,
        backend_router=router,
        session_id="session_post_123",
        planning_phase=False,
    ):
        events.append(event)

    assert tool.executed is True
    assert len(post_exec_payloads) == 1
    p = post_exec_payloads[0]
    assert p.tool_name == "dummy_tool"
    assert p.arguments == {"arg1": "allowed_value"}
    assert p.is_error is False
    assert "Executed dummy_tool" in p.output
    assert p.session_id == "session_post_123"


@pytest.mark.asyncio
async def test_on_pre_compact_event_fires_before_compaction(clean_registry):
    """
    Criterion: on_pre_compact fires before compaction summary generation.
    """
    pre_compact_payloads = []

    async def on_pre_compact_hook(payload: PreCompactPayload):
        pre_compact_payloads.append(payload)
        return None

    clean_registry.register_hook("on_pre_compact", on_pre_compact_hook, origin=None)

    router = MockBackendRouter()
    messages = [
        {"role": "user", "content": "msg 1"},
        {"role": "assistant", "content": "msg 2"},
        {"role": "user", "content": "msg 3"},
    ]

    summary, ledger = await compact(
        messages,
        keep_last_n=1,
        backend_router=router,
        session_id="session_compact_99",
        cwd="/tmp/compact_cwd"
    )

    assert len(pre_compact_payloads) == 1
    p = pre_compact_payloads[0]
    assert p.session_id == "session_compact_99"
    assert p.cwd == "/tmp/compact_cwd"
    assert p.keep_last_n == 1
    assert len(p.messages) == 3
    assert len(router.generated_prompts) == 1


@pytest.mark.asyncio
async def test_extension_api_helper_registration_and_origin_isolation(clean_registry):
    """
    Verify ExtensionAPI helper methods (.on_agent_start, .on_tool_pre_exec, etc.)
    and project-local origin filtering.
    """
    global_start_count = 0
    project_start_count = 0

    api_global = ExtensionAPI(clean_registry, origin=None)
    api_project_a = ExtensionAPI(clean_registry, origin="/repo/a")

    async def global_start_handler(payload: AgentStartPayload):
        nonlocal global_start_count
        global_start_count += 1

    async def project_start_handler(payload: AgentStartPayload):
        nonlocal project_start_count
        project_start_count += 1

    api_global.on_agent_start(global_start_handler)
    api_project_a.on_agent_start(project_start_handler)

    tool = DummyTool()

    # Run agent loop with cwd=/repo/a -> Both global and project_a handlers fire
    async for _ in agent_loop(
        messages=[{"role": "user", "content": "hi"}],
        tools=[tool],
        context=ToolContext(cwd="/repo/a", trusted=True, protected_files=[]),
        backend_router=MockBackendRouter(),
    ):
        pass

    assert global_start_count == 1
    assert project_start_count == 1

    # Run agent loop with cwd=/repo/b -> Only global handler fires
    async for _ in agent_loop(
        messages=[{"role": "user", "content": "hi"}],
        tools=[tool],
        context=ToolContext(cwd="/repo/b", trusted=True, protected_files=[]),
        backend_router=MockBackendRouter(),
    ):
        pass

    assert global_start_count == 2
    assert project_start_count == 1

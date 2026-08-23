import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel
from app.core.extensions.registry import ExtensionRegistry

class MockPayload(BaseModel):
    data: str

@pytest.mark.asyncio
async def test_registry_tool_isolation():
    registry = ExtensionRegistry()

    global_tool = MagicMock()
    global_tool.name = "t1"
    registry.register_tool(global_tool, origin=None)

    project_tool = MagicMock()
    project_tool.name = "t2"
    registry.register_tool(project_tool, origin="/repo/a")

    # tools_for A should have both
    tools_a = registry.tools_for("/repo/a")
    assert any(t.name == "t1" for t in tools_a)
    assert any(t.name == "t2" for t in tools_a)
    assert any(getattr(t, "name", None) == "apply_unified_patch" for t in tools_a)
    assert any(getattr(t, "name", None) == "edit" for t in tools_a)

    # tools_for B should only have global
    tools_b = registry.tools_for("/repo/b")
    assert any(t.name == "t1" for t in tools_b)
    assert not any(t.name == "t2" for t in tools_b)

@pytest.mark.asyncio
async def test_registry_hook_isolation():
    registry = ExtensionRegistry()

    h1 = AsyncMock()
    registry.register_hook("session_start", h1, origin=None)

    h2 = AsyncMock()
    registry.register_hook("session_start", h2, origin="/repo/a")

    payload = MockPayload(data="test")

    # Fire for A
    await registry.fire("session_start", payload, "/repo/a")
    assert h1.call_count == 1
    assert h2.call_count == 1

    # Fire for B
    h1.reset_mock()
    h2.reset_mock()
    await registry.fire("session_start", payload, "/repo/b")
    assert h1.call_count == 1
    assert h2.call_count == 0

@pytest.mark.asyncio
async def test_registry_veto():
    registry = ExtensionRegistry()

    h1 = AsyncMock(return_value="No way")
    registry.register_hook("before_tool_call", h1, origin=None)

    h2 = AsyncMock()
    registry.register_hook("before_tool_call", h2, origin=None)

    veto = await registry.fire("before_tool_call", MockPayload(data="x"), "/any")
    assert veto == "No way"
    # Second handler should NOT be called
    assert h2.call_count == 0

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extensions.hooked_tool import HookedTool
from app.core.tools.base import ToolResult

@pytest.mark.asyncio
async def test_hooked_tool_execution():
    inner = MagicMock()
    inner.name = "test_tool"
    inner.description = "desc"
    inner.parameters_schema = {}
    inner.execute = AsyncMock(return_value=ToolResult(output="ok"))

    registry = MagicMock()
    registry.fire = AsyncMock(return_value=None)

    hooked = HookedTool(inner, registry, "s1", "/cwd")

    res = await hooked.execute({"arg": 1}, MagicMock())

    assert res.output == "ok"
    assert registry.fire.call_count == 2
    assert registry.fire.await_args_list[0][0][0] == "before_tool_call"
    assert registry.fire.await_args_list[1][0][0] == "after_tool_call"
    assert inner.execute.called

@pytest.mark.asyncio
async def test_hooked_tool_veto():
    inner = MagicMock()
    inner.name = "test_tool"
    inner.description = "desc"
    inner.parameters_schema = {}
    inner.execute = AsyncMock()

    registry = MagicMock()
    registry.fire = AsyncMock(side_effect=[ "Blocked", None ])

    hooked = HookedTool(inner, registry, "s1", "/cwd")

    res = await hooked.execute({}, MagicMock())

    assert res.is_error
    assert "Blocked" in res.output
    assert not inner.execute.called

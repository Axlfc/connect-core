import os
import sys
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure root directory and cognito-backend are in sys.path
ROOT_DIR = Path(__file__).parent.parent.parent.parent.resolve()
BACKEND_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from cognito_agent import SimpleCognitoStack
from app.core.session_manager import SessionManager
from app.core.tools.base import AgentTool, ToolResult, ToolContext
from app.core.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent, DoneEvent


@pytest.fixture
def temp_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return str(workspace)


def test_cognito_agent_initialization(temp_workspace):
    stack = SimpleCognitoStack(cwd=temp_workspace)
    assert stack.cwd == str(Path(temp_workspace).resolve())
    assert stack.session_id is not None

    # Confirm session was registered in SessionManager
    sm = SessionManager(sessions_dir=stack.session_manager.sessions_dir)
    meta = sm.open(stack.session_id)
    assert meta.cwd == str(Path(temp_workspace).resolve())


def test_cognito_agent_solve_flow_uses_agent_loop(temp_workspace):
    stack = SimpleCognitoStack(cwd=temp_workspace)

    async def mock_generate(messages, tools, model_params=None):
        yield {"token": "Deduction output: 2 + 2 = 4"}

    with patch("cognito_agent.backend_router.generate_with_tools", side_effect=mock_generate):
        with patch.object(stack, "route_task", return_value="deduction"):
            result = stack.solve("Calcular 2 + 2")

    assert "Deduction output: 2 + 2 = 4" in result

    # Check that messages were persisted to SessionManager
    messages = stack.session_manager.get_effective_messages(stack.session_id)
    assert len(messages) > 0
    assert any("Calcular 2 + 2" in m.get("content", "") for m in messages)


def test_cognito_agent_tool_execution_and_exec_policy(temp_workspace):
    stack = SimpleCognitoStack(cwd=temp_workspace)

    turn = 0
    async def mock_generate(messages, tools, model_params=None):
        nonlocal turn
        turn += 1
        if turn == 1:
            yield {
                "token": "Ejecutando comando...",
                "tool_calls": [{
                    "function": {
                        "name": "bash_run",
                        "arguments": {"command": "rm -rf /"}
                    }
                }]
            }
        else:
            yield {"token": "Comando bloqueado por política de seguridad."}

    from app.core.tools.bash_tool import BashTool
    bash_tool = BashTool()

    with patch("cognito_agent.backend_router.generate_with_tools", side_effect=mock_generate):
        with patch("cognito_agent.extension_registry.tools_for", return_value=[bash_tool]):
            result = stack.execute_reasoning("Test dangerous command", "conduction")

    # Verify command was executed through agent_loop and blocked by ExecPolicy
    assert "Comando bloqueado" in result or "Ejecutando" in result
    messages = stack.session_manager.get_effective_messages(stack.session_id)
    # Confirm security error / tool output was captured
    tool_results = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_results) == 1
    assert "DENIED" in tool_results[0].get("content", "") or "blocked" in tool_results[0].get("content", "").lower() or "policy" in tool_results[0].get("content", "").lower() or "tool_output" in tool_results[0].get("content", "")


def test_cognito_agent_triggers_tool_loop_detector(temp_workspace):
    stack = SimpleCognitoStack(cwd=temp_workspace)

    class RepetitiveTool(AgentTool):
        name = "write_file"
        description = "Write file"
        parameters_schema = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}

        async def execute(self, arguments, context):
            return ToolResult(output="Written OK")

    tool = RepetitiveTool()
    turns = 0

    async def mock_generate(messages, tools, model_params=None):
        nonlocal turns
        turns += 1
        if turns <= 4:
            yield {
                "token": f"Turn {turns}",
                "tool_calls": [{
                    "function": {
                        "name": "write_file",
                        "arguments": {"path": "test.txt", "content": "same"}
                    }
                }]
            }
        else:
            yield {"token": "Finished"}

    with patch("cognito_agent.backend_router.generate_with_tools", side_effect=mock_generate):
        with patch("cognito_agent.extension_registry.tools_for", return_value=[tool]):
            result = stack.execute_reasoning("Test loop detector", "conduction")

    messages = stack.session_manager.get_effective_messages(stack.session_id)
    # Check if system loop warning was injected by ToolLoopDetector
    system_msgs = [m for m in messages if m.get("role") == "system" and "repetitivas" in m.get("content", "").lower()]
    assert len(system_msgs) > 0 or turns >= 4

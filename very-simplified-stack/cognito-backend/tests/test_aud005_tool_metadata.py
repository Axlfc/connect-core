import pytest
from typing import Any, Dict
from app.core.tools.base import AgentTool, ToolContext, ToolResult
from app.core.tools.read_tool import ReadTool
from app.core.tools.write_tool import WriteTool
from app.core.tools.edit_tool import EditTool
from app.core.tools.unified_patch_tool import UnifiedPatchTool
from app.core.tools.fs_tools import ListDirectoryTool, SearchFilesTool
from app.core.tools.bash_tool import BashTool
from app.core.tools.persistent_shell_tool import PersistentShellTool
from app.core.tools.nooa_tools import ShellTools, TodoTools, WebPublisherTools
from app.core.tools.query_spill_tool import QuerySpillTool
from app.core.tools.read_spill_tool import ReadSpillTool
from app.core.tools.code_review_tool import CodeReviewTool
from app.core.mcp_client import WrappedMCPTool
from app.core.extensions.hooked_tool import HookedTool
from app.core.guardrails.tool_loop_detector import ToolLoopDetector
from app.core.exec_policy import evaluate_tool_execution, ExecVerdict
from app.core.approval import ApprovalManager


class CustomReadOnlyTool(AgentTool):
    name = "custom_read_only"
    description = "Custom tool that is read only."
    is_read_only = True
    is_destructive = False
    concurrency_safe = True

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(output="read_ok")


class CustomDestructiveTool(AgentTool):
    name = "custom_destructive"
    description = "Custom tool that is destructive."
    is_read_only = False
    is_destructive = True
    concurrency_safe = False

    async def execute(self, arguments: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(output="destruct_ok")


def test_agent_tool_base_metadata_defaults():
    """Verify base AgentTool has metadata fields defined."""
    assert hasattr(AgentTool, "is_read_only")
    assert hasattr(AgentTool, "is_destructive")
    assert hasattr(AgentTool, "concurrency_safe")


def test_all_official_tools_declare_metadata():
    """Verify all official tools explicitly define risk and concurrency metadata."""
    tools = [
        (ReadTool(), True, False, True),
        (ListDirectoryTool(), True, False, True),
        (SearchFilesTool(), True, False, True),
        (QuerySpillTool(), True, False, True),
        (ReadSpillTool(), True, False, True),
        (CodeReviewTool(), True, False, True),
        (WriteTool(), False, True, False),
        (EditTool(), False, True, False),
        (UnifiedPatchTool(), False, True, False),
        (BashTool(), False, True, False),
        (PersistentShellTool(), False, True, False),
        (ShellTools(), False, True, False),
        (TodoTools(), False, False, False),
        (WebPublisherTools(), False, True, False),
    ]

    for tool, expected_read_only, expected_destructive, expected_concurrency in tools:
        assert tool.is_read_only == expected_read_only, f"Tool {tool.name} mismatch on is_read_only"
        assert tool.is_destructive == expected_destructive, f"Tool {tool.name} mismatch on is_destructive"
        assert tool.concurrency_safe == expected_concurrency, f"Tool {tool.name} mismatch on concurrency_safe"


def test_wrapped_mcp_and_hooked_tool_metadata_propagation():
    """Verify WrappedMCPTool and HookedTool propagate metadata correctly."""
    mcp_tool = WrappedMCPTool(
        name="mcp_read",
        description="mcp read tool",
        parameters_schema={},
        client=None,
        is_read_only=True,
        is_destructive=False,
        concurrency_safe=True,
    )
    assert mcp_tool.is_read_only is True
    assert mcp_tool.is_destructive is False
    assert mcp_tool.concurrency_safe is True

    hooked = HookedTool(
        inner=CustomDestructiveTool(),
        registry=None,
        session_id="s1",
        cwd="/tmp"
    )
    assert hooked.is_read_only is False
    assert hooked.is_destructive is True
    assert hooked.concurrency_safe is False


def test_tool_loop_detector_queries_tool_metadata():
    """Verify ToolLoopDetector uses tool.is_read_only metadata for hashing output."""
    detector = ToolLoopDetector(window_size=10, threshold=3)
    custom_read_tool = CustomReadOnlyTool()

    # Read-only tool: output changes per call, so hash differs and loop is NOT triggered
    detector.record_and_check("custom_read_only", {"q": "1"}, output="res1", tool=custom_read_tool)
    detector.record_and_check("custom_read_only", {"q": "1"}, output="res2", tool=custom_read_tool)
    warning = detector.record_and_check("custom_read_only", {"q": "1"}, output="res3", tool=custom_read_tool)
    assert warning is None

    # Destructive tool: output ignored for hashing, so identical args trigger loop detector
    custom_dest_tool = CustomDestructiveTool()
    detector.reset()
    detector.record_and_check("custom_destructive", {"path": "f.txt"}, output="a", tool=custom_dest_tool)
    detector.record_and_check("custom_destructive", {"path": "f.txt"}, output="b", tool=custom_dest_tool)
    warning = detector.record_and_check("custom_destructive", {"path": "f.txt"}, output="c", tool=custom_dest_tool)
    assert warning is not None
    assert "ADVERTENCIA DEL SISTEMA" in warning


def test_exec_policy_evaluates_tool_metadata():
    """Verify evaluate_tool_execution checks tool.is_destructive against project trust."""
    dest_tool = CustomDestructiveTool()
    read_tool = CustomReadOnlyTool()

    # Destructive tool in untrusted environment requires approval
    verdict, reason = evaluate_tool_execution(tool=dest_tool, trusted=False)
    assert verdict == ExecVerdict.REQUIERE_APROBACION
    assert "Herramienta destructiva" in reason

    # Destructive tool in trusted environment is permitted
    verdict, reason = evaluate_tool_execution(tool=dest_tool, trusted=True)
    assert verdict == ExecVerdict.PERMITIR

    # Read-only tool is permitted even in untrusted environment
    verdict, reason = evaluate_tool_execution(tool=read_tool, trusted=False)
    assert verdict == ExecVerdict.PERMITIR


@pytest.mark.asyncio
async def test_approval_manager_records_tool_metadata():
    """Verify ApprovalManager stores is_destructive and is_read_only in PendingApprovalRequest."""
    mgr = ApprovalManager()
    req = await mgr.create_request(
        session_id="s_test",
        tool_name="write",
        arguments={"path": "file.py"},
        reason="Writing file",
        is_destructive=True,
        is_read_only=False,
    )

    assert req.is_destructive is True
    assert req.is_read_only is False

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.exec_policy import ExecPolicy, ExecVerdict
from app.core.approval import ApprovalManager, ApprovalDecisionAudit
from app.core.events import ApprovalRequiredEvent, ToolResultEvent
from app.core.tools.base import ToolContext, ToolResult
from app.core.tools.bash_tool import BashTool
from app.core.agent_loop import agent_loop

client = TestClient(app)

@pytest.mark.asyncio
async def test_exec_policy_requiere_aprobacion_classification():
    policy = ExecPolicy()

    # Sensitive action -> REQUIERE_APROBACION
    verdict = policy.evaluate("git reset --hard", project_trusted=True)
    assert verdict == ExecVerdict.REQUIERE_APROBACION

    # Untrusted project -> REQUIERE_APROBACION
    verdict_untrusted = policy.evaluate("ls -la", project_trusted=False)
    assert verdict_untrusted == ExecVerdict.REQUIERE_APROBACION

    # Dangerous action -> DENEGAR
    verdict_dangerous = policy.evaluate("sudo rm -rf /", project_trusted=True)
    assert verdict_dangerous == ExecVerdict.DENEGAR


@pytest.mark.asyncio
async def test_human_approval_flow_approved(tmp_path):
    mgr = ApprovalManager(default_timeout_seconds=5, audit_log_path=tmp_path / "audit.jsonl")

    async def simulate_operator():
        await asyncio.sleep(0.05)
        pending = await mgr.list_pending(session_id="s1")
        assert len(pending) == 1
        await mgr.submit_decision(
            approval_id=pending[0].approval_id,
            approved=True,
            actor="operator_jane",
            reason="Confirmed safe"
        )

    task_operator = asyncio.create_task(simulate_operator())

    audit = await mgr.request_approval(
        session_id="s1",
        tool_name="bash",
        arguments={"command": "git reset --hard"},
        reason="Sensitive command",
        command="git reset --hard",
    )

    await task_operator

    assert audit.status == "approved"
    assert audit.actor == "operator_jane"
    assert audit.session_id == "s1"
    assert audit.action == "git reset --hard"

    logs = await mgr.get_audit_logs(session_id="s1")
    assert len(logs) == 1
    assert logs[0].approval_id == audit.approval_id


@pytest.mark.asyncio
async def test_human_approval_flow_denied(tmp_path):
    mgr = ApprovalManager(default_timeout_seconds=5, audit_log_path=tmp_path / "audit.jsonl")

    async def simulate_operator():
        await asyncio.sleep(0.05)
        pending = await mgr.list_pending(session_id="s2")
        assert len(pending) == 1
        await mgr.submit_decision(
            approval_id=pending[0].approval_id,
            approved=False,
            actor="operator_john",
            reason="Risk too high"
        )

    task_operator = asyncio.create_task(simulate_operator())

    audit = await mgr.request_approval(
        session_id="s2",
        tool_name="bash",
        arguments={"command": "git clean -fd"},
        reason="Sensitive command",
        command="git clean -fd",
    )

    await task_operator

    assert audit.status == "denied"
    assert audit.actor == "operator_john"
    assert audit.session_id == "s2"


@pytest.mark.asyncio
async def test_human_approval_flow_timeout_default_deny(tmp_path):
    mgr = ApprovalManager(default_timeout_seconds=1, audit_log_path=tmp_path / "audit.jsonl")

    audit = await mgr.request_approval(
        session_id="s3",
        tool_name="bash",
        arguments={"command": "npm install -g malicious-pkg"},
        reason="Sensitive command",
        command="npm install -g malicious-pkg",
    )

    assert audit.status == "timed_out"
    assert audit.actor == "system_timeout"
    assert audit.session_id == "s3"
    assert "timeout" in audit.reason.lower()


@pytest.mark.asyncio
async def test_agent_loop_human_in_the_loop_integration(tmp_path):
    # Mock backend router
    class DummyRouter:
        async def generate_with_tools(self, messages, tools_schema, model_params):
            yield {"tool_calls": [{"id": "tc_1", "function": {"name": "bash", "arguments": {"command": "git reset --hard"}}}]}

    dummy_router = DummyRouter()
    bash_tool = BashTool()
    tools = [bash_tool]
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    events = []

    async def consume_agent_loop_and_approve():
        with patch("app.core.sandbox.is_bwrap_available", return_value=True), \
             patch("app.core.sandbox.SandboxedExecutor.execute_cmd", return_value={"stdout": "HEAD is now at 1234\n", "stderr": "", "exit_code": 0}):

            async for ev in agent_loop(
                messages=[{"role": "user", "content": "Reset git state"}],
                tools=tools,
                context=ctx,
                backend_router=dummy_router,
                max_turns=1,
                session_id="test_hitl_session"
            ):
                events.append(ev)
                if isinstance(ev, ApprovalRequiredEvent):
                    from app.core.approval import approval_manager
                    # Submit decision using the exact approval_id emitted in the event
                    await approval_manager.submit_decision(
                        approval_id=ev.approval_id,
                        approved=True,
                        actor="test_admin",
                        reason="Approved for regression test"
                    )

    await consume_agent_loop_and_approve()

    # Verify ApprovalRequiredEvent was emitted
    appr_events = [e for e in events if isinstance(e, ApprovalRequiredEvent)]
    assert len(appr_events) == 1
    assert appr_events[0].tool_name == "bash"
    assert appr_events[0].session_id == "test_hitl_session"

    # Verify ToolResultEvent executed after approval
    result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(result_events) == 1
    assert result_events[0].is_error is False
    assert "HEAD is now at 1234" in result_events[0].output


def test_rest_api_approvals_endpoints():
    # 1. Initially pending approvals list is empty
    resp = client.get("/api/agent/approvals/pending")
    assert resp.status_code == 200

    # 2. Try deciding non-existent approval_id -> 404
    resp = client.post(
        "/api/agent/approvals/non_existent_id/decide",
        json={"decision": "approved", "actor": "tester", "reason": "N/A"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_configurable_approval_timeout_hierarchy():
    mgr = ApprovalManager(default_timeout_seconds=30)
    session_id = "sess_config_timeout"

    # Default timeout
    assert mgr.get_effective_timeout(session_id=session_id) == 30

    # Per-session timeout
    mgr.set_session_timeout(session_id, 120)
    assert mgr.get_effective_timeout(session_id=session_id) == 120

    # Request-level override takes precedence over session-level timeout
    assert mgr.get_effective_timeout(session_id=session_id, request_timeout=5) == 5


@pytest.mark.asyncio
async def test_non_live_session_approval_timeout_visibility(tmp_path):
    from app.core.session_manager import SessionManager
    from app.core.approval import approval_manager

    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    sess_mgr = SessionManager(sessions_dir=sess_dir)
    session_id = sess_mgr.create(cwd=str(tmp_path), approval_timeout_seconds=1)

    class DummyRouter:
        async def generate_with_tools(self, messages, tools_schema, model_params):
            yield {"tool_calls": [{"id": "tc_nonlive", "function": {"name": "bash", "arguments": {"command": "git reset --hard"}}}]}

    dummy_router = DummyRouter()
    bash_tool = BashTool()
    tools = [bash_tool]
    ctx = ToolContext(cwd=str(tmp_path), trusted=True, protected_files=set())

    events = []

    # Non-live execution: agent loop runs without any live client responding to approval
    async for ev in agent_loop(
        messages=[{"role": "user", "content": "Execute git reset --hard in background"}],
        tools=tools,
        context=ctx,
        backend_router=dummy_router,
        max_turns=1,
        session_manager=sess_mgr,
        session_id=session_id,
        approval_timeout_seconds=1,
    ):
        events.append(ev)

    # 1. Verify ToolResultEvent indicates default denial due to timeout
    result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(result_events) == 1
    assert result_events[0].is_error is True
    assert "timed_out" in result_events[0].output or "deniegada" in result_events[0].output

    # 2. Verify SessionMetadata was updated with blocked_actions_count and approval_summary
    meta = sess_mgr.open(session_id)
    assert meta.blocked_actions_count == 1
    assert len(meta.approval_summary) == 1
    assert meta.approval_summary[0]["status"] == "timed_out"
    assert meta.approval_summary[0]["actor"] == "system_timeout"

    # 3. Verify prominent steering message was persisted for future operators inspecting session history
    undelivered = sess_mgr.get_undelivered_steering_messages(session_id)
    assert len(undelivered) >= 1
    block_notices = [m for m in undelivered if "[ACCION_BLOQUEADA_POR_APROBACION_HUMANA]" in m["content"]]
    assert len(block_notices) == 1
    assert "git reset --hard" in block_notices[0]["content"]

    # 4. Verify audit log recorded the timeout decision
    audit_logs = await approval_manager.get_audit_logs(session_id=session_id)
    assert len(audit_logs) >= 1
    assert audit_logs[-1].status == "timed_out"

import os
import json
import socket
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from app.core.audit import (
    AuditLogManager, AuditLogRecord, ActorInfo,
    SyslogExporter, WebhookExporter, record_approval_decision
)
from app.core.logging_config import set_trace_id, get_trace_id
from app.core.extensions.api import AgentStartPayload, ToolPreExecPayload, ToolPostExecPayload
from app.core.extensions.registry import ExtensionRegistry
from app.core.approval import ApprovalManager, ApprovalDecisionAudit


@pytest.fixture
def temp_audit_file(tmp_path):
    return tmp_path / "structured_audit_logs.jsonl"


@pytest.fixture
def audit_mgr(temp_audit_file):
    return AuditLogManager(log_file_path=temp_audit_file)


def test_audit_log_schema_actor_trace_timestamp(audit_mgr):
    token = set_trace_id("test-trace-12345")
    try:
        record = audit_mgr.record(AuditLogRecord(
            action="tool.execute",
            resource="bash:ls -la",
            status="SUCCESS",
            actor=ActorInfo(type="user", id="usr-test", user_id="usr-test", org_id="org-acme"),
            session_id="sess-001"
        ))

        assert record.audit_id.startswith("aud-")
        assert record.trace_id == "test-trace-12345"
        assert record.actor.user_id == "usr-test"
        assert record.actor.org_id == "org-acme"
        assert record.action == "tool.execute"
        assert record.resource == "bash:ls -la"
        assert record.status == "SUCCESS"
        assert record.timestamp is not None
    finally:
        set_trace_id("")


def test_audit_log_append_only_persistence(temp_audit_file, audit_mgr):
    rec1 = audit_mgr.record(AuditLogRecord(
        action="action.one",
        resource="res1",
        status="SUCCESS"
    ))
    rec2 = audit_mgr.record(AuditLogRecord(
        action="action.two",
        resource="res2",
        status="FAILED"
    ))

    # File append check
    assert temp_audit_file.exists()
    lines = temp_audit_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    parsed1 = json.loads(lines[0])
    parsed2 = json.loads(lines[1])

    assert parsed1["audit_id"] == rec1.audit_id
    assert parsed1["action"] == "action.one"
    assert parsed2["audit_id"] == rec2.audit_id
    assert parsed2["action"] == "action.two"

    records = audit_mgr.get_records()
    assert len(records) >= 2
    record_ids = [r.audit_id for r in records]
    assert rec1.audit_id in record_ids
    assert rec2.audit_id in record_ids


def test_syslog_rfc5424_exporter_formatting_and_sending():
    exporter = SyslogExporter(host="127.0.0.1", port=5140, protocol="udp")
    record = AuditLogRecord(
        action="tool.bash.execute",
        resource="rm -rf /tmp/test",
        status="APPROVED",
        trace_id="trace-syslog-99"
    )

    rfc_msg = exporter.format_rfc5424(record)
    assert rfc_msg.startswith("<38>1 ")
    assert "cognito-agent" in rfc_msg
    assert "tool_bash_execute" in rfc_msg
    assert "trace-syslog-99" in rfc_msg

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        success = exporter.send(record)
        assert success is True
        assert mock_sock.sendto.called
        sent_bytes = mock_sock.sendto.call_args[0][0]
        assert b"<38>1 " in sent_bytes
        assert b"trace-syslog-99" in sent_bytes


def test_webhook_exporter_sending():
    exporter = WebhookExporter(webhook_url="http://localhost:9999/webhook/audit")
    record = AuditLogRecord(
        action="agent.start",
        resource="agent_loop:sess-100",
        status="STARTED",
        trace_id="trace-webhook-01"
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success = exporter.send(record)
        assert success is True
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:9999/webhook/audit"
        assert req.get_header("Content-type") == "application/json"
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["action"] == "agent.start"
        assert payload["trace_id"] == "trace-webhook-01"


@pytest.mark.asyncio
async def test_aud020_lifecycle_hooks_capture():
    from app.core.audit import audit_logger, register_audit_lifecycle_hooks
    registry = ExtensionRegistry()
    register_audit_lifecycle_hooks(registry)

    # Fire on_agent_start
    start_payload = AgentStartPayload(
        session_id="sess-aud020",
        cwd="/workspace",
        messages=[],
        model_name="qwen2.5-coder",
        trace_id="trace-hooks-1"
    )
    await registry.fire("on_agent_start", start_payload, "/workspace")

    # Fire on_tool_pre_exec
    pre_payload = ToolPreExecPayload(
        session_id="sess-aud020",
        cwd="/workspace",
        tool_name="write_file",
        arguments={"path": "test.txt", "content": "hello"},
        tool_call_id="call-123",
        turn=1,
        trace_id="trace-hooks-1"
    )
    await registry.fire("on_tool_pre_exec", pre_payload, "/workspace")

    # Fire on_tool_post_exec
    post_payload = ToolPostExecPayload(
        session_id="sess-aud020",
        cwd="/workspace",
        tool_name="write_file",
        arguments={"path": "test.txt", "content": "hello"},
        tool_call_id="call-123",
        output="File written successfully",
        is_error=False,
        turn=1,
        trace_id="trace-hooks-1"
    )
    await registry.fire("on_tool_post_exec", post_payload, "/workspace")

    records = audit_logger.get_records(session_id="sess-aud020")
    actions = [r.action for r in records]
    assert "agent.start" in actions
    assert "tool.pre_exec" in actions
    assert "tool.post_exec" in actions


@pytest.mark.asyncio
async def test_aud021_approval_decision_unification(temp_audit_file, tmp_path):
    appr_mgr = ApprovalManager(audit_log_path=tmp_path / "approval_audit_logs.jsonl")

    # Request approval and submit decision
    req = await appr_mgr.create_request(
        session_id="sess-appr-unify",
        tool_name="bash",
        arguments={"command": "rm -rf /workspace/target"},
        reason="Destructive command",
        command="rm -rf /workspace/target"
    )

    decision_task = asyncio.create_task(appr_mgr.wait_for_decision(req.approval_id))
    await asyncio.sleep(0.01)

    submitted = await appr_mgr.submit_decision(
        approval_id=req.approval_id,
        approved=True,
        actor="sec-admin@company.com",
        reason="Approved after inspection"
    )
    await decision_task

    assert submitted is not None
    assert submitted.status == "approved"

    # Verify single source of truth in audit log
    audit_logs = await appr_mgr.get_audit_logs(session_id="sess-appr-unify")
    assert len(audit_logs) >= 1
    found = next((l for l in audit_logs if l.approval_id == req.approval_id), None)
    assert found is not None
    assert found.actor == "sec-admin@company.com"
    assert found.status == "approved"

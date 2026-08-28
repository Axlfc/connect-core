import os
import json
import uuid
import socket
import logging
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from app.core.logging_config import get_trace_id

logger = logging.getLogger("cognito.backend.audit")


class ActorInfo(BaseModel):
    type: str = "agent"  # "user", "agent", "system", "operator"
    id: str = "cognito-agent"
    user_id: Optional[str] = "usr-default-local"
    org_id: Optional[str] = "org-default-local"
    email: Optional[str] = None


class AuditLogRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    org_id: str = "org-default-local"
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = "usr-default-local"
    actor: ActorInfo = Field(default_factory=ActorInfo)
    action: str  # e.g., "tool.execute", "agent.start", "approval.decision"
    resource: str  # e.g., affected file path, command, tool name
    trace_id: str = ""
    request_id: Optional[str] = None
    status: str = "SUCCESS"  # "SUCCESS", "FAILED", "BLOCKED", "APPROVED", "DENIED", "TIMED_OUT"
    approval_metadata: Optional[Dict[str, Any]] = None
    security_context: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None


class SyslogExporter:
    """
    Exports structured audit records via Syslog (RFC 5424 text protocol) using standard library `socket`.
    """
    def __init__(self, host: str, port: int, protocol: str = "udp"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()

    def format_rfc5424(self, record: AuditLogRecord) -> str:
        # PRI = facility * 8 + severity. (facility=4 auth, severity=6 info -> 38)
        pri = 38
        version = 1
        timestamp = record.timestamp
        hostname = socket.gethostname() or "localhost"
        app_name = "cognito-agent"
        proc_id = str(os.getpid())
        msg_id = record.action.replace(".", "_")
        msg = record.model_dump_json()
        return f"<{pri}>{version} {timestamp} {hostname} {app_name} {proc_id} {msg_id} - {msg}"

    def send(self, record: AuditLogRecord) -> bool:
        if not self.host or self.port <= 0:
            return False
        try:
            formatted_msg = self.format_rfc5424(record)
            msg_bytes = formatted_msg.encode("utf-8")
            if self.protocol == "tcp":
                with socket.create_connection((self.host, self.port), timeout=5) as sock:
                    sock.sendall(msg_bytes + b"\n")
            else:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(msg_bytes, (self.host, self.port))
            return True
        except Exception as e:
            logger.warning(f"Failed to export audit record to Syslog ({self.host}:{self.port}): {e}")
            return False


class WebhookExporter:
    """
    Exports structured audit records to HTTP webhook using standard library `urllib`.
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, record: AuditLogRecord) -> bool:
        if not self.webhook_url:
            return False
        try:
            payload_bytes = record.model_dump_json().encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 201, 202, 204)
        except Exception as e:
            logger.warning(f"Failed to export audit record to Webhook ({self.webhook_url}): {e}")
            return False


class AuditLogManager:
    """
    Central Audit Log Manager.
    Captures, persists (in-memory, JSONL file, and append-only database table),
    and exports (Syslog RFC 5424 & HTTP Webhook) structured audit logs.
    """
    def __init__(self, log_file_path: Optional[Path] = None):
        self.log_file_path = log_file_path or (Path.home() / ".cognito" / "sessions" / "structured_audit_logs.jsonl")
        self._records: List[AuditLogRecord] = []
        self.syslog_exporter: Optional[SyslogExporter] = None
        self.webhook_exporter: Optional[WebhookExporter] = None
        self.reload_exporters()

    def reload_exporters(self) -> None:
        """
        Reloads exporter configurations from environment variables.
        """
        syslog_host = os.getenv("COGNITO_SYSLOG_HOST", "")
        syslog_port = int(os.getenv("COGNITO_SYSLOG_PORT", "0"))
        syslog_proto = os.getenv("COGNITO_SYSLOG_PROTO", "udp")
        self.syslog_exporter = SyslogExporter(syslog_host, syslog_port, syslog_proto) if syslog_host and syslog_port > 0 else None

        webhook_url = os.getenv("COGNITO_AUDIT_WEBHOOK_URL", "")
        self.webhook_exporter = WebhookExporter(webhook_url) if webhook_url else None

    def record(self, record: AuditLogRecord) -> AuditLogRecord:
        if not record.trace_id:
            record.trace_id = get_trace_id() or ""

        self._records.append(record)
        self._append_to_file(record)
        self._append_to_db(record)

        if self.syslog_exporter:
            self.syslog_exporter.send(record)
        if self.webhook_exporter:
            self.webhook_exporter.send(record)

        logger.info(
            f"AUDIT_EVENT [{record.audit_id}] action={record.action} | "
            f"resource={record.resource} | status={record.status} | trace_id={record.trace_id}"
        )
        return record

    def _append_to_file(self, record: AuditLogRecord) -> None:
        try:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
        except Exception as e:
            logger.warning(f"Failed writing audit log to disk: {e}")

    def _append_to_db(self, record: AuditLogRecord) -> None:
        """
        Persists into DB table `structured_audit_logs`.
        Note: strictly APPEND-ONLY (only INSERT statement used).
        """
        try:
            from app.core.database import get_db_sync_session
            from app.models.db import DBStructuredAuditLog

            db = get_db_sync_session()
            try:
                raw_payload = record.model_dump()
                db_item = DBStructuredAuditLog(
                    audit_id=record.audit_id,
                    timestamp=record.timestamp,
                    org_id=record.org_id,
                    project_id=record.project_id,
                    session_id=record.session_id,
                    user_id=record.user_id,
                    actor=record.actor.model_dump(),
                    action=record.action,
                    resource=record.resource,
                    trace_id=record.trace_id,
                    request_id=record.request_id,
                    status=record.status,
                    approval_metadata=record.approval_metadata,
                    security_context=record.security_context,
                    raw_payload=raw_payload,
                )
                db.add(db_item)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed inserting audit record to DB: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed connecting DB for audit record: {e}")

    def get_records(self, session_id: Optional[str] = None, org_id: Optional[str] = None) -> List[AuditLogRecord]:
        results = list(self._records)
        if self.log_file_path.exists():
            try:
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            rec = AuditLogRecord(**json.loads(line))
                            if not any(r.audit_id == rec.audit_id for r in results):
                                results.append(rec)
            except Exception as e:
                logger.warning(f"Error reading audit logs file: {e}")

        filtered = []
        for r in results:
            if session_id and r.session_id != session_id:
                continue
            if org_id and r.org_id != org_id:
                continue
            filtered.append(r)
        return filtered


audit_logger = AuditLogManager()


def record_approval_decision(decision: Any) -> AuditLogRecord:
    actor_name = getattr(decision, "actor", "operator")
    actor_type = "operator" if actor_name != "system_timeout" else "system"
    approval_dict = decision.model_dump() if hasattr(decision, "model_dump") else dict(decision)

    rec = AuditLogRecord(
        audit_id=getattr(decision, "approval_id", f"aud-{uuid.uuid4().hex[:12]}"),
        timestamp=getattr(decision, "timestamp", datetime.now(timezone.utc).isoformat()),
        session_id=getattr(decision, "session_id", None),
        actor=ActorInfo(type=actor_type, id=actor_name, email=actor_name if "@" in str(actor_name) else None),
        action="approval.decision",
        resource=getattr(decision, "action", "unknown_action"),
        status=getattr(decision, "status", "APPROVED").upper(),
        approval_metadata=approval_dict,
        details={"reason": getattr(decision, "reason", None)}
    )
    return audit_logger.record(rec)


async def audit_on_agent_start(payload: Any) -> Optional[str]:
    session_id = getattr(payload, "session_id", None)
    trace_id = getattr(payload, "trace_id", "") or ""
    messages = getattr(payload, "messages", [])
    model_name = getattr(payload, "model_name", None)
    max_turns = getattr(payload, "max_turns", 10)

    rec = AuditLogRecord(
        session_id=session_id,
        trace_id=trace_id,
        action="agent.start",
        resource=f"agent_loop:{session_id or 'unknown'}",
        status="STARTED",
        actor=ActorInfo(type="agent", id="cognito-agent"),
        details={"messages_count": len(messages), "model": model_name, "max_turns": max_turns}
    )
    audit_logger.record(rec)
    return None


async def audit_on_tool_pre_exec(payload: Any) -> Optional[str]:
    session_id = getattr(payload, "session_id", None)
    trace_id = getattr(payload, "trace_id", "") or ""
    tool_name = getattr(payload, "tool_name", "unknown_tool")
    arguments = getattr(payload, "arguments", {})
    tool_call_id = getattr(payload, "tool_call_id", "")
    turn = getattr(payload, "turn", 1)

    rec = AuditLogRecord(
        session_id=session_id,
        trace_id=trace_id,
        action="tool.pre_exec",
        resource=f"{tool_name}:{arguments}",
        status="ATTEMPTING",
        actor=ActorInfo(type="agent", id="cognito-agent"),
        details={"tool_call_id": tool_call_id, "turn": turn}
    )
    audit_logger.record(rec)
    return None


async def audit_on_tool_post_exec(payload: Any) -> Optional[str]:
    session_id = getattr(payload, "session_id", None)
    trace_id = getattr(payload, "trace_id", "") or ""
    tool_name = getattr(payload, "tool_name", "unknown_tool")
    arguments = getattr(payload, "arguments", {})
    tool_call_id = getattr(payload, "tool_call_id", "")
    turn = getattr(payload, "turn", 1)
    is_error = getattr(payload, "is_error", False)
    output = getattr(payload, "output", "")

    rec = AuditLogRecord(
        session_id=session_id,
        trace_id=trace_id,
        action="tool.post_exec",
        resource=f"{tool_name}:{arguments}",
        status="FAILED" if is_error else "SUCCESS",
        actor=ActorInfo(type="agent", id="cognito-agent"),
        details={"tool_call_id": tool_call_id, "turn": turn, "is_error": is_error, "output_preview": output[:200] if output else ""}
    )
    audit_logger.record(rec)
    return None


def register_audit_lifecycle_hooks(registry=None) -> None:
    try:
        from app.core.extensions.registry import extension_registry
        reg = registry or extension_registry
        reg.register_hook("on_agent_start", audit_on_agent_start, origin=None)
        reg.register_hook("on_tool_pre_exec", audit_on_tool_pre_exec, origin=None)
        reg.register_hook("on_tool_post_exec", audit_on_tool_post_exec, origin=None)
    except Exception as e:
        logger.warning(f"Failed registering audit lifecycle hooks: {e}")


# Register default global audit hooks
register_audit_lifecycle_hooks()

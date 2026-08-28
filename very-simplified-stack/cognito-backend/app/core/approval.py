import asyncio
import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_APPROVAL_TIMEOUT_SECONDS = int(os.getenv("COGNITO_APPROVAL_TIMEOUT_SECONDS", "30"))

class ApprovalDecisionAudit(BaseModel):
    approval_id: str
    session_id: str
    action: str
    actor: str = "operator"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str  # "approved", "denied", "timed_out"
    reason: Optional[str] = None


class PendingApprovalRequest(BaseModel):
    approval_id: str
    session_id: str
    tool_name: str
    arguments: Dict[str, Any]
    command: Optional[str] = None
    reason: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timeout_seconds: int = DEFAULT_APPROVAL_TIMEOUT_SECONDS
    is_destructive: bool = False
    is_read_only: bool = False


class PendingApprovalState:
    def __init__(self, request: PendingApprovalRequest):
        self.request = request
        self.future: asyncio.Future[ApprovalDecisionAudit] = asyncio.get_running_loop().create_future()


class ApprovalManager:
    """
    Manages human-in-the-loop approval requests for sensitive actions.
    Pauses agent execution until explicit decision or timeout.
    Tracks structured audit log records designed for future SIEM integration (AUD-009).
    """

    def __init__(self, default_timeout_seconds: Optional[int] = None, audit_log_path: Optional[Path] = None):
        self._pending: Dict[str, PendingApprovalState] = {}
        self._audit_log: List[ApprovalDecisionAudit] = []
        self._session_timeouts: Dict[str, int] = {}
        self._lock = asyncio.Lock()
        self.default_timeout_seconds = (
            default_timeout_seconds
            if default_timeout_seconds is not None
            else DEFAULT_APPROVAL_TIMEOUT_SECONDS
        )
        self.audit_log_path = audit_log_path or (Path.home() / ".cognito" / "sessions" / "approval_audit_logs.jsonl")

    def set_session_timeout(self, session_id: str, timeout_seconds: int) -> None:
        """
        Registers a session-specific approval timeout.
        """
        self._session_timeouts[session_id] = timeout_seconds

    def get_effective_timeout(
        self, session_id: Optional[str] = None, request_timeout: Optional[int] = None
    ) -> int:
        """
        Resolves the timeout hierarchy:
        1. Explicit request-level timeout
        2. Session-level registered timeout
        3. Global ApprovalManager default_timeout_seconds
        """
        if request_timeout is not None:
            return request_timeout
        if session_id and session_id in self._session_timeouts:
            return self._session_timeouts[session_id]
        return self.default_timeout_seconds

    def _append_audit_log_to_disk(self, decision: ApprovalDecisionAudit) -> None:
        """
        Persists audit decisions to disk so they survive backend restarts.
        """
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a") as f:
                f.write(decision.model_dump_json() + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist approval audit log to disk: {e}")

    def _read_audit_logs_from_disk(self, session_id: Optional[str] = None) -> List[ApprovalDecisionAudit]:
        """
        Loads persisted audit decisions from disk file.
        """
        if not self.audit_log_path.exists():
            return []
        disk_logs = []
        try:
            with open(self.audit_log_path, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        audit = ApprovalDecisionAudit(**data)
                        if not session_id or audit.session_id == session_id:
                            disk_logs.append(audit)
        except Exception as e:
            logger.warning(f"Failed reading approval audit log from disk: {e}")
        return disk_logs

    async def create_request(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str,
        command: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        approval_id: Optional[str] = None,
        is_destructive: bool = False,
        is_read_only: bool = False,
    ) -> PendingApprovalRequest:
        """
        Registers a pending approval request in state without blocking execution.
        """
        appr_id = approval_id or f"appr-{uuid.uuid4().hex[:12]}"
        effective_timeout = self.get_effective_timeout(session_id=session_id, request_timeout=timeout_seconds)

        request = PendingApprovalRequest(
            approval_id=appr_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            command=command,
            reason=reason,
            timeout_seconds=effective_timeout,
            is_destructive=is_destructive,
            is_read_only=is_read_only,
        )

        state = PendingApprovalState(request)

        async with self._lock:
            self._pending[appr_id] = state

        logger.info(
            f"Approval registered [{appr_id}] for session {session_id} | "
            f"tool={tool_name} | command={command or 'N/A'} | timeout={effective_timeout}s"
        )

        return request

    async def wait_for_decision(self, approval_id: str) -> ApprovalDecisionAudit:
        """
        Awaits a decision on a previously created pending approval request, enforcing timeout and fallback denial.
        """
        async with self._lock:
            state = self._pending.get(approval_id)

        if not state:
            raise KeyError(f"Approval request '{approval_id}' not found in pending state.")

        effective_timeout = state.request.timeout_seconds
        session_id = state.request.session_id
        tool_name = state.request.tool_name
        arguments = state.request.arguments
        command = state.request.command

        try:
            decision = await asyncio.wait_for(
                asyncio.shield(state.future), timeout=float(effective_timeout)
            )
        except asyncio.TimeoutError:
            logger.warning(f"Approval request [{approval_id}] timed out after {effective_timeout}s. Denying by default.")
            decision = ApprovalDecisionAudit(
                approval_id=approval_id,
                session_id=session_id,
                action=command or f"{tool_name}:{arguments}",
                actor="system_timeout",
                status="timed_out",
                reason=f"No operator response within {effective_timeout} seconds timeout.",
            )
            if not state.future.done():
                state.future.set_result(decision)
        finally:
            async with self._lock:
                self._pending.pop(approval_id, None)

        async with self._lock:
            self._audit_log.append(decision)

        self._append_audit_log_to_disk(decision)

        try:
            from app.core.audit import record_approval_decision
            record_approval_decision(decision)
        except Exception as e:
            logger.warning(f"Failed recording approval decision in unified audit log: {e}")

        if decision.status in ("timed_out", "denied"):
            logger.warning(
                f"[APPROVAL_BLOCKED] Session {session_id} action '{decision.action}' "
                f"blocked due to {decision.status}: {decision.reason}"
            )

        return decision

    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        reason: str,
        command: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        approval_id: Optional[str] = None,
        is_destructive: bool = False,
        is_read_only: bool = False,
    ) -> ApprovalDecisionAudit:
        """
        Registers request and awaits decision in a single call.
        """
        req = await self.create_request(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            reason=reason,
            command=command,
            timeout_seconds=timeout_seconds,
            approval_id=approval_id,
            is_destructive=is_destructive,
            is_read_only=is_read_only,
        )
        return await self.wait_for_decision(req.approval_id)

    async def submit_decision(
        self,
        approval_id: str,
        approved: bool,
        actor: str = "operator",
        reason: Optional[str] = None,
    ) -> Optional[ApprovalDecisionAudit]:
        """
        Submits an operator decision ('approved' or 'denied') for a pending request.
        Resolves the paused agent future.
        """
        async with self._lock:
            state = self._pending.get(approval_id)

        if not state:
            logger.warning(f"No pending approval found for ID {approval_id}")
            return None

        status = "approved" if approved else "denied"
        decision = ApprovalDecisionAudit(
            approval_id=approval_id,
            session_id=state.request.session_id,
            action=state.request.command or f"{state.request.tool_name}:{state.request.arguments}",
            actor=actor,
            status=status,
            reason=reason or f"Manually {status} by {actor}",
        )

        if not state.future.done():
            state.future.set_result(decision)

        return decision

    async def list_pending(self, session_id: Optional[str] = None) -> List[PendingApprovalRequest]:
        """
        Lists active pending approval requests.
        """
        async with self._lock:
            requests = [s.request for s in self._pending.values()]
        if session_id:
            return [r for r in requests if r.session_id == session_id]
        return requests

    async def get_audit_logs(self, session_id: Optional[str] = None) -> List[ApprovalDecisionAudit]:
        """
        Retrieves recorded structured audit decision logs from memory, disk, and unified audit logger.
        """
        async with self._lock:
            mem_logs = list(self._audit_log)

        disk_logs = self._read_audit_logs_from_disk(session_id=session_id)

        # Combine and deduplicate by approval_id
        combined: Dict[str, ApprovalDecisionAudit] = {}
        for l in disk_logs:
            combined[l.approval_id] = l
        for l in mem_logs:
            if not session_id or l.session_id == session_id:
                combined[l.approval_id] = l

        try:
            from app.core.audit import audit_logger
            audit_records = audit_logger.get_records(session_id=session_id)
            for rec in audit_records:
                if rec.action == "approval.decision" and rec.approval_metadata:
                    appr = ApprovalDecisionAudit(**rec.approval_metadata)
                    if appr.approval_id not in combined:
                        if not mem_logs and not disk_logs:
                            combined[appr.approval_id] = appr
                        elif any(m.approval_id == appr.approval_id for m in mem_logs + disk_logs):
                            combined[appr.approval_id] = appr
        except Exception as e:
            logger.warning(f"Failed querying unified audit log for approvals: {e}")

        return list(combined.values())


# Default global instance
approval_manager = ApprovalManager()
